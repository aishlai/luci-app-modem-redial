# Release v1.4.8 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🛡️ 核心功能增强：实时 UDP 连通性监测日志 (内存零损耗)

1. **新增「实时连通性监测日志」面板**
   - 在「监测重拨」标签页中新增暗色终端风格的实时连通性日志看板；
   - 完整展示当前网络下所有 UDP 检测目标（包括 DNS `53`、STUN `3478`、NTP `123` 等）的实时往返延迟 (RTT)、协议类型与通讯状态；
   - 实时呈现当前失败计数、触发阈值及当前网络是否遭遇运营商 UDP QoS 阻断的综合诊断信息。

2. **每轮检测覆盖刷新，不占用路由器闪存寿命**
   - 实时监测日志严格存储在内存系统临时目录 (`/tmp/log/modem_redial_live_qos.log`) 中；
   - 无论后台守护进程周期轮询，还是手动触发探测，每次均以覆盖模式 (`w`) 仅保留最新单轮探测结果；
   - 彻底避免频繁写盘对路由器内置 Flash 闪存造成磨损，重启后自动清理。

3. **快捷交互与无感自动轮询**
   - 提供「🔄 刷新实时日志」按钮，随时读取后台最新监测报告；
   - 新增「⚡ 立即探测一轮」按钮，一键向所有节点发送实时探测包并即刻刷新日志看板；
   - 页面开启时后台每 5 秒静默同步一次最新数据，当用户选中或交互时智能防打扰。

4. **历史记录与实时探测职责清晰分离**
   - **实时监测日志** (`/tmp/log/modem_redial_live_qos.log`)：纯内存非持久化，仅保留单轮最新指标；
   - **QoS 触发重拨历史日志** (`/etc/modem_redial_qos.log`)：持久化存储在 Flash 中，仅在网络全断流并实际触发光猫重拨时记录归档。

---

## 🇺🇸 English Changelog

### 🛡️ Core Feature: Real-Time UDP QoS Telemetry Log (RAM-only, Zero Flash Wear)

1. **New Real-Time Live Monitoring Log Panel**
   - Added a dark terminal-style live telemetry log box inside the "监测重拨" (Monitoring Redial) tab.
   - Accurately reports bidirectional round-trip latency (RTT), protocol tags (DNS 53, STUN 3478, NTP 123), and connection health for every target node.
   - Provides instant diagnostic insight into failure counters, trigger thresholds, and ISP UDP QoS throttling.

2. **Per-Round Overwrite Refresh, Zero Flash Wear**
   - Strictly resides in volatile memory (`/tmp/log/modem_redial_live_qos.log` on `tmpfs`).
   - Every background probe cycle and manual check overwrites the previous round (`mode="w"`), retaining only the latest single-round telemetry.
   - Eliminates flash disk writes, ensuring complete zero flash degradation.

3. **Instant Controls & Silent Auto-Sync**
   - "🔄 Refresh Live Log" button for instant file reload.
   - "⚡ Probe Round Now" button to execute an immediate probe round across all endpoints and update telemetry on the fly.
   - Silent 5-second polling keeps the live log updated in the background without interrupting text selection or focus.

4. **Clean Separation Between Live Telemetry & Historical Events**
   - **Live Telemetry** (`/tmp/log/modem_redial_live_qos.log`): RAM-only, non-persistent, single-round live metrics.
   - **QoS Trigger History** (`/etc/modem_redial_qos.log`): Persistent on flash, strictly logs actual redial interventions and IP acquisition results.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.4.8-1_all.ipk
```
