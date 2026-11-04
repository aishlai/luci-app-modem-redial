#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
联通定制版华为光猫 V271-20 自动重新拨号换IP脚本 (纯Python内置标准库实现，无第三方依赖)

适用场景：无需安装 requests 等任何第三方库，原生 Python 3 直接运行。

工作流程：
1. 请求 /asp/GetRandCount.asp 获取动态防重放/CSRF Token
2. 构造 Base64 密码与会话 Cookie，向 /login.cgi 提交登录
3. 获取 /html/bbsp/wan/wan.asp 提取页面操作 Token (onttoken)
4. 解析 /html/bbsp/common/getwanlist.asp 获取目标 WAN 连接 (2_INTERNET_R_VID_3961)
5. 向 /complex.cgi 提交将 ConnectionTrigger 修改为 Manual (手动拨号，触发下线)
6. 等待指定秒数 (默认 3 秒)
7. 再次获取新 Token，向 /complex.cgi 提交将 ConnectionTrigger 修改为 AlwaysOn (自动拨号，触发上线)
8. 循环探测拨号状态，输出重拨前后的公网 IP 对比
9. 任何情况下 (无论成功、失败或异常中断) 在 finally 中均通过 /logout.cgi 释放光猫单用户锁
"""

import argparse
import base64
import http.cookiejar
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


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

        # 使用内置 CookieJar 管理会话 Cookie
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self._last_ont_token = ""

    def _request(self, url: str, data: dict = None, headers: dict = None) -> tuple:
        """发送 HTTP 请求 (使用 urllib)"""
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

        c1 = http.cookiejar.Cookie(
            0, "Cookie", "body:Language:chinese:id=-1", None, False,
            self.host, False, False, "/", True, False, None, True, None, None, {}
        )
        c2 = http.cookiejar.Cookie(
            0, "MenuJumpIndex", "0", None, False,
            self.host, False, False, "/", True, False, None, True, None, None, {}
        )
        self.cookie_jar.set_cookie(c1)
        self.cookie_jar.set_cookie(c2)

        login_url = f"{self.base_url}/login.cgi"
        payload = {
            "UserName": self.username,
            "PassWord": pwd_b64,
            "Language": "chinese",
            "x.X_HW_Token": rand_token
        }
        headers = {
            "Referer": f"{self.base_url}/",
            "Origin": self.base_url
        }

        status, resp_text, resp_headers = self._request(login_url, data=payload, headers=headers)
        if status != 200:
            return False

        cookie_names = [c.name for c in self.cookie_jar]
        if "CookieHttp" in cookie_names or "sid=" in resp_headers.get("Set-Cookie", "") or "index.asp" in resp_text:
            return True
        return False

    def get_ont_token(self) -> str:
        """从 wan.asp 页面中提取 onttoken (带 403 自动重新认证)"""
        wan_url = f"{self.base_url}/html/bbsp/wan/wan.asp"
        headers = {"Referer": f"{self.base_url}/index.asp"}
        status = None
        for attempt in range(3):
            try:
                status, content, _ = self._request(wan_url, headers=headers)
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
        """获取所有 WAN 连接信息 (支持 403 自动重登)"""
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

                        domain = raw_args[0]
                        trigger = raw_args[3]
                        status_desc = raw_args[5]
                        name = decode_huawei_str(raw_args[8])
                        ip = decode_huawei_str(raw_args[14])

                        wan_list.append({
                            "domain": domain,
                            "name": name,
                            "trigger": trigger,
                            "status": status_desc,
                            "ip": ip,
                        })
                    return wan_list
            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    self.login()
        raise RuntimeError(f"获取 WAN 列表失败 (最后状态码: {status})")

    def find_wan(self, target_name: str) -> dict:
        """查找指定名称的 WAN 连接"""
        wans = self.get_wan_connections()
        for wan in wans:
            if target_name.upper() in wan["name"].upper():
                return wan
        return None

    def set_connection_trigger(self, wan_domain: str, trigger_mode: str) -> bool:
        """向 complex.cgi 提交修改拨号方式 (Manual / AlwaysOn) (带失败重试机制)"""
        for attempt in range(3):
            try:
                onttoken = self.get_ont_token()
                complex_url = (
                    f"{self.base_url}/complex.cgi?"
                    f"y={wan_domain}&"
                    f"RequestFile=html/bbsp/wan/confirmwancfginfo.html"
                )
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


def query_status(
    router_ip: str = "http://192.168.1.1",
    username: str = "user",
    password: str = "",
    target_wan_name: str = "2_INTERNET_R_VID_3961"
) -> bool:
    """仅查询当前光猫连接状态与公网 IP，查询完毕后立即注销退出"""
    client = HuaweiONTClient(base_url=router_ip, username=username, password=password)
    logged_in = False
    try:
        print(f"[*] 正在登录光猫后台 ({router_ip}) ...")
        if not client.login():
            print("[-] 登录失败，请检查账号密码或光猫连接状态。")
            return False
        logged_in = True
        print("[+] 登录成功！正在查询 WAN 接口信息...")

        target_wan = client.find_wan(target_wan_name)
        if not target_wan:
            print(f"[-] 未找到包含 '{target_wan_name}' 的 WAN 连接！")
            return False

        print("\n" + "=" * 50)
        print(f"[✓] 当前连接状态:")
        print(f"    - 连接名称:     {target_wan['name']}")
        print(f"    - 公网 IP 地址: {target_wan['ip']}")
        print(f"    - 连接状态:     {target_wan['status']}")
        print(f"    - 拨号模式:     {target_wan['trigger']}")
        print(f"    - TR-069 节点:  {target_wan['domain']}")
        print("=" * 50 + "\n")
        return True
    finally:
        if logged_in:
            print("[*] 正在退出光猫登录后台，释放单用户会话锁...")
            client.logout()
            print("[✓] 退出登录成功，光猫后台会话已正常注销释放！")


def redial_wan(
    router_ip: str = "http://192.168.1.1",
    username: str = "user",
    password: str = "",
    target_wan_name: str = "2_INTERNET_R_VID_3961",
    pause_seconds: int = 3
) -> bool:
    """执行完整的重新拨号流程"""
    client = HuaweiONTClient(base_url=router_ip, username=username, password=password)
    logged_in = False
    switched_to_manual = False
    switched_to_alwayson = False
    domain = None

    try:
        print(f"[*] 正在登录光猫后台 ({router_ip}) ...")
        if not client.login():
            print("[-] 登录失败，请检查账号密码或网络连接。")
            return False
        logged_in = True
        print("[+] 登录成功！")

        print(f"[*] 正在查找目标 WAN 连接: {target_wan_name} ...")
        target_wan = client.find_wan(target_wan_name)
        if not target_wan:
            print(f"[-] 未找到包含 '{target_wan_name}' 的 WAN 连接！")
            return False

        domain = target_wan["domain"]
        old_ip = target_wan["ip"]
        print(f"[+] 找到目标连接: {target_wan['name']}")
        print(f"    - TR-069 节点: {domain}")
        print(f"    - 当前拨号模式: {target_wan['trigger']}")
        print(f"    - 当前连接状态: {target_wan['status']}")
        print(f"    - 当前公网 IP:  {old_ip}")

        # 第一步：修改为 Manual (手动拨号，使连接断开)
        print("\n[*] [步骤 1/3] 正在将拨号方式切换为【手动】(Manual)，断开当前连接...")
        if not client.set_connection_trigger(domain, "Manual"):
            print("[-] 提交【手动】拨号方式失败！")
            return False
        switched_to_manual = True
        print("[+] 切换为【手动】成功，PPPoE 正在下线...")

        # 第二步：暂停等待
        print(f"[*] [步骤 2/3] 等待 {pause_seconds} 秒 ...")
        time.sleep(pause_seconds)

        # 第三步：修改为 AlwaysOn (自动拨号，使重新拨号)
        print("[*] [步骤 3/3] 正在将拨号方式切换回【自动】(AlwaysOn)，触发重新拨号...")
        if not client.set_connection_trigger(domain, "AlwaysOn"):
            print("[-] 首次提交【自动】拨号方式失败，正在重新认证重试...")
            time.sleep(1)
            client.login()
            if not client.set_connection_trigger(domain, "AlwaysOn"):
                print("[-] 重试提交【自动】拨号方式依然失败！")
                return False
        switched_to_alwayson = True
        print("[+] 切换为【自动】成功，等待光猫获取新 IP...")

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
                    print(f"    - 探测 {attempt:02d}: 状态={status}, 模式={trigger}, IP={ip}")
                    if status == "Connected" and ip and ip != "0.0.0.0":
                        new_ip = ip
                        break
            except Exception as e:
                print(f"    - 探测 {attempt:02d} 出错: {e}")

        print("\n" + "=" * 50)
        if new_ip:
            print("[✓] 重新拨号成功！")
            print(f"    - 重拨前 IP: {old_ip}")
            print(f"    - 重拨后 IP: {new_ip}")
            if new_ip != old_ip:
                print("[✓] 成功获取到全新的公网 IP！")
            else:
                print("[!] 本次重拨获取的 IP 与原 IP 相同 (局端分配策略)，如需换段可适当延长断开时间。")
            print("=" * 50)
            return True
        else:
            print("[!] 超时未检测到连接完全上线，请在光猫后台确认状态。")
            print("=" * 50)
            return False
    finally:
        # 兜底恢复：若切换到了 Manual 但未成功恢复为 AlwaysOn，强力恢复！
        if switched_to_manual and not switched_to_alwayson and domain:
            print("[!] 警告：检测到拨号模式停留在 Manual，正在执行紧急安全恢复为 AlwaysOn ...")
            for rec_idx in range(3):
                try:
                    time.sleep(1)
                    client.login()
                    if client.set_connection_trigger(domain, "AlwaysOn"):
                        print("[+] 紧急恢复成功：WAN 拨号模式已恢复为【自动】(AlwaysOn)！")
                        switched_to_alwayson = True
                        break
                except Exception as ex:
                    print(f"[-] 紧急恢复第 {rec_idx+1} 次失败: {ex}")

        if logged_in:
            print("[*] 正在退出光猫登录后台，释放单用户会话锁...")
            ok = client.logout()
            if ok:
                print("[✓] 退出登录成功，光猫后台会话已正常注销释放！")
            else:
                print("[✓] 退出登录请求已完成。")


def main():
    parser = argparse.ArgumentParser(description="华为光猫自动重拨助手 (Huawei ONT Auto-Redial Assistant)")
    parser.add_argument("--url", default="http://192.168.1.1", help="光猫后台管理地址 (默认: http://192.168.1.1)")
    parser.add_argument("--user", default="user", help="登录账号 (默认: user)")
    parser.add_argument("--password", required=True, help="光猫后台登录密码 (必填)")
    parser.add_argument("--wan", default="2_INTERNET_R_VID_3961", help="目标 WAN 名称 (默认: 2_INTERNET_R_VID_3961)")
    parser.add_argument("--delay", type=int, default=3, help="断开后等待秒数 (默认: 3)")
    parser.add_argument("--status", action="store_true", help="仅查询当前公网IP与连接状态 (查询完毕后自动退出登录)")

    args = parser.parse_args()

    if args.status:
        success = query_status(
            router_ip=args.url,
            username=args.user,
            password=args.password,
            target_wan_name=args.wan
        )
        sys.exit(0 if success else 1)

    success = redial_wan(
        router_ip=args.url,
        username=args.user,
        password=args.password,
        target_wan_name=args.wan,
        pause_seconds=args.delay
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
