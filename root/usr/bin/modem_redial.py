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
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "1.1.4-1"

PID_FILE = "/tmp/run/modem_redial.pid"


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


def load_uci_config() -> dict:
    """读取 OpenWrt UCI 配置 (若无 uci 命令则尝试直接解析配置文件)"""
    config = {
        "enabled": "0",
        "router_url": DEFAULT_URL,
        "username": DEFAULT_USER,
        "password": DEFAULT_PASS,
        "wan_name": DEFAULT_WAN,
        "pause_seconds": str(DEFAULT_DELAY),
        "log_file": "/tmp/log/modem_redial.log"
    }

    # 1. 优先使用 uci 命令导出
    try:
        res = subprocess.run(["uci", "-q", "export", "modem_redial"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("option"):
                    parts = line.split(maxsplit=2)
                    if len(parts) >= 3:
                        key = parts[1]
                        val = parts[2].strip("'\"")
                        config[key] = val
            return config
    except Exception:
        pass

    # 2. 直接读取 /etc/config/modem_redial
    config_file = "/etc/config/modem_redial"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("option"):
                        parts = line.split(maxsplit=2)
                        if len(parts) >= 3:
                            key = parts[1]
                            val = parts[2].strip("'\"")
                            config[key] = val
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


def redial_wan(
    router_ip: str,
    username: str,
    password: str,
    target_wan_name: str,
    pause_seconds: int,
    log_file: str = None
) -> bool:
    """执行完整的重新拨号流程"""
    log("=" * 60, log_file)
    log(f"开始执行光猫重新拨号任务 (目标: {target_wan_name})", log_file)
    client = HuaweiONTClient(base_url=router_ip, username=username, password=password)

    switched_to_manual = False
    switched_to_alwayson = False
    domain = None

    try:
        log(f"正在登录光猫后台 ({router_ip}) ...", log_file)
        if not client.login():
            log("[-] 登录失败，请检查账号密码或光猫连接状态！", log_file)
            return False
        log("[+] 登录成功！", log_file)

        log(f"正在查找目标 WAN 连接: {target_wan_name} ...", log_file)
        target_wan = client.find_wan(target_wan_name)
        if not target_wan:
            log(f"[-] 未找到包含 '{target_wan_name}' 的 WAN 连接！", log_file)
            return False

        domain = target_wan["domain"]
        old_ip = target_wan["ip"]
        log(f"[+] 找到目标连接: {target_wan['name']} (当前IP: {old_ip}, 模式: {target_wan['trigger']})", log_file)

        # 1. 切换为 Manual (手动拨号，触发下线)
        log("[步骤 1/3] 正在将拨号方式切换为【手动】(Manual)，断开当前连接...", log_file)
        if not client.set_connection_trigger(domain, "Manual"):
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
                log("[-] 重试切换【自动】拨号方式依然失败！", log_file)
                return False
        switched_to_alwayson = True
        log("[+] 切换为【自动】成功，等待光猫获取新 IP...", log_file)

        # 循环检查是否上线并获取到了新 IP
        new_ip = None
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

    # 重载服务并清除 LuCI 缓存以确保新配置与视图生效 (使用 rpcd reload 保留用户会话，绝不执行 restart 导致用户退登)
    try:
        subprocess.run(["/etc/init.d/modem_redial", "restart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["rm", "-f", "/tmp/luci-indexcache*"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["rm", "-rf", "/tmp/luci-modulecache/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["/etc/init.d/rpcd", "reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    set_update_status("success", "插件升级成功！", success=True)
    return {
        "success": True,
        "message": "插件升级成功！"
    }


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
    parser.add_argument("--pkg-url", default="", help="指定升级包下载地址 (可选)")

    args = parser.parse_args()

    if args.check_update:
        info = check_github_update()
        print(json.dumps(info, ensure_ascii=False))
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

    # 如果是定时任务模式，严格校验插件是否开启
    if args.cron and uci_conf.get("enabled", "0") == "0":
        log("[!] 插件处于禁用状态，跳过定时执行。", args.logfile)
        sys.exit(0)

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
        success = redial_wan(
            router_ip=args.url,
            username=args.user,
            password=args.password,
            target_wan_name=args.wan,
            pause_seconds=args.delay,
            log_file=args.logfile
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
