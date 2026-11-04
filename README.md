# luci-app-modem-redial (光猫重拨助手)

<p align="center">
  <img src="https://img.shields.io/badge/OpenWrt-24.10%20%7C%2023.05%20%7C%2022.03-blue?style=flat-square&logo=openwrt" alt="OpenWrt Support">
  <img src="https://img.shields.io/badge/iStoreOS-Supported-brightgreen?style=flat-square" alt="iStoreOS">
  <img src="https://img.shields.io/badge/Architecture-all-orange?style=flat-square" alt="Arch all">
  <img src="https://img.shields.io/badge/Python-3.x%20(Pure%20Stdlib)-blue?style=flat-square&logo=python" alt="Python 3">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License MIT">
  <a href="https://github.com/aishlai/luci-app-modem-redial/actions"><img src="https://img.shields.io/github/actions/workflow/status/aishlai/luci-app-modem-redial/release.yml?style=flat-square&logo=github&label=Build%20IPK" alt="Build Status"></a>
  <a href="https://github.com/aishlai/luci-app-modem-redial/releases"><img src="https://img.shields.io/github/v/release/aishlai/luci-app-modem-redial?style=flat-square&color=blueviolet" alt="GitHub Release"></a>
</p>

专为**北京联通版本华为光猫 V271-20** 打造的 OpenWrt / iStoreOS 路由控制插件与自动化脚本。通过智能控制光猫后台切换拨号方式，实现**秒级自动化重新拨号换 IP**，一键摆脱运营商恶意的 **UDP QoS 丢包、限速与网络阻断**！

---

## 📖 痛点背景与诞生原因

### 1. 强制光猫拨号与旁路由困局
以**北京联通**为代表的很多省市运营商，目前收紧了普通宽带改桥接的权限，默认甚至强制要求光猫负责 PPPoE 路由拨号。在这种环境下，家庭网络玩家与极客用户通常只能将 OpenWrt / iStoreOS 设备配置为**旁路由（旁路网关）**，用于承载科学上网分流、游戏加速、音视频流媒体优化等业务。

### 2. 运营商严苛的 UDP QoS 惩罚机制
当旁路由或内网设备产生大流量、高并发或未知长连接的 UDP 流量（例如国外代理协议、QUIC / HTTP3 传输、海外游戏对战联机、音视频实时通话会议等）时，极易被运营商骨干网 DPI 流控检测命中，随后对**当前公网 IP 实施严苛的基于 UDP 的 QoS 限速甚至阻断**：
- 🎮 **网游联机**：Steam、CS2、Apex、主机游戏等疯狂丢包，延迟从 30ms 暴增至 300ms+，甚至频频掉线断开连接；
- 📞 **音视频会议与通话**：微信音视频通话画面卡死、声音断续断流，飞书/腾讯会议/Zoom 频繁重连；
- 📹 **网络直播与视频**：OBS 推流断流、抖音/B站推流丢帧、QUIC 网页视频疯狂加载缓冲。

### 3. 为什么换 IP 是唯一的“神药”？
运营商的这类 UDP QoS 策略是**直接绑定在当前分配的公网 IP** 上的。经过大量实测验证，**只要光猫重新拨号获取到一个全新的公网 IP，该 IP 上的 UDP QoS 限制就会立即解除，所有 UDP 流量瞬间满血复活！**

### 4. 华为光猫的手动重拨痛点
华为光猫的 Web 后台**并没有提供直接的“断开/重拨”按钮**，用户遇到阻断时，必须手动经历以下繁琐步骤：
1. 打开浏览器登录光猫管理页；
2. 找到 WAN 配置，将连接模式由 `AlwaysOn`（自动拨号）修改为 `Manual`（手动拨号）并保存，强行让 PPPoE 下线；
3. 人工等待数秒后，再修改回 `AlwaysOn` 触发重新拨号；
4. 光猫限制单账号同时在线，操作完如果不及时退出登录，还会锁死后台管理权限。

### 5. 本插件的解决之道
**`luci-app-modem-redial (光猫重拨助手)`** 让这一过程变得极致简单！直接在你的 OpenWrt / iStoreOS 路由器后台，轻点一下按钮，后台全自动在 20 秒内完成登录、切手动断网、等待延时、切自动重拨、验证新公网 IP、退出登录释放会话锁的全套动作。**无需改动光猫，无需进光猫后台，一键解限！**

---

## ✨ 核心特性

- ⚡ **秒级一键重拨**：WebUI 界面一键触发，自动完成 Manual 切换与 AlwaysOn 恢复，20 秒获取新 IP。
- 📊 **实时日志流式回显**：前台逐秒滚动回显重拨进度，重拨前后 IP 对比、成功状态清晰可见。
- 🕒 **Crontab 定时自动换 IP**：支持标准 5 位 Cron 表达式（如每天凌晨 4 点静默重拨 `0 4 * * *`），保持 IP 始终洁净。
- 🛡️ **单用户会话锁安全释放**：执行结束或发生异常时，强制注销会话并清理 Cookie，绝不占用光猫单用户锁。
- 🔄 **紧急安全回滚机制**：若网络发生波动或断网，脚本内置 3 次重试与安全兜底逻辑，强制回滚 AlwaysOn，杜绝光猫卡在断网状态。
- 🚀 **100% 纯标准库与无依赖**：底层引擎采用 Python 3 原生标准库（`urllib` + `http.cookiejar`），**不需要**安装庞大的 `requests` 库；前端采用 OpenWrt 24.10 / iStoreOS 官方规范的纯 JavaScript 视图（全架构通用）。
- 💻 **附带独立 CLI 脚本**：仓库内提供免 LuCI 依赖的独立 Python 脚本 [`redial_v271_20.py`](redial_v271_20.py)，支持在 Linux / macOS / Windows / Docker 容器或无界面的路由器上直接运行。

---

## 📱 验证机型说明

> [!IMPORTANT]
> **本插件仅在「北京联通版本 华为 V271-20」光猫上进行了实际测试与功能验证。**  
> 其他地区或其他光猫型号暂未进行测试，请以实际设备为准。

---

## 📦 安装方法

### 方式一：从 GitHub Releases 下载预编译 IPK（最推荐）

1. 进入 [Releases 页面](https://github.com/aishlai/luci-app-modem-redial/releases) 下载最新版的 `luci-app-modem-redial_x.x.x_all.ipk`；
2. **iStoreOS 用户**：可以直接在 iStore 应用商店中点击【手动安装】，上传该 `.ipk` 文件一键完成安装；
3. **原生 OpenWrt 用户**：通过 SCP 上传至路由器 `/tmp` 目录，通过 SSH 安装：
   ```bash
   opkg update
   opkg install python3
   opkg install /tmp/luci-app-modem-redial_*_all.ipk
   ```
4. 安装完成后，刷新路由器后台网页（建议按 `Ctrl + F5` 强制刷新浏览器缓存），即可在 **【网络】** 或 **【服务】** 菜单中看到 **【光猫重拨助手】**。

---

### 方式二：终端命令行一键在线下载安装

在路由器 SSH 终端中直接运行以下命令（自动从 GitHub 获取最新 Release 并安装）：

```bash
# 安装 python3 依赖
opkg update && opkg install python3

# 下载并安装最新版 IPK
LATEST_URL=$(curl -s https://api.github.com/repos/aishlai/luci-app-modem-redial/releases/latest | grep "browser_download_url.*_all.ipk" | head -n 1 | cut -d '"' -f 4)
wget -O /tmp/luci-app-modem-redial_latest.ipk "$LATEST_URL"
opkg install --force-reinstall /tmp/luci-app-modem-redial_latest.ipk
rm -f /tmp/luci-app-modem-redial_latest.ipk
```

---

### 方式三：源码集成编译（适用于固件编译者）

```bash
cd package/
git clone https://github.com/aishlai/luci-app-modem-redial.git
make menuconfig
# 在 LuCI -> Applications 中选中 luci-app-modem-redial
make package/luci-app-modem-redial/compile V=s
```

---

## ⚙️ 界面参数配置说明

进入 OpenWrt 后台菜单 **【网络】->【光猫重拨助手】**（或 **【服务】->【光猫重拨助手】**）：

| 配置项 | 推荐值 / 示例 | 说明 |
| :--- | :--- | :--- |
| **启用插件** | 勾选（开） | 插件主控制开关 |
| **光猫后台地址** | `http://192.168.1.1` | 光猫的管理 Web 地址（若修改过光猫 IP 请按实际填写，如 `http://192.168.50.1`） |
| **登录用户名** | `user` | 光猫普通用户账号（无需超级密码，背标普通用户即可） |
| **登录密码** | 光猫背标默认密码 | 光猫背标贴纸上的初始管理密码，或你修改后的密码 |
| **目标 WAN 连接名称** | `2_INTERNET_R_VID_3961` | 光猫中负责 Internet 上网的 WAN 名称（见下方获取方法） |
| **断开等待时间 (秒)** | `3` | 切换为 Manual 后等待 PPPoE 彻底下线的停顿时间，默认 3 秒 |
| **启用定时自动重拨** | 可选（开/关） | 开启后将在指定时间自动执行静默重拨换 IP |
| **Cron 表达式** | `0 4 * * *` | 标准 Linux Crontab 表达式，默认每天凌晨 4 点重拨 |

### 🔍 如何确认我的“目标 WAN 连接名称”？
1. 电脑浏览器打开光猫管理地址，用背标账号密码登录；
2. 点击顶部【网络】->【WAN 配置】；
3. 查看列表中类型包含 `INTERNET`（路由模式 PPPoE）的连接名称，例如常见的：
   - `2_INTERNET_R_VID_3961`（北京联通典型值）
   - `1_INTERNET_R_VID_xxxx`
4. 将该字符串复制填入插件配置中即可。

---

## 💻 独立 Python 脚本使用指南

如果你不想安装 LuCI 插件，或者希望在群晖 NAS、PVE 宿主机、Docker 容器中通过定时任务调用，可以直接使用独立脚本 [`redial_v271_20.py`](redial_v271_20.py)。

### 方式 A：直接在脚本顶部填写配置（最简便）
用任意文本编辑器打开 `redial_v271_20.py`，在开头的 **【用户配置区】** 填入你的光猫管理信息：
```python
MODEM_URL = "http://192.168.1.1"   # 你的光猫管理后台地址
PASSWORD  = "你的光猫密码"          # 光猫背标贴纸上的管理密码
```
保存后，无需输入长串参数，直接双击或运行即可：
```bash
python3 redial_v271_20.py
```
> 若未填写任何配置直接运行，脚本会友好地打印出使用指南与参数提示，绝不会静默闪退或报错。

### 方式 B：通过命令行参数直接运行
也可以不修改脚本，直接通过命令行传参调用：

#### 1. 查询当前公网 IP 与光猫状态
```bash
python3 redial_v271_20.py --url http://192.168.1.1 --user user --password "你的光猫密码" --status
```

#### 2. 立即触发重新拨号换 IP
```bash
python3 redial_v271_20.py --url http://192.168.1.1 --user user --password "你的光猫密码" --wan 2_INTERNET_R_VID_3961 --delay 3
```

输出示例：
```
[*] 正在登录光猫后台 (http://192.168.1.1) ...
[+] 登录成功！
[*] 正在查找目标 WAN 连接: 2_INTERNET_R_VID_3961 ...
[+] 找到目标连接: 2_INTERNET_R_VID_3961 (当前IP: 114.254.34.62, 模式: AlwaysOn)
[*] [步骤 1/3] 正在将拨号方式切换为【手动】(Manual)，断开当前连接...
[+] 切换为【手动】成功，PPPoE 正在下线...
[*] [步骤 2/3] 等待 3 秒 ...
[*] [步骤 3/3] 正在将拨号方式切换回【自动】(AlwaysOn)，触发重新拨号...
[+] 切换为【自动】成功，等待光猫获取新 IP...
    - 探测 01: 状态=Connected, 模式=AlwaysOn, IP=114.254.37.208
------------------------------------------------------------
[✓] 重新拨号成功！
    - 重拨前 IP: 114.254.34.62
    - 重拨后 IP: 114.254.37.208
[✓] 成功获取到全新的公网 IP！
============================================================
[*] 正在退出光猫登录后台，释放单用户会话锁...
[✓] 退出登录成功，光猫后台会话已正常注销释放！
```

---

## 🚀 编译打包与 GitHub Actions 自动发版

### 1. 本地打包构建

项目根目录提供了官方规范打包脚本 `build_ipk.sh`，版本号统一与 Git Tag 对齐：

```bash
# 自动读取当前 Git Tag 打包 (例如当前 Tag 为 v1.0.5，则生成 luci-app-modem-redial_1.0.5-1_all.ipk)
bash ./build_ipk.sh

# 也支持直接传入指定版本号打包
bash ./build_ipk.sh v1.0.5
```

### 2. GitHub Actions 自动编译与发版

本项目已内置完整的 GitHub Actions 自动化工作流 [`.github/workflows/release.yml`](.github/workflows/release.yml)：

1. **自动构建与验证**：任何代码 Push 到 `main` 分支时，Actions 会自动构建 `.ipk` 并输出构建产物 Artifacts 与 SHA256 校验和。
2. **统一基于 Git Tag 一键发版**：只需在本地打 Tag 并推送至 GitHub：
   ```bash
   git tag v1.0.5
   git push origin v1.0.5
   ```
   GitHub Actions 检测到 Tag 推送后，会自动将 Tag 版本（如 `v1.0.5`）解析为符合 OpenWrt 规范的包版本（如 `1.0.5-1`），打包并将编译好的 `luci-app-modem-redial_1.0.5-1_all.ipk` 自动发布到 GitHub Releases 供下载！

---

## 🛣️ 路线图 (Roadmap)

- [x] 原生 OpenWrt 24.10 / iStoreOS 纯 JS 视图规范重构；
- [x] 进程双 fork 守护化与 0.16s 异步极速响应；
- [x] 单用户锁自动清理与防锁死兜底；
- [x] 统一遵循 Git Tag 的版本号管理与 GitHub Actions 自动打包发布；
- [ ] **UDP 阻断智能探测与自动重拨机制**（计划中）：
  - 后台守护线程周期性探测特定高敏 UDP 目标（如游戏服务器、DNS over UDP 等）；
  - 自动统计近期 UDP 丢包率与连通性；
  - 一旦判定触发运营商 UDP QoS 阻断，自动发起重拨换 IP 并通知用户，真正做到**零感知无人值守解限**！

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 与 Pull Request！
