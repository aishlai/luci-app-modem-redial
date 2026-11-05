#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
北京联通华为光猫 V271-20 自动重拨助手 (Huawei V271-20 Auto-Redial Assistant)
OpenWrt / LuCI 后端核心脚本 (纯原生标准库，支持 UCI 配置读取与 CLI 参数)
"""

# ==============================================================================
# 【默认配置区】
# 优先从 OpenWrt UCI 配置文件 (/etc/config/modem_redial) 读取。
# 若脱离 LuCI 环境作为独立脚本运行，可直接在此处填入默认信息。
# ==============================================================================
DEFAULT_URL = ""                      # 光猫后台地址，如 "http://192.168.1.1" 或 "http://192.168.50.1"
DEFAULT_USER = "user"                 # 光猫登录账号，通常为 "user"
DEFAULT_PASS = ""                     # 光猫登录密码 (光猫背标贴纸默认密码或自定义密码)
DEFAULT_WAN = "2_INTERNET_R_VID_3961" # 目标 WAN 连接名称 (例如北京联通: 2_INTERNET_R_VID_3961)
DEFAULT_DELAY = 3                     # 切换为手动拨号后的下线等待秒数 (默认 3 秒)
# ==============================================================================

import argparse
import base64
import http.cookiejar
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "1.5.5-1"

PID_FILE = "/tmp/run/modem_redial.pid"
WATCHDOG_PID_FILE = "/tmp/run/modem_redial_watchdog.pid"


def write_pid(pid: int = None):
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid or os.getpid()))
    except Exception:
        pass


def remove_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def is_redial_running() -> bool:
    """检查是否已经有重拨进程在运行"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pid_str = f.read().strip()
            if pid_str:
                pid = int(pid_str)
                # 若 PID 就是自身，绝非冲突
                if pid == os.getpid():
                    return False
                # 检查进程是否存在 (发信号 0)
                os.kill(pid, 0)
                # 校验进程命令行，防止残留的死 PID 恰好被系统其他无关进程复用
                proc_cmd = f"/proc/{pid}/cmdline"
                if os.path.exists(proc_cmd):
                    try:
                        with open(proc_cmd, "rb") as pf:
                            cmd_bytes = pf.read()
                        if b"modem_redial" not in cmd_bytes:
                            remove_pid()
                            return False
                    except Exception:
                        pass
                return True
        except (ProcessLookupError, OSError):
            remove_pid()
            return False
        except Exception:
            return False
    return False


def write_watchdog_pid(pid: int = None):
    try:
        os.makedirs(os.path.dirname(WATCHDOG_PID_FILE), exist_ok=True)
        with open(WATCHDOG_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid or os.getpid()))
    except Exception:
        pass


def remove_watchdog_pid():
    try:
        if os.path.exists(WATCHDOG_PID_FILE):
            os.remove(WATCHDOG_PID_FILE)
    except Exception:
        pass


def is_watchdog_running() -> bool:
    """检查是否已有 UDP 连通性监测守护进程在运行"""
    if os.path.exists(WATCHDOG_PID_FILE):
        try:
            with open(WATCHDOG_PID_FILE, "r", encoding="utf-8") as f:
                pid_str = f.read().strip()
            if pid_str:
                pid = int(pid_str)
                if pid == os.getpid():
                    return True
                os.kill(pid, 0)
                proc_cmd = f"/proc/{pid}/cmdline"
                if os.path.exists(proc_cmd):
                    try:
                        with open(proc_cmd, "rb") as pf:
                            cmd_bytes = pf.read()
                        if b"watchdog" not in cmd_bytes:
                            remove_watchdog_pid()
                            return False
                    except Exception:
                        pass
                return True
        except (ProcessLookupError, OSError):
            remove_watchdog_pid()
            return False
        except Exception:
            return False
    return False


def daemonize(log_file: str):
    """
    标准 Unix 双 fork 守护进程化
    彻底切断与父进程 (rpcd / cgi-io) 的会话和所有管道连接，
    使 rpcd / ubus / HTTP 请求能够在毫秒级立即返回，绝不阻塞后端！
    """
    # 写入初始行，确保日志文件永远不为 0 字节 (避免 rpcd file read 报 NoData 错误)
    if log_file:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"[{now_str}] [*] 正在启动后台守护重拨换IP任务...\n")
                f.flush()
        except Exception:
            pass

    try:
        pid = os.fork()
        if pid > 0:
            # 第一次 fork 的父进程直接向 stdout 打印 STARTED 并退出，通知前端任务已启动
            print("STARTED", flush=True)
            sys.stdout.flush()
            os._exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork #1 failed: {e}\n")
        os._exit(1)

    os.setsid()

    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork #2 failed: {e}\n")
        os._exit(1)

    # 孙进程 (真正的独立后台守护任务)
    sys.stdout.flush()
    sys.stderr.flush()

    # 关闭从 rpcd 继承的所有多余文件描述符 (0 到 1024)
    for fd in range(0, 1024):
        try:
            os.close(fd)
        except OSError:
            pass

    devnull_fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull_fd, 0)
    os.dup2(devnull_fd, 1)
    os.dup2(devnull_fd, 2)
    if devnull_fd > 2:
        try:
            os.close(devnull_fd)
        except OSError:
            pass


def log(msg: str, log_file: str = None):
    """统一日志输出：写日志文件并刷新"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now_str}] {msg}"

    if log_file:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
                f.flush()
        except Exception:
            pass
    else:
        print(formatted, flush=True)


DEFAULT_UDP_TARGETS = [
    "223.5.5.5:53",
    "119.29.29.29:53",
    "180.76.76.76:53",
    "114.114.114.114:53",
    "stun.miwifi.com:3478",
    "ntp.aliyun.com:123"
]


DEFAULT_QOS_LOG = "/etc/modem_redial_qos.log"
DEFAULT_LIVE_QOS_LOG = "/tmp/log/modem_redial_live_qos.log"


def load_uci_config() -> dict:
    """读取 OpenWrt UCI 配置 (若无 uci 命令则尝试直接解析配置文件)"""
    config = {
        "enabled": "0",
        "router_url": DEFAULT_URL,
        "username": DEFAULT_USER,
        "password": DEFAULT_PASS,
        "wan_name": DEFAULT_WAN,
        "pause_seconds": str(DEFAULT_DELAY),
        "log_file": "/tmp/log/modem_redial.log",
        "udp_watchdog_enabled": "0",
        "udp_check_interval": "60",
        "udp_fail_threshold": "2",
        "udp_cooldown": "180",
        "udp_log_file": DEFAULT_QOS_LOG,
        "udp_targets": list(DEFAULT_UDP_TARGETS),
        "ntfy_enabled": "0",
        "ntfy_server": "https://ntfy.sh",
        "ntfy_topic": "",
        "ntfy_token": "",
        "notify_event_manual": "1",
        "notify_event_cron": "1",
        "notify_event_qos": "1",
        "notify_event_fail": "1"
    }

    def parse_lines(lines):
        targets_list = []
        for line in lines:
            line = line.strip()
            if line.startswith("option"):
                parts = line.split(maxsplit=2)
                if len(parts) >= 3:
                    config[parts[1]] = parts[2].strip("'\"")
            elif line.startswith("list"):
                parts = line.split(maxsplit=2)
                if len(parts) >= 3 and parts[1] == "udp_targets":
                    targets_list.append(parts[2].strip("'\""))
        if targets_list:
            config["udp_targets"] = targets_list

    # 1. 优先使用 uci 命令导出
    try:
        res = subprocess.run(["uci", "-q", "export", "modem_redial"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout:
            parse_lines(res.stdout.splitlines())
            return config
    except Exception:
        pass

    # 2. 直接读取 /etc/config/modem_redial
    config_file = "/etc/config/modem_redial"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                parse_lines(f.readlines())
        except Exception:
            pass

    return config


def decode_huawei_str(s: str) -> str:
    """解码光猫接口中转义的字符串 (例如 \\x5f -> _, \\x2e -> .)"""
    if not s:
        return ""
    return re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)


class HuaweiONTClient:
    def __init__(self, base_url: str = "http://192.168.1.1", username: str = "user", password: str = "", timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.host = urllib.parse.urlparse(self.base_url).hostname

        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self._last_ont_token = ""

    def _request(self, url: str, data: dict = None, headers: dict = None) -> tuple:
        req_headers = dict(self.default_headers)
        if headers:
            req_headers.update(headers)

        encoded_data = None
        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, headers=req_headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                content = resp.read().decode("utf-8", errors="ignore")
                resp_headers = resp.headers
                return status_code, content, resp_headers
        except urllib.error.HTTPError as e:
            content = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
            return e.code, content, e.headers
        except Exception as e:
            raise RuntimeError(f"请求 {url} 发生异常: {e}")

    def login(self) -> bool:
        """登录光猫后台"""
        rand_url = f"{self.base_url}/asp/GetRandCount.asp"
        status, content, _ = self._request(rand_url, data={}, headers={"Referer": f"{self.base_url}/"})
        if status != 200:
            return False

        rand_token = content.strip().lstrip("\ufeff")
        pwd_b64 = base64.b64encode(self.password.encode("utf-8")).decode("ascii")

        c1 = http.cookiejar.Cookie(0, "Cookie", "body:Language:chinese:id=-1", None, False, self.host, False, False, "/", True, False, None, True, None, None, {})
        c2 = http.cookiejar.Cookie(0, "MenuJumpIndex", "0", None, False, self.host, False, False, "/", True, False, None, True, None, None, {})
        self.cookie_jar.set_cookie(c1)
        self.cookie_jar.set_cookie(c2)

        login_url = f"{self.base_url}/login.cgi"
        payload = {
            "UserName": self.username,
            "PassWord": pwd_b64,
            "Language": "chinese",
            "x.X_HW_Token": rand_token
        }
        headers = {"Referer": f"{self.base_url}/", "Origin": self.base_url}
        status, resp_text, resp_headers = self._request(login_url, data=payload, headers=headers)
        if status != 200:
            return False

        cookie_names = [c.name for c in self.cookie_jar]
        return "CookieHttp" in cookie_names or "sid=" in resp_headers.get("Set-Cookie", "") or "index.asp" in resp_text

    def get_ont_token(self) -> str:
        """提取页面操作 Token (带 403 自动重新登录)"""
        wan_url = f"{self.base_url}/html/bbsp/wan/wan.asp"
        status = None
        for attempt in range(3):
            try:
                status, content, _ = self._request(wan_url, headers={"Referer": f"{self.base_url}/index.asp"})
                if status == 200:
                    match = re.search(r'id=[\"\']?hwonttoken[\"\']?[^>]*value=[\"\']?([^\"\'\s>]+)', content)
                    if not match:
                        match = re.search(r'<input[^>]*name=[\"\']?onttoken[\"\']?[^>]*value=[\"\']?([^\"\'\s>]+)', content)
                    if match:
                        self._last_ont_token = match.group(1)
                        return self._last_ont_token
                elif status in (401, 403) and attempt < 2:
                    time.sleep(1)
                    self.login()
            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    self.login()
        raise RuntimeError(f"获取 wan.asp onttoken 失败 (状态码: {status})")

    def get_rand_token(self) -> str:
        """从 GetRandToken.asp 获取当前会话随机 Token (官方 logoutfunc 标准方式)"""
        try:
            token_url = f"{self.base_url}/html/ssmp/common/GetRandToken.asp"
            headers = {"Referer": f"{self.base_url}/index.asp"}
            status, content, _ = self._request(token_url, data={}, headers=headers)
            if status == 200 and content.strip():
                return content.strip().lstrip("\ufeff")
        except Exception:
            pass
        return ""

    def logout(self, ont_token: str = None) -> bool:
        """退出登录，注销光猫后台会话，释放单用户登录锁"""
        token = ont_token or getattr(self, "_last_ont_token", "")
        if not token:
            token = self.get_rand_token()
        if not token:
            try:
                token = self.get_ont_token()
            except Exception:
                pass

        logout_url = f"{self.base_url}/logout.cgi?RequestFile=html/logout.html"
        payload = {"x.X_HW_Token": token} if token else {}
        headers = {
            "Referer": f"{self.base_url}/index.asp",
            "Origin": self.base_url
        }
        try:
            status, _, _ = self._request(logout_url, data=payload, headers=headers)
            return status == 200
        except Exception:
            # 华为光猫在处理注销时会主动断开底层 TCP 连接，会话已被成功销毁
            return True

    def get_wan_connections(self) -> list:
        """获取所有 WAN 连接信息 (支持 403 自动重新登录)"""
        list_url = f"{self.base_url}/html/bbsp/common/getwanlist.asp"
        headers = {"Referer": f"{self.base_url}/html/bbsp/wan/wan.asp"}
        status = None
        for attempt in range(3):
            try:
                status, content, _ = self._request(list_url, headers=headers)
                if status in (401, 403) and attempt < 2:
                    time.sleep(1)
                    self.login()
                    continue
                if status == 200:
                    wan_list = []
                    for match in re.finditer(r'new\s+WanPPP\((.*?)\)', content):
                        raw_args = [x.strip('\"\' ') for x in match.group(1).split(',')]
                        if len(raw_args) < 15:
                            continue

                        wan_list.append({
                            "domain": raw_args[0],
                            "trigger": raw_args[3],
                            "status": raw_args[5],
                            "name": decode_huawei_str(raw_args[8]),
                            "ip": decode_huawei_str(raw_args[14]),
                        })
                    return wan_list
            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    self.login()
        raise RuntimeError(f"获取 WAN 列表失败 (最后状态码: {status})")

    def find_wan(self, target_name: str) -> dict:
        for wan in self.get_wan_connections():
            if target_name.upper() in wan["name"].upper():
                return wan
        return None

    def set_connection_trigger(self, wan_domain: str, trigger_mode: str) -> bool:
        """修改拨号方式 (Manual / AlwaysOn) (带失败重试机制)"""
        for attempt in range(3):
            try:
                onttoken = self.get_ont_token()
                complex_url = f"{self.base_url}/complex.cgi?y={wan_domain}&RequestFile=html/bbsp/wan/confirmwancfginfo.html"
                post_data = {
                    "y.ConnectionTrigger": trigger_mode,
                    "x.X_HW_Token": onttoken
                }
                headers = {
                    "Referer": f"{self.base_url}/html/bbsp/wan/wan.asp",
                    "Origin": self.base_url
                }
                status, _, _ = self._request(complex_url, data=post_data, headers=headers)
                if status == 200:
                    return True
                if status in (401, 403) and attempt < 2:
                    time.sleep(1)
                    self.login()
            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    self.login()
        return False


def query_status_json(router_ip: str, username: str, password: str, wan_name: str) -> str:
    """输出 JSON 格式状态供 LuCI 前端异步读取"""
    uci_conf = load_uci_config()
    if uci_conf.get("enabled", "0") != "1":
        return json.dumps({
            "status": "未启用",
            "ip": "未启用",
            "trigger": "-",
            "wan": wan_name or "-",
            "running": False,
            "enabled": False
        }, ensure_ascii=False)

    # 若重拨进程正在运行，直接返回状态，避免并发登录导致光猫锁死或踢出会话
    if is_redial_running():
        return json.dumps({
            "status": "重拨中...",
            "ip": "正在获取新IP...",
            "trigger": "切换中",
            "wan": wan_name or "-",
            "running": True
        }, ensure_ascii=False)

    if not router_ip or not username or not password:
        return json.dumps({
            "status": "未配置",
            "ip": "未配置",
            "trigger": "-",
            "wan": wan_name or "-",
            "running": False
        }, ensure_ascii=False)

    client = HuaweiONTClient(base_url=router_ip, username=username, password=password)
    try:
        if not client.login():
            return json.dumps({"status": "登录失败", "ip": "未知", "trigger": "未知", "wan": wan_name, "running": False}, ensure_ascii=False)
        target = client.find_wan(wan_name)
        if not target:
            return json.dumps({"status": "未找到指定WAN", "ip": "未知", "trigger": "未知", "wan": wan_name, "running": False}, ensure_ascii=False)
        return json.dumps({
            "status": target["status"],
            "ip": target["ip"],
            "trigger": target["trigger"],
            "wan": target["name"],
            "domain": target["domain"],
            "running": False
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": f"错误: {e}", "ip": "未知", "trigger": "未知", "wan": wan_name, "running": False}, ensure_ascii=False)
    finally:
        try:
            client.logout()
        except Exception:
            pass


def send_ntfy_notification(
    title: str,
    message: str,
    priority: int = 3,
    tags: list = None,
    conf: dict = None
) -> tuple:
    """
    发送 Ntfy 消息通知 (以纯 Markdown 格式作为 Body 发送至 ntfy.sh 或自建服务器)
    返回: (success: bool, msg: str)
    """
    if conf is None:
        conf = load_uci_config()

    if str(conf.get("enabled", "0")) != "1" or str(conf.get("ntfy_enabled", "0")) != "1":
        return False, "插件未启用或 Ntfy 功能未启用"

    server = (conf.get("ntfy_server") or "https://ntfy.sh").strip().rstrip("/")
    topic = (conf.get("ntfy_topic") or "").strip().lstrip("/")
    token = (conf.get("ntfy_token") or "").strip()

    if not topic:
        return False, "Ntfy Topic 为空，请先配置主题名称"

    # 1. 构造带查询参数的 URL (Query Parameters 格式传递元数据，兼容性最佳)
    params = {
        "title": title,
        "priority": str(priority),
        "markdown": "yes"
    }
    if tags:
        params["tags"] = ",".join(tags)

    query_str = urllib.parse.urlencode(params)
    url = f"{server}/{topic}?{query_str}"

    # 2. 构造 HTTP 头部 (RFC 2047 编码 Title，支持 Content-Type: text/markdown)
    import base64
    b64_title = base64.b64encode(title.encode("utf-8")).decode("ascii")
    headers = {
        "Content-Type": "text/markdown; charset=utf-8",
        "Title": f"=?utf-8?B?{b64_title}?=",
        "Priority": str(priority),
        "Markdown": "yes",
        "User-Agent": "OpenWrt-Modem-Redial/Ntfy"
    }
    if tags:
        headers["Tags"] = ",".join(tags)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 3. Request Body 采用纯 Markdown 文本，绝不使用 JSON 格式
    data_bytes = message.encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

    last_err = ""
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                if resp.status in (200, 201, 204):
                    return True, "发送成功"
                else:
                    last_err = f"Ntfy 服务器返回状态码: {resp.status}"
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="ignore")[:100]
            except Exception:
                pass
            last_err = f"HTTP {e.code} 错误: {err_body or e.reason}"
        except Exception as e:
            last_err = f"网络请求异常: {e}"

        if attempt < 2:
            time.sleep(3)

    return False, last_err


def notify_redial_result(
    trigger_source: str,
    success: bool,
    old_ip: str = "",
    new_ip: str = "",
    elapsed: int = 0,
    fail_reason: str = "",
    wan_name: str = "",
    extra_info: str = "",
    delay_seconds: int = 10,
    log_file: str = None
):
    """根据用户配置的事件定义，发送对应的 Ntfy Markdown 格式消息通知"""
    try:
        conf = load_uci_config()
        if str(conf.get("enabled", "0")) != "1" or str(conf.get("ntfy_enabled", "0")) != "1":
            return

        # 检查当前事件是否在用户的接收订阅列表中
        if not success:
            if str(conf.get("notify_event_fail", "1")) != "1":
                return
        else:
            if trigger_source == "manual" and str(conf.get("notify_event_manual", "1")) != "1":
                return
            elif trigger_source == "cron" and str(conf.get("notify_event_cron", "1")) != "1":
                return
            elif trigger_source == "qos" and str(conf.get("notify_event_qos", "1")) != "1":
                return

        # 刚刚联网时路由表与 DNS 可能尚未完全就绪，延时等待确保网络链路彻底畅通
        if delay_seconds > 0:
            log(f"[*] [Ntfy] 刚刚完成联网，等待 {delay_seconds} 秒缓冲延时以确保网络与 DNS 完全稳定后再推送通知...", log_file)
            time.sleep(delay_seconds)

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        trigger_names = {
            "manual": "手动执行",
            "cron": "定时任务",
            "qos": "UDP QoS 触发"
        }
        src_name = trigger_names.get(trigger_source, "自动重拨")

        if success:
            ip_changed_tag = " *(已更换)*" if (new_ip and old_ip and new_ip != old_ip) else ""
            if trigger_source == "qos":
                title = "🚨 UDP QoS 阻断已解除并换新 IP"
                msg = (
                    f"### 🚨 UDP QoS 阻断已解除并换新 IP\n"
                    f"> **检测到运营商 UDP QoS 阻断，已自动重新拨号换 IP 恢复！**\n\n"
                    f"- **触发原因**: {extra_info or 'UDP 探测全部失败，疑似遭遇限速/阻断'}\n"
                    f"- **重拨耗时**: `{elapsed} 秒`\n"
                    f"- **重拨前 IP**: `{old_ip or '未知'}`\n"
                    f"- **重拨后 IP**: `{new_ip}`{ip_changed_tag}\n"
                    f"- **发生时间**: {now_str}"
                )
                priority = 4
                tags = ["rotating_light", "arrows_counterclockwise", "shield"]
            elif trigger_source == "cron":
                title = "🕒 光猫定时重拨换 IP 完成"
                msg = (
                    f"### 🕒 光猫定时重拨换 IP 完成\n"
                    f"> **计划任务定时重拨换 IP 成功！**\n\n"
                    f"- **目标接口**: `{wan_name}`\n"
                    f"- **重拨耗时**: `{elapsed} 秒`\n"
                    f"- **重拨前 IP**: `{old_ip or '未知'}`\n"
                    f"- **重拨后 IP**: `{new_ip}`{ip_changed_tag}\n"
                    f"- **发生时间**: {now_str}"
                )
                priority = 2
                tags = ["alarm_clock", "arrows_counterclockwise"]
            else:
                title = "⚡ 光猫手动重拨换 IP 完成"
                msg = (
                    f"### ⚡ 光猫手动重拨换 IP 完成\n"
                    f"> **光猫手动重新拨号换 IP 成功！**\n\n"
                    f"- **目标接口**: `{wan_name}`\n"
                    f"- **重拨耗时**: `{elapsed} 秒`\n"
                    f"- **重拨前 IP**: `{old_ip or '未知'}`\n"
                    f"- **重拨后 IP**: `{new_ip}`{ip_changed_tag}\n"
                    f"- **发生时间**: {now_str}"
                )
                priority = 3
                tags = ["zap", "arrows_counterclockwise", "white_check_mark"]
        else:
            title = f"⚠️ 光猫重拨换 IP 失败告警 ({src_name})"
            msg = (
                f"### ⚠️ 光猫重拨换 IP 失败告警 ({src_name})\n"
                f"> **【严重告警】光猫重拨换 IP 执行失败！**\n\n"
                f"- **触发方式**: {src_name}\n"
                f"- **目标接口**: `{wan_name}`\n"
                f"- **失败原因**: `{fail_reason or '执行异常或超时未上线'}`\n"
                f"- **累计耗时**: `{elapsed} 秒`\n"
                f"- **发生时间**: {now_str}\n"
                f"- **安全状态**: 已执行 AlwaysOn 回滚恢复，请检查光猫连接或密码"
            )
            priority = 5
            tags = ["warning", "rotating_light", "x"]

        ok, res_msg = send_ntfy_notification(title, msg, priority, tags, conf)
        if ok:
            log(f"[+] [Ntfy] Markdown 消息通知推送成功: {title}", log_file)
        else:
            log(f"[-] [Ntfy] Markdown 消息通知推送失败: {res_msg}", log_file)
    except Exception as e:
        log(f"[-] [Ntfy] 处理消息通知异常: {e}", log_file)


def redial_wan(
    router_ip: str,
    username: str,
    password: str,
    target_wan_name: str,
    pause_seconds: int,
    log_file: str = None,
    trigger_source: str = "manual",
    extra_info: str = ""
) -> bool:
    """执行完整的重新拨号流程"""
    t_start = time.time()
    old_ip = "未知"
    new_ip = None
    fail_reason = ""
    log("=" * 60, log_file)
    log(f"开始执行光猫重新拨号任务 (目标: {target_wan_name})", log_file)
    client = HuaweiONTClient(base_url=router_ip, username=username, password=password)

    switched_to_manual = False
    switched_to_alwayson = False
    domain = None

    try:
        log(f"正在登录光猫后台 ({router_ip}) ...", log_file)
        if not client.login():
            fail_reason = "登录光猫失败，请检查账号密码或光猫连接状态"
            log("[-] 登录失败，请检查账号密码或光猫连接状态！", log_file)
            return False
        log("[+] 登录成功！", log_file)

        log(f"正在查找目标 WAN 连接: {target_wan_name} ...", log_file)
        target_wan = client.find_wan(target_wan_name)
        if not target_wan:
            fail_reason = f"未找到包含 '{target_wan_name}' 的 WAN 连接"
            log(f"[-] 未找到包含 '{target_wan_name}' 的 WAN 连接！", log_file)
            return False

        domain = target_wan["domain"]
        old_ip = target_wan["ip"]
        log(f"[+] 找到目标连接: {target_wan['name']} (当前IP: {old_ip}, 模式: {target_wan['trigger']})", log_file)

        # 1. 切换为 Manual (手动拨号，触发下线)
        log("[步骤 1/3] 正在将拨号方式切换为【手动】(Manual)，断开当前连接...", log_file)
        if not client.set_connection_trigger(domain, "Manual"):
            fail_reason = "切换【手动】拨号方式失败"
            log("[-] 切换【手动】拨号方式失败！", log_file)
            return False
        switched_to_manual = True
        log("[+] 切换为【手动】成功，PPPoE 正在下线...", log_file)

        # 2. 暂停等待
        log(f"[步骤 2/3] 等待 {pause_seconds} 秒 ...", log_file)
        time.sleep(pause_seconds)

        # 3. 切换回 AlwaysOn (自动拨号，触发上线)
        log("[步骤 3/3] 正在将拨号方式切换回【自动】(AlwaysOn)，触发重新拨号...", log_file)
        if not client.set_connection_trigger(domain, "AlwaysOn"):
            log("[-] 首次切换【自动】失败，正在尝试重新建立会话重试...", log_file)
            time.sleep(1)
            client.login()
            if not client.set_connection_trigger(domain, "AlwaysOn"):
                fail_reason = "切换【自动】拨号方式失败"
                log("[-] 重试切换【自动】拨号方式依然失败！", log_file)
                return False
        switched_to_alwayson = True
        log("[+] 切换为【自动】成功，等待光猫获取新 IP...", log_file)

        # 循环检查是否上线并获取到了新 IP
        for attempt in range(1, 16):
            time.sleep(2)
            try:
                current_wans = client.get_wan_connections()
                curr = next((w for w in current_wans if w["domain"] == domain), None)
                if curr:
                    status = curr["status"]
                    ip = curr["ip"]
                    trigger = curr["trigger"]
                    log(f"    - 探测 {attempt:02d}: 状态={status}, 模式={trigger}, IP={ip}", log_file)
                    if status == "Connected" and ip and ip != "0.0.0.0":
                        new_ip = ip
                        break
            except Exception as e:
                log(f"    - 探测 {attempt:02d} 出错: {e}", log_file)

        if new_ip:
            log("-" * 60, log_file)
            log("[✓] 重新拨号成功！", log_file)
            log(f"    - 重拨前 IP: {old_ip}", log_file)
            log(f"    - 重拨后 IP: {new_ip}", log_file)
            if new_ip != old_ip:
                log("[✓] 成功获取到全新的公网 IP！", log_file)
            else:
                log("[!] 本次重拨获取的 IP 与原 IP 相同 (局端分配策略)，如需换段可适当延长断开时间。", log_file)
            log("=" * 60, log_file)
            return True
        else:
            fail_reason = "超时未检测到连接完全上线并获取有效公网 IP"
            log("[-] 超时未检测到连接完全上线，请检查光猫后台状态。", log_file)
            log("=" * 60, log_file)
            return False
    finally:
        # 紧急安全回滚机制：如果已经切换到 Manual 但未成功恢复为 AlwaysOn，强力恢复！
        if switched_to_manual and not switched_to_alwayson and domain:
            log("[!] 警告：检测到光猫处于【手动】状态，正在执行紧急安全恢复...", log_file)
            for recover_idx in range(3):
                try:
                    time.sleep(1)
                    client.login()
                    if client.set_connection_trigger(domain, "AlwaysOn"):
                        log("[+] 紧急恢复成功：WAN 接口已强行设为【自动】(AlwaysOn)！", log_file)
                        switched_to_alwayson = True
                        break
                except Exception as ex:
                    log(f"[-] 紧急恢复第 {recover_idx + 1} 次尝试失败: {ex}", log_file)

        log("[*] 正在退出光猫登录后台，释放单用户会话锁...", log_file)
        try:
            client.logout()
        except Exception:
            pass
        log("[*] 重拨换IP流程结束。", log_file)
        remove_pid()

        # 触发 Ntfy 消息通知（在会话完全注销、网络恢复后发出）
        notify_redial_result(
            trigger_source=trigger_source,
            success=bool(new_ip),
            old_ip=old_ip,
            new_ip=new_ip or "",
            elapsed=int(time.time() - t_start),
            fail_reason=fail_reason,
            wan_name=target_wan_name,
            extra_info=extra_info,
            log_file=log_file
        )


GITHUB_REPO = "aishlai/luci-app-modem-redial"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RAW_VER_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/VERSION"


def parse_version_tuple(v: str):
    v = re.sub(r'^[vV]', '', str(v).strip())
    parts = v.split('-', 1)
    main_ver = parts[0]
    rel = parts[1] if len(parts) > 1 else "0"
    num_parts = [int(x) if x.isdigit() else 0 for x in re.split(r'[._]', main_ver)]
    rel_num = int(rel) if rel.isdigit() else 0
    return (num_parts, rel_num)


def check_github_update() -> dict:
    """检查 GitHub Releases 是否有新版本"""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    current_ver = __version__
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenWrt-Modem-Redial-Updater",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 优先尝试直接访问 GitHub Releases API
    data = None
    last_err = None
    try:
        req = urllib.request.Request(GITHUB_API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        last_err = e

    if data and "tag_name" in data:
        tag_name = data.get("tag_name", "").strip()
        clean_tag = re.sub(r'^[vV]', '', tag_name)
        has_update = parse_version_tuple(clean_tag) > parse_version_tuple(current_ver)

        download_url = None
        for a in data.get("assets", []):
            name = a.get("name", "")
            if name.endswith(".ipk"):
                download_url = a.get("browser_download_url")
                break

        if not download_url:
            clean_tag_rel = clean_tag if '-' in clean_tag else f"{clean_tag}-1"
            download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{tag_name}/luci-app-modem-redial_{clean_tag_rel}_all.ipk"

        return {
            "success": True,
            "current_version": f"v{current_ver.split('-')[0]}",
            "latest_version": tag_name if tag_name.startswith("v") else f"v{tag_name}",
            "has_update": has_update,
            "download_url": download_url,
            "release_url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest"),
            "release_notes": data.get("body", "").strip(),
            "published_at": data.get("published_at", "")
        }

    # 2. 备选方案：若 API 访问受限（如 GFW 或速率限制），通过镜像查询 main 分支 VERSION 文件
    raw_urls = [
        GITHUB_RAW_VER_URL,
        f"https://ghfast.top/{GITHUB_RAW_VER_URL}"
    ]
    remote_ver_str = None
    for r_url in raw_urls:
        try:
            req = urllib.request.Request(r_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                if resp.status == 200:
                    remote_ver_str = resp.read().decode('utf-8').strip()
                    if remote_ver_str:
                        break
        except Exception as e:
            last_err = e
            continue

    if remote_ver_str:
        clean_tag = re.sub(r'^[vV]', '', remote_ver_str)
        has_update = parse_version_tuple(clean_tag) > parse_version_tuple(current_ver)
        main_tag = f"v{clean_tag.split('-')[0]}"
        download_url = f"https://github.com/{GITHUB_REPO}/releases/download/{main_tag}/luci-app-modem-redial_{clean_tag}_all.ipk"
        return {
            "success": True,
            "current_version": f"v{current_ver.split('-')[0]}",
            "latest_version": main_tag,
            "has_update": has_update,
            "download_url": download_url,
            "release_url": f"https://github.com/{GITHUB_REPO}/releases/latest",
            "release_notes": "通过镜像仓库检测到更新，建议升级。",
            "published_at": ""
        }

    return {
        "success": False,
        "current_version": f"v{current_ver.split('-')[0]}",
        "has_update": False,
        "error": f"无法连接到 GitHub 检查更新 ({last_err})"
    }


UPDATE_STATUS_FILE = "/tmp/log/modem_redial_update.status"


def set_update_status(stage: str, message: str, success: bool = None, error: str = None):
    """记录升级进度状态至临时文件，供前端异步轮询展示"""
    try:
        os.makedirs("/tmp/log", exist_ok=True)
        data = {
            "stage": stage,
            "message": message,
            "success": success,
            "error": error,
            "time": int(time.time())
        }
        with open(UPDATE_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def do_github_update(download_url: str = None) -> dict:
    """下载最新 IPK 并执行 opkg 重装升级，严格保护用户现有配置"""
    set_update_status("downloading", "正在准备升级安装包...")

    if not download_url:
        info = check_github_update()
        if not info.get("success") or not info.get("download_url"):
            err_msg = info.get("error") or "未获取到最新安装包下载地址"
            set_update_status("error", err_msg, success=False, error=err_msg)
            return {
                "success": False,
                "error": err_msg
            }
        download_url = info["download_url"]

    # 升级前备份现有用户配置文件 (内存级与临时文件级双重备份)
    cfg_file = "/etc/config/modem_redial"
    cfg_backup_content = None
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg_backup_content = f.read()
            with open("/tmp/_modem_redial_cfg.bak", "w", encoding="utf-8") as f:
                f.write(cfg_backup_content)
        except Exception:
            pass

    target_ipk = "/tmp/modem_redial_update.ipk"
    if os.path.exists(target_ipk):
        try:
            os.remove(target_ipk)
        except Exception:
            pass

    # 优先使用国内高速加速镜像，将直接访问放在最后；单次超时设为 8 秒 (18KB 安装包毫秒级可下载完)
    set_update_status("downloading", "正在从加速镜像下载最新安装包...")
    download_candidates = [
        f"https://ghfast.top/{download_url}",
        f"https://mirror.ghproxy.com/{download_url}",
        f"https://ghproxy.net/{download_url}",
        download_url
    ]

    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    downloaded = False
    last_err = None

    for d_url in download_candidates:
        try:
            req = urllib.request.Request(d_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenWrt-Modem-Redial-Updater"})
            with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                if resp.status == 200:
                    content = resp.read()
                    if len(content) > 1024:
                        with open(target_ipk, "wb") as f:
                            f.write(content)
                        downloaded = True
                        break
        except Exception as e:
            last_err = e
            continue

    if not downloaded or not os.path.exists(target_ipk):
        err_msg = f"下载新版安装包失败: {last_err}"
        set_update_status("error", err_msg, success=False, error=err_msg)
        return {
            "success": False,
            "error": err_msg
        }

    # 执行 opkg 安装
    set_update_status("installing", "安装包下载完成，正在执行覆盖安装与系统配置保护...")
    try:
        res = subprocess.run(
            ["opkg", "install", "--force-reinstall", target_ipk],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode != 0:
            err_msg = f"opkg 安装失败: {res.stderr or res.stdout}"
            set_update_status("error", err_msg, success=False, error=err_msg)
            return {
                "success": False,
                "error": err_msg
            }
    except Exception as e:
        err_msg = f"执行 opkg 异常: {e}"
        set_update_status("error", err_msg, success=False, error=err_msg)
        return {
            "success": False,
            "error": err_msg
        }
    finally:
        # 强力恢复配置兜底：确保用户配置绝对不被安装包默认模板冲掉
        if cfg_backup_content:
            try:
                with open(cfg_file, "w", encoding="utf-8") as f:
                    f.write(cfg_backup_content)
            except Exception:
                pass
        if os.path.exists("/tmp/_modem_redial_cfg.bak"):
            try:
                os.remove("/tmp/_modem_redial_cfg.bak")
            except Exception:
                pass
        if os.path.exists(target_ipk):
            try:
                os.remove(target_ipk)
            except Exception:
                pass

    # 重载服务并清除 LuCI 缓存以确保新配置与视图生效 (绝不执行 rpcd reload/restart 避免打断 ubus 与用户会话)
    try:
        subprocess.run(["/etc/init.d/modem_redial", "restart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["rm", "-f", "/tmp/luci-indexcache*"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["rm", "-rf", "/tmp/luci-modulecache/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    set_update_status("success", "插件升级成功！", success=True)
    return {
        "success": True,
        "message": "插件升级成功！"
    }


def probe_single_udp_target(target: str, timeout: float = 1.5) -> tuple:
    """
    单目标 UDP 双向探测：发送针对性协议请求并等待回包
    返回: (ok: bool, rtt_ms: int, msg: str, proto: str)
    """
    try:
        if ":" in target:
            host, port_str = target.split(":", 1)
            port = int(port_str.strip())
            host = host.strip()
        else:
            host = target.strip()
            port = 53
    except Exception as e:
        return False, 0, f"格式错误: {e}", "UNKNOWN"

    if port == 53:
        proto = "DNS"
        tx_id = 0x4a4a
        req = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
        for part in "baidu.com".split("."):
            req += bytes([len(part)]) + part.encode("ascii")
        req += b"\x00" + struct.pack(">HH", 1, 1)
        expect_check = lambda resp: len(resp) >= 12 and resp[:2] == struct.pack(">H", tx_id)
    elif port in (3478, 3479):
        proto = "STUN"
        # RFC 5389 STUN Binding Request
        req = struct.pack(">HHI", 0x0001, 0, 0x2112A442) + b"123456789012"
        expect_check = lambda resp: len(resp) >= 20 and resp[:2] == b"\x01\x01"
    elif port == 123:
        proto = "NTP"
        req = b"\x1b" + 47 * b"\0"
        expect_check = lambda resp: len(resp) >= 48
    else:
        proto = f"UDP-{port}"
        req = b"PING\n"
        expect_check = lambda resp: len(resp) > 0

    s = None
    t0 = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(req, (host, port))
        resp, _ = s.recvfrom(512)
        rtt = int((time.time() - t0) * 1000)
        if expect_check(resp):
            return True, rtt, "正常响应", proto
        return False, rtt, "回复内容异常", proto
    except socket.timeout:
        return False, 0, "超时无响应 (疑似阻断/丢包)", proto
    except Exception as e:
        return False, 0, str(e), proto
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


def check_all_udp_targets(targets: list, quick_exit: bool = False, timeout: float = 1.5) -> dict:
    """
    测试多个目标节点的 UDP 连通性
    若 quick_exit=True，只要有一个成功就立刻返回（常用于后台轮询，耗时仅几毫秒）
    """
    if not targets:
        targets = DEFAULT_UDP_TARGETS

    results = []
    any_ok = False
    working_target = ""

    for t in targets:
        if not t or not str(t).strip():
            continue
        t = str(t).strip()
        ok, rtt, msg, proto = probe_single_udp_target(t, timeout=timeout)
        results.append({
            "target": t,
            "ok": ok,
            "rtt": rtt,
            "msg": msg,
            "proto": proto
        })
        if ok:
            any_ok = True
            working_target = t
            if quick_exit:
                break

    return {
        "all_failed": not any_ok,
        "any_ok": any_ok,
        "working_target": working_target,
        "results": results
    }


def format_live_qos_log(res: dict, consecutive_fails: int = 0, fail_threshold: int = 2, interval: int = 60, status_note: str = "") -> str:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    results = res.get("results", []) if isinstance(res, dict) else []
    all_failed = res.get("all_failed", True) if isinstance(res, dict) else True

    lines = []
    lines.append("=" * 76)
    lines.append(f"[{now_str}] 🛡️ UDP 连通性监测实时日志 (每轮自动覆盖刷新)")
    lines.append("-" * 76)

    if all_failed:
        status_text = f"⚠️ 全部目标不可达！疑似遭遇运营商 UDP QoS 阻断 (连续失败: {consecutive_fails}/{fail_threshold})"
    else:
        status_text = f"✅ 通讯正常 (未遭遇 QoS 阻断) | 失败计数: {consecutive_fails}/{fail_threshold}"

    if status_note:
        status_text += f" | {status_note}"

    lines.append(f"当前状态: {status_text}")
    lines.append(f"探测策略: 每 {interval} 秒轮询一次 | 连续 {fail_threshold} 次全不通自动触发重拨换 IP")
    lines.append("-" * 76)
    h1, h2, h3, h4, h5 = "目标节点", "协议", "延迟", "状态", "详情说明"
    lines.append(f"{h1:<24} {h2:<6} {h3:<10} {h4:<6} {h5}")
    lines.append("-" * 76)

    for r in results:
        t = str(r.get("target", ""))
        proto = str(r.get("proto", "UDP"))
        ok = r.get("ok", False)
        rtt = r.get("rtt", 0)
        msg = str(r.get("msg", ""))
        rtt_str = f"{rtt} ms" if ok else "--"
        status_str = "✅ 畅通" if ok else "❌ 阻断"
        lines.append(f"{t:<24} {proto:<8} {rtt_str:<10} {status_str:<6} {msg}")

    lines.append("=" * 76)
    lines.append("💡 提示: 本日志仅展示当前最新一轮探测结果，存储于系统内存 (/tmp)，不消耗路由器闪存。")
    return "\n".join(lines) + "\n"


def write_live_qos_log(res: dict, consecutive_fails: int = 0, fail_threshold: int = 2, interval: int = 60, status_note: str = "") -> str:
    """
    输出最新一轮 UDP QoS 连通性监测结果至非持久化内存日志 (/tmp/log/modem_redial_live_qos.log)
    每轮探测覆盖刷新，不写闪存，并返回格式化文本
    """
    content = format_live_qos_log(res, consecutive_fails, fail_threshold, interval, status_note)
    try:
        os.makedirs(os.path.dirname(DEFAULT_LIVE_QOS_LOG), exist_ok=True)
        with open(DEFAULT_LIVE_QOS_LOG, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
    except Exception as e:
        sys.stderr.write(f"写入实时 QoS 日志失败: {e}\n")
    return content


def log_qos_event(msg: str, qos_log_file: str = DEFAULT_QOS_LOG):
    """
    记录独立的持久化 UDP QoS 重拨触发日志
    仅在检测全部失败且触发重拨换 IP 时记录，带有最大文件大小保护（自动轮转截断）
    """
    if not qos_log_file:
        qos_log_file = DEFAULT_QOS_LOG

    try:
        log_dir = os.path.dirname(os.path.abspath(qos_log_file))
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        qos_log_file = "/tmp/log/modem_redial_qos.log"
        os.makedirs("/tmp/log", exist_ok=True)

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now_str}] {msg}\n"

    try:
        # 文件体积控制：若超过 64KB，保留最近 32KB，防止消耗 Flash
        if os.path.exists(qos_log_file) and os.path.getsize(qos_log_file) > 65536:
            try:
                with open(qos_log_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                keep_content = content[-32768:]
                with open(qos_log_file, "w", encoding="utf-8") as f:
                    f.write("[--- 历史 QoS 日志已自动截断归档 ---]\n" + keep_content)
            except Exception:
                pass

        with open(qos_log_file, "a", encoding="utf-8") as f:
            f.write(entry)
            f.flush()
    except Exception as e:
        sys.stderr.write(f"写入 QoS 日志失败: {e}\n")


def run_udp_watchdog(log_file: str = "/tmp/log/modem_redial.log"):
    """
    后台守护进程：按指定间隔周期性探测 UDP 连通性，全不通时触发重拨换 IP
    并在专属持久化日志中记录触发详情
    """
    if is_watchdog_running():
        return
    write_watchdog_pid()
    log("[*] [UDP Watchdog] 启动 UDP QoS 连通性监测守护进程...", log_file)
    consecutive_fails = 0

    try:
        while True:
            try:
                # 重新加载最新的 UCI 配置 (允许用户在后台保存后立即动态生效)
                conf = load_uci_config()
                # 若插件或监测被关闭，进入低功耗待机轮询，不退出进程，一旦重新开启立即恢复监测
                if conf.get("enabled", "0") != "1" or conf.get("udp_watchdog_enabled", "0") != "1":
                    time.sleep(5)
                    continue

                interval = int(conf.get("udp_check_interval", "60") or "60")
                fail_threshold = int(conf.get("udp_fail_threshold", "2") or "2")
                cooldown = int(conf.get("udp_cooldown", "180") or "180")
                targets = conf.get("udp_targets") or DEFAULT_UDP_TARGETS
                if isinstance(targets, str):
                    targets = [t.strip() for t in targets.split() if t.strip()]

                # 执行 UDP 检测 (完整探测全部目标，输出完整实时指标)
                res = check_all_udp_targets(targets, quick_exit=False, timeout=1.5)
                if res["all_failed"]:
                    consecutive_fails += 1
                    write_live_qos_log(res, consecutive_fails, fail_threshold, interval, status_note="疑似被运营商阻断")
                    log(f"[!] [UDP Watchdog] UDP 探测全部失败 ({consecutive_fails}/{fail_threshold})！疑似遭遇运营商 UDP QoS 阻断。", log_file)
                    if consecutive_fails >= fail_threshold:
                        log("[!] [UDP Watchdog] 连续失败次数达到阈值，判定当前网络已被 QoS，立即触发光猫自动重拨换 IP！", log_file)
                        consecutive_fails = 0

                        if is_redial_running():
                            log("[!] [UDP Watchdog] 已有重拨任务在运行，跳过本次触发。", log_file)
                        else:
                            qos_log_path = conf.get("udp_log_file") or DEFAULT_QOS_LOG
                            targets_desc = ", ".join(targets)

                            # 记录进入独立持久化日志
                            log_qos_event(
                                f"[!] 检测到连续 {fail_threshold} 次所有 UDP 目标均不可达，判定遭遇运营商 UDP QoS 限制/阻断！\n"
                                f"                      探测目标列表: {targets_desc}\n"
                                f"                      正在执行光猫重新拨号以更换新 IP...",
                                qos_log_file=qos_log_path
                            )
                            write_live_qos_log(res, fail_threshold, fail_threshold, interval, status_note="达到阈值，正在触发光猫重拨换 IP...")

                            t_start = time.time()
                            redial_success = redial_wan(
                                router_ip=conf.get("router_url"),
                                username=conf.get("username"),
                                password=conf.get("password"),
                                target_wan_name=conf.get("wan_name", "2_INTERNET_R_VID_3961"),
                                pause_seconds=int(conf.get("pause_seconds", "3") or "3"),
                                log_file=log_file,
                                trigger_source="qos",
                                extra_info=f"连续 {fail_threshold} 次探测所有 UDP 目标均不可达 ({targets_desc})"
                            )
                            elapsed = int(time.time() - t_start)

                            if redial_success:
                                log(f"[+] [UDP Watchdog] 重拨换 IP 成功！进入冷却时间 {cooldown} 秒...", log_file)
                                new_ip_desc = ""
                                try:
                                    client = HuaweiONTClient(conf.get("router_url"), conf.get("username"), conf.get("password"))
                                    wan_info = client.get_wan_status()
                                    for w in wan_info.get("wan_list", []):
                                        if w.get("name") == conf.get("wan_name", "2_INTERNET_R_VID_3961") and w.get("ip"):
                                            new_ip_desc = f"，已成功获取新 IP: {w.get('ip')}"
                                            break
                                except Exception:
                                    pass

                                log_qos_event(
                                    f"[+] 光猫自动重拨完成 (耗时 {elapsed} 秒){new_ip_desc}，进入冷却缓冲期 {cooldown} 秒。\n"
                                    f"--------------------------------------------------------------------------------",
                                    qos_log_file=qos_log_path
                                )
                                write_live_qos_log(res, 0, fail_threshold, interval, status_note=f"重拨换 IP 完成{new_ip_desc}，冷却缓冲中 ({cooldown}s)")
                            else:
                                log(f"[-] [UDP Watchdog] 重拨换 IP 失败，将在 {cooldown} 秒后重试监测...", log_file)
                                log_qos_event(
                                    f"[-] 光猫自动重拨换 IP 失败 (耗时 {elapsed} 秒)，请检查光猫登录密码或连接，将在 {cooldown} 秒后重试。\n"
                                    f"--------------------------------------------------------------------------------",
                                    qos_log_file=qos_log_path
                                )
                                write_live_qos_log(res, 0, fail_threshold, interval, status_note=f"重拨换 IP 失败，将在 {cooldown} 秒后重试")

                            time.sleep(max(10, cooldown))
                            continue
                else:
                    if consecutive_fails > 0:
                        log(f"[+] [UDP Watchdog] UDP 连通性已恢复正常 (探测通过: {res.get('working_target', '')})。", log_file)
                    consecutive_fails = 0
                    write_live_qos_log(res, 0, fail_threshold, interval, status_note=f"首通节点: {res.get('working_target', '')}")

                time.sleep(max(5, interval))
            except Exception as e:
                log(f"[!] [UDP Watchdog] 监测运行异常: {e}", log_file)
                time.sleep(30)
    finally:
        remove_watchdog_pid()


def main():
    uci_conf = load_uci_config()

    parser = argparse.ArgumentParser(description="北京联通华为光猫 V271-20 自动重拨助手 (Huawei V271-20 Auto-Redial Assistant)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--url", default=uci_conf.get("router_url", ""), help="光猫地址")
    parser.add_argument("--user", default=uci_conf.get("username", ""), help="登录账号")
    parser.add_argument("--password", default=uci_conf.get("password", ""), help="登录密码")
    parser.add_argument("--wan", default=uci_conf.get("wan_name", "2_INTERNET_R_VID_3961"), help="目标 WAN 名称")
    parser.add_argument("--delay", type=int, default=int(uci_conf.get("pause_seconds", "3")), help="断开等待秒数")
    parser.add_argument("--logfile", default=uci_conf.get("log_file", "/tmp/log/modem_redial.log"), help="日志文件路径")
    parser.add_argument("--status", action="store_true", help="查询当前状态并以 JSON 输出")
    parser.add_argument("--start", action="store_true", help="后台异步守护启动重拨 (避免阻塞调用者)")
    parser.add_argument("--cron", action="store_true", help="定时任务执行模式 (严格遵循 enabled/cron_enabled)")
    parser.add_argument("--check-update", action="store_true", help="检查 GitHub 是否有新版本")
    parser.add_argument("--do-update", action="store_true", help="一键下载并升级到最新版本")
    parser.add_argument("--start-update", action="store_true", help="后台异步守护启动升级 (彻底根除 XHR 超时)")
    parser.add_argument("--get-update-status", action="store_true", help="获取当前升级进度状态 JSON")
    parser.add_argument("--pkg-url", default="", help="指定升级包下载地址 (可选)")
    parser.add_argument("--watchdog", action="store_true", help="运行 UDP 连通性监测后台守护进程")
    parser.add_argument("--start-watchdog", action="store_true", help="后台异步守护启动 UDP 监测进程")
    parser.add_argument("--stop-watchdog", action="store_true", help="停止 UDP 监测守护进程")
    parser.add_argument("--test-udp", action="store_true", help="测试当前网络环境下各目标 UDP 连通性并输出 JSON")
    parser.add_argument("--clear-qos-log", action="store_true", help="清空 UDP QoS 独立持久化日志")
    parser.add_argument("--show-qos-log", action="store_true", help="输出 UDP QoS 独立持久化日志内容")
    parser.add_argument("--show-live-qos-log", action="store_true", help="输出 UDP 实时监测最新单轮日志")
    parser.add_argument("--test-ntfy", action="store_true", help="发送测试 Ntfy 消息通知并输出 JSON")

    args = parser.parse_args()

    if args.test_ntfy:
        if str(uci_conf.get("enabled", "0")) != "1":
            print(json.dumps({"success": False, "error": "插件当前处于关闭状态，请先开启「启用插件」并保存应用"}, ensure_ascii=False))
            sys.exit(0)
        if str(uci_conf.get("ntfy_enabled", "0")) != "1":
            print(json.dumps({"success": False, "error": "请先开启「启用 Ntfy 通知」开关并点击保存应用"}, ensure_ascii=False))
            sys.exit(0)
        topic = (uci_conf.get("ntfy_topic") or "").strip()
        if not topic:
            print(json.dumps({"success": False, "error": "请先填写 Topic 主题名称并点击保存应用"}, ensure_ascii=False))
            sys.exit(0)

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        title = "🔔 光猫重拨助手 - Ntfy 测试通知"
        message = (
            f"### 🔔 光猫重拨助手 - Ntfy 测试通知\n"
            f"> **恭喜！这是一条来自 OpenWrt / iStoreOS 光猫重拨助手的测试通知。**\n\n"
            f"- **服务器**: `{uci_conf.get('ntfy_server', 'https://ntfy.sh')}`\n"
            f"- **订阅主题**: `{topic}`\n"
            f"- **发送时间**: {now_str}\n"
            f"- **消息格式**: `Markdown 纯文本渲染`\n\n"
            f"如果您收到了这条消息，说明您的 Ntfy 配置完全正确，可正常接收重拨与 QoS 告警通知！"
        )
        ok, res_msg = send_ntfy_notification(
            title=title,
            message=message,
            priority=3,
            tags=["tada", "bell"],
            conf=uci_conf
        )
        print(json.dumps({"success": ok, "error": ("" if ok else res_msg), "msg": res_msg}, ensure_ascii=False))
        sys.exit(0)

    if args.clear_qos_log:
        qos_log_path = uci_conf.get("udp_log_file") or DEFAULT_QOS_LOG
        try:
            with open(qos_log_path, "w", encoding="utf-8") as f:
                f.write("")
            print("CLEARED")
        except Exception as e:
            print(f"ERROR: {e}")
        sys.exit(0)

    if args.show_qos_log:
        qos_log_path = uci_conf.get("udp_log_file") or DEFAULT_QOS_LOG
        if os.path.exists(qos_log_path):
            with open(qos_log_path, "r", encoding="utf-8", errors="ignore") as f:
                sys.stdout.write(f.read())
        sys.exit(0)

    if args.show_live_qos_log:
        if os.path.exists(DEFAULT_LIVE_QOS_LOG):
            with open(DEFAULT_LIVE_QOS_LOG, "r", encoding="utf-8", errors="ignore") as f:
                sys.stdout.write(f.read())
        else:
            print("暂无实时检测日志，请等待监测后台运行或点击「⚡ 立即探测一轮」。")
        sys.exit(0)

    if args.stop_watchdog:
        if os.path.exists(WATCHDOG_PID_FILE):
            try:
                with open(WATCHDOG_PID_FILE, "r", encoding="utf-8") as f:
                    p = int(f.read().strip())
                os.kill(p, 15)
            except Exception:
                pass
            remove_watchdog_pid()
        print("STOPPED")
        sys.exit(0)

    if args.start_watchdog:
        if is_watchdog_running():
            print("ALREADY_RUNNING")
            sys.exit(0)
        daemonize(args.logfile)
        run_udp_watchdog(args.logfile)
        sys.exit(0)

    if args.test_udp:
        targets = uci_conf.get("udp_targets") or DEFAULT_UDP_TARGETS
        if isinstance(targets, str):
            targets = [t.strip() for t in targets.split() if t.strip()]
        res = check_all_udp_targets(targets, quick_exit=False, timeout=2.0)
        try:
            interval = int(uci_conf.get("udp_check_interval", "60") or "60")
            fail_threshold = int(uci_conf.get("udp_fail_threshold", "2") or "2")
            status_note = "手动单轮探测"
            if str(uci_conf.get("enabled", "0")) != "1":
                status_note += " (提示: 插件主开关当前未开启)"
            log_text = write_live_qos_log(res, 0 if res.get("any_ok") else 1, fail_threshold, interval, status_note=status_note)
            res["log_text"] = log_text
        except Exception as e:
            res["log_text"] = f"写入实时日志异常: {e}"
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(0)

    if args.watchdog:
        run_udp_watchdog(args.logfile)
        sys.exit(0)

    if args.check_update:
        info = check_github_update()
        print(json.dumps(info, ensure_ascii=False))
        sys.exit(0)

    if args.get_update_status:
        if os.path.exists(UPDATE_STATUS_FILE):
            try:
                with open(UPDATE_STATUS_FILE, "r", encoding="utf-8") as f:
                    sys.stdout.write(f.read())
                    sys.exit(0)
            except Exception:
                pass
        print(json.dumps({"stage": "idle", "message": "", "success": None}, ensure_ascii=False))
        sys.exit(0)

    if args.start_update:
        set_update_status("downloading", "正在准备下载最新安装包...")
        daemonize(args.logfile)
        do_github_update(args.pkg_url)
        sys.exit(0)

    if args.do_update:
        res = do_github_update(args.pkg_url)
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(0)

    if args.status:
        res = query_status_json(args.url, args.user, args.password, args.wan)
        print(res)
        sys.exit(0)

    # 检查是否已有任务在运行
    if is_redial_running():
        if args.start:
            print("ALREADY_RUNNING")
            sys.exit(0)
        log("[!] 已有重拨任务在运行中，请勿重复触发！", args.logfile)
        sys.exit(0)

    # 严格校验插件主开关是否开启：若未开启，阻止所有重拨任务（包括手动触发与定时任务）
    if uci_conf.get("enabled", "0") != "1":
        log("[!] 插件处于关闭禁用状态，已阻止执行重拨任务。", args.logfile)
        if args.start:
            print("PLUGIN_DISABLED")
            sys.exit(0)
        print("错误: 插件当前处于关闭状态，请先在配置中开启「启用插件」！")
        sys.exit(1)

    if not args.url or not args.user or not args.password:
        log("[!] 光猫后台地址、登录账号或密码未配置，请先在后台设置中保存！", args.logfile)
        if args.start:
            print("NOT_CONFIGURED")
            sys.exit(1)
        print("\n" + "=" * 70)
        print("  [!] 提示: 未检测到光猫配置信息！")
        print("-" * 70)
        print("  本插件需要光猫登录信息才能正常运行，您可以通过以下方式配置:\n")
        print("  【方式一：在 OpenWrt 网页后台配置 (最推荐)】")
        print("    登录路由器网页，打开【网络】或【服务】->【光猫重拨助手】填写并保存配置。\n")
        print("  【方式二：通过命令行参数直接运行】")
        print('    modem_redial --url http://192.168.1.1 --password "您的光猫密码"\n')
        print("  【方式三：编辑脚本头部默认参数】")
        print("    在 /usr/bin/modem_redial.py 顶部的【默认配置区】填写您的信息。")
        print("=" * 70 + "\n")
        sys.exit(1)

    # 若指定了 --start，执行彻底脱离父进程的 Unix 双 fork 守护进程化
    if args.start:
        daemonize(args.logfile)

    write_pid()
    try:
        trigger = "cron" if args.cron else "manual"
        success = redial_wan(
            router_ip=args.url,
            username=args.user,
            password=args.password,
            target_wan_name=args.wan,
            pause_seconds=args.delay,
            log_file=args.logfile,
            trigger_source=trigger
        )
        sys.exit(0 if success else 1)
    finally:
        remove_pid()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        err_msg = f"[{now_str}] [!] 发生未捕获异常: {e}\n{traceback.format_exc()}"
        try:
            with open("/tmp/log/modem_redial.log", "a", encoding="utf-8") as f:
                f.write(err_msg + "\n")
        except Exception:
            pass
        remove_pid()
        sys.exit(1)
