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
- 📑 **清晰优雅的 Tab 分页与悬浮日志浮层**：采用 OpenWrt 规范标准的 5 大 Tab 标签页架构（光猫状态、参数配置、定时重拨、监测重拨、消息通知）；触发重拨或查看日志时弹出优雅的悬浮模态层（Modal），实时流式展示执行日志，支持一键清空与关闭，页面整洁清爽。
- 📊 **实时日志流式回显**：前台逐秒滚动回显重拨进度，重拨前后 IP 对比、成功状态清晰可见。
- 🕒 **Crontab 定时自动换 IP**：支持标准 5 位 Cron 表达式（如每天凌晨 4 点静默重拨 `0 4 * * *`），保持 IP 始终洁净。
- 🛡️ **单用户会话锁安全释放**：执行结束或发生异常时，强制注销会话并清理 Cookie，绝不占用光猫单用户锁。
- 🔄 **紧急安全回滚机制**：若网络发生波动或断网，脚本内置 3 次重试与安全兜底逻辑，强制回滚 AlwaysOn，杜绝光猫卡在断网状态。
- 🚀 **100% 纯标准库与无依赖**：底层引擎采用 Python 3 原生标准库（`urllib` + `http.cookiejar`），**不需要**安装庞大的 `requests` 库；前端采用 OpenWrt 24.10 / iStoreOS 官方规范的纯 JavaScript 视图（全架构通用）。
- 📡 **UDP QoS 智能监测与自动换 IP**：后台守护进程周期性探测高敏 UDP 目标（涵盖 DNS 53、STUN 3478、NTP 123 等协议），连续检测全部不通判定遭遇运营商 QoS 阻断时，全自动触发重拨换 IP，配合持久化日志留痕，实现真正无人值守解限。
- 🔔 **Ntfy 实时消息推送通知**：原生支持集成 ntfy.sh 或自建 ntfy 实例，支持用户自定义订阅接收事件（手动重拨、定时重拨、UDP QoS 阻断恢复、重拨失败告警），重拨换 IP 状态秒级推送到手机或电脑桌面。
- 🔄 **在线版本检测与一键升级**：集成 GitHub Releases 官方版本对比，支持国内高速镜像加速下载，Web 界面一键检测新版并静默覆盖升级。
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

## ⚙️ 界面功能与 Tab 标签页说明

进入 OpenWrt 后台菜单 **【网络】->【光猫重拨助手】**（或 **【服务】->【光猫重拨助手】**）：

插件采用清晰整洁的 **Tab 分页架构**，功能模块一目了然：

### 1. 📊 光猫状态 (Tab)
- **状态卡片**：实时展示当前公网 IP、PPPoE 连接状态、当前拨号模式、目标 WAN 连接名称；
- **⚡ 立即重拨换IP**：点击后弹出悬浮模态日志层，即时呈现 Manual 切换与 AlwaysOn 重新拨号完整流程；
- **🔄 刷新状态**：异步读取光猫后台最新网络状态与获取到的新 IP；
- **📜 查看日志**：弹窗展示当前系统的实时执行日志，提供 **【🗑️ 清空日志】** 与 **【关闭】** 功能；
- **🚀 检查更新**：在线检测 GitHub 最新版本并支持一键升级。

### 2. ⚙️ 参数配置 (Tab)
| 配置项 | 推荐值 / 示例 | 说明 |
| :--- | :--- | :--- |
| **启用插件** | 勾选（开） | 插件全局总开关。开启后恢复运行状态面板、定时自动重拨、UDP QoS 监测与 Ntfy 消息通知；关闭时所有功能联动停用并隐藏。 |
| **光猫后台地址** | `http://192.168.1.1` | 光猫的管理 Web 地址（若修改过光猫 IP 请按实际填写，如 `http://192.168.50.1`） |
| **登录用户名** | `user` | 光猫普通用户账号（无需超级密码，背标普通用户即可） |
| **登录密码** | 光猫背标默认密码 | 光猫背标贴纸上的初始管理密码，或你修改后的密码 |
| **目标 WAN 连接名称** | `2_INTERNET_R_VID_3961` | 光猫中负责 Internet 上网的 WAN 名称（见下方获取方法） |
| **断开等待时间 (秒)** | `3` | 切换为 Manual 后等待 PPPoE 彻底下线的停顿时间，默认 3 秒 |

### 3. ⏰ 定时重拨 (Tab)
| 配置项 | 推荐值 / 示例 | 说明 |
| :--- | :--- | :--- |
| **启用定时自动重拨** | 可选（开/关） | 开启后将在指定时间自动执行静默重拨换 IP |
| **Cron 表达式** | `0 4 * * *` | 标准 Linux Crontab 表达式，默认每天凌晨 4 点重拨（例如：`0 */6 * * *` 为每6小时换一次 IP） |

### 4. 🛡️ 监测重拨 (Tab)
| 配置项 | 推荐值 / 示例 | 说明 |
| :--- | :--- | :--- |
| **启用 UDP 连通性监测** | 可选（开/关） | 开启后常驻后台守护探测 UDP 连通性，全不通时自动重拨换 IP |
| **探测周期间隔 (秒)** | `60` | 后台每次探测的间隔时间，默认 60 秒 |
| **连续判定阈值 (次)** | `2` | 连续检测全部失败达到该次数才触发重拨，防偶发网络抖动误判 |
| **重拨冷却时间 (秒)** | `180` | 触发重拨成功后的冷却保护期，冷却期内不重复触发 |
| **UDP 检测目标列表** | 阿里云/腾讯DNS/STUN/NTP | 支持自定义 IP/域名:端口，任意一个通畅即视为正常 |
| **连通性测试** | 按钮交互 | 即时并发向各目标发送双向 UDP 探测包并弹窗回显结果与延迟 |
| **QoS 独立持久化日志路径** | `/etc/modem_redial_qos.log` | 记录因 UDP QoS 阻断而触发的重拨日志，保存在 `/etc/` 重启不丢失，下方内嵌日志浏览与清空功能 |

### 5. 🔔 消息通知 (Tab)
| 配置项 | 推荐值 / 示例 | 说明 |
| :--- | :--- | :--- |
| **启用 Ntfy 通知** | 可选（开/关） | 开启后支持向手机/电脑推送重拨与告警消息 |
| **Ntfy 服务器地址** | `https://ntfy.sh` | 默认为官方公共服务器，支持自建实例 |
| **Topic 主题名称** | 自定义字符串 | 消息接收主题（建议使用不易被猜测的名称，如 `my_modem_xxx`） |
| **访问令牌 Token** | 可选（留空） | 保护主题或自建服务器所需的 Bearer Access Token |
| **自定义接收事件** | 四项独立开关 | 支持分别勾选：手动重拨通知、定时重拨通知、QoS 阻断换 IP 通知、重拨失败告警 |
| **测试通知** | 按钮交互 | 点击向目标 Topic 发送一条纯文本 Markdown 测试消息，验证通道是否畅通 |

### 🔍 如何确认我的“目标 WAN 连接名称”？
1. 电脑浏览器打开光猫管理地址，用背标账号密码登录；
2. 点击顶部【网络】->【WAN 配置】；
3. 查看列表中类型包含 `INTERNET`（路由模式 PPPoE）的连接名称，例如常见的：
   - `2_INTERNET_R_VID_3961`（北京联通典型值）
   - `1_INTERNET_R_VID_xxxx`
4. 将该字符串复制填入插件配置中即可。

---

## 🔔 Ntfy 实时消息推送通知指南

插件原生集成了 [ntfy.sh](https://ntfy.sh) 实时消息推送支持，底层基于 Python 纯标准库实现，**无需安装任何额外第三方依赖**。当发生重拨换 IP、遭遇运营商 UDP QoS 阻断恢复或发生重拨异常时，均可秒级向手机（iOS / Android）或电脑桌面推送提醒。

> [!TIP]
> **网络稳定缓冲机制**：重拨换 IP 完成后，插件会自动加入 10 秒缓冲延时，等待网络链路与 DNS 解析彻底稳定后再发出 Ntfy 消息，并在发送遇到网络波动时内置重试，确保通知必达。

### 1. 快速使用步骤

1. **手机端订阅主题**：
   - 在手机应用商店下载安装 **ntfy** App（支持 iOS / Android，亦可在电脑浏览器直接访问 [ntfy.sh](https://ntfy.sh) 网页版）；
   - 在客户端中点击添加订阅，设置一个属于您的专属主题（例如 `my_modem_2026_xyz`，建议使用不易被猜测的长随机字符以防他人误订阅）。
2. **在路由器后台配置**：
   - 进入【网络】或【服务】->【光猫重拨助手】；
   - 勾选 **【启用 Ntfy 通知】**；
   - **Ntfy 服务器地址**：保持默认 `https://ntfy.sh` 即可；若自建了 ntfy 实例，请填写您的完整服务器 URL；
   - **Topic 主题名称**：填写第 1 步中设置的主题名称；
   - **访问令牌 Token**：若为公开主题直接留空；若自建服务或主题开启了写保护，填写对应的 Bearer Token；
   - 点击页面右下角 **【保存并应用】**。
3. **即时测试验证**：
   - 点击配置区下方的 **【🔔 发送测试通知】** 按钮；
   - 您的手机将在 1 秒内收到一条测试推送，验证通道完全畅通。

---

### 2. 自定义通知事件（按需订阅，免受打扰）

用户可根据个人偏好自由定义哪些事件需要接收通知，避免频繁通知造成打扰：

| 事件开关 | 默认状态 | 触发说明与推送内容 |
| :--- | :--- | :--- |
| **手动重拨完成时通知** | 开启 | 在 Web 界面点击「立即重拨换IP」或手动执行重拨成功后，推送重拨耗时与新公网 IP。 |
| **定时自动重拨完成时通知** | 开启 | 凌晨 Crontab 定时自动换 IP 成功后推送。若夜间不想手机亮屏打扰，**可单独取消此项勾选**。 |
| **UDP QoS 阻断换 IP 通知** | 开启 | 当检测到连续 UDP 丢包阻断触发光猫重拨恢复后，推送解限警报与新公网 IP。 |
| **重拨失败告警通知** | 开启 | 无论手动、定时还是 QoS 触发，只要发生异常或重拨失败，立即以**最高优先级 (Urgent)** 发送强提醒告警。 |

---

### 3. 推送消息展示样例

```markdown
### 🚨 UDP QoS 阻断已解除并换新 IP
> **检测到运营商 UDP QoS 阻断，已自动重新拨号换 IP 恢复！**

- **触发原因**: 连续 2 次探测所有 UDP 目标均不可达 (223.5.5.5:53, ...)
- **重拨耗时**: `19 秒`
- **重拨前 IP**: `114.248.10.12`
- **重拨后 IP**: `114.248.33.95` *(已更换)*
- **发生时间**: 2026-11-05 02:15:30
```

```markdown
### 🕒 光猫定时重拨换 IP 完成
> **计划任务定时重拨换 IP 成功！**

- **目标接口**: `2_INTERNET_R_VID_3961`
- **重拨耗时**: `18 秒`
- **重拨前 IP**: `114.248.33.95`
- **重拨后 IP**: `114.248.45.108` *(已更换)*
- **发生时间**: 2026-11-05 04:00:18
```

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
- [x] **UDP 阻断智能探测与自动重拨机制**：
  - 后台守护进程周期性并发探测高敏 UDP 目标（DNS 53、STUN 3478、NTP 123 等）；
  - 连续失败阈值防误判机制与多目标快速熔断判定；
  - 判定触发运营商 UDP QoS 阻断时自动发起光猫重拨换 IP 并进入冷却保护；
  - 配备专属持久化日志记录重拨触发记录，重启不丢失，真正做到**零感知无人值守解限**！
- [x] **Ntfy 实时消息推送通知支持**：
  - 原生标准库零依赖集成，支持官方公共节点与自建 ntfy 实例（含 Token 鉴权）；
  - 支持用户自定义事件过滤订阅（手动重拨/定时重拨/QoS 解限/失败告警）；
  - Web 界面提供一键「发送测试通知」即时交互验证。
- [x] **全局总开关与全功能启停联动**：
  - 插件主开关全局统一调度，关闭时自动停用并隐藏运行状态、操作面板、定时自动重拨、UDP QoS 监测与 Ntfy 消息通知；
  - 开启时动态恢复所有子功能及原有配置项，支持平滑一键启停。
- [x] **Tab 分页架构与模态悬浮日志层**：
  - 全面采用 OpenWrt 官方 5 大 Tab 布局（光猫状态、参数配置、定时重拨、监测重拨、消息通知）；
  - 立即重拨与查看日志升级为悬浮模态弹窗（Modal），支持动态流式进度回显、一键清空日志与随时关闭，主页面整洁无干扰。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 与 Pull Request！
