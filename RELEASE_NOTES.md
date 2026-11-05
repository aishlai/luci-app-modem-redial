# Release v1.5.8 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🛡️ 重拨全流程与 UDP 连通性监测避让保护：彻底消除断网期间误判冲突

1. **重拨开始即刻触发冷却保护（全入口无缝覆盖）**
   - **痛点分析**：光猫在执行重新拨号（无论是由用户在网页后台点击「立即重拨」、定时任务触发、还是 QoS 阻断自动触发）期间，WAN 口网络必定会经历数十秒的暂时断网。旧版本中 UDP 监测守护进程若在此期间继续发包，会导致探测包全部丢包超时，累加失败计数并导致日志红字报错，甚至产生误判死循环；
   - **毫秒级即时冷却锁定**：在 `/usr/bin/modem_redial` 启动脚本、Python CLI `--start` 及 `redial_wan` 入口处，只要重拨一旦启动，毫秒级在 `/tmp/run/modem_redial_cooldown.time` 写入冷却保护时间戳（严格采用用户配置的 `udp_cooldown` 时长，默认 180 秒）；
   - **失败计数即刻归零**：检测到重拨运行或处于冷却期时，后台守护进程将连续失败计数器 `consecutive_fails` 强制清零，杜绝任何误触二次重拨的可能。

2. **守护进程 1 秒细粒度切片感知与动态倒计时**
   - **切片中断响应**：监测主循环在等待检测周期间采用 1 秒细粒度切片检测，一旦外部触发重拨，监测进程在 1 秒内即可精准感知并退出休眠，立即转入避让状态，绝不滞后发包；
   - **实时黑框友好呈现**：在重拨及后续冷却保护期内，实时监测日志黑框状态自动标示为 `⏸️ 避让`，状态栏动态更新倒计时：`重拨冷却缓冲中 (剩余 X 秒)...`，日志内容干净规整；
   - **冷却结束后无缝恢复**：冷却时间完全走完后，后台守护进程自动且无缝地恢复正常的 UDP 连通性监测。

3. **LuCI 网页手动探测智能互斥保护**
   - 当光猫正在重拨或处于冷却期时，若用户在网页端点击「⚡ 立即探测一轮」或「📊 详细体检弹窗」，插件底层将主动拦截探测请求，返回友好的避让提示并保持日志整洁，不再盲目向断开的网络发送无意义的探测包。

---

## 🇺🇸 English Changelog

### 🛡️ Redial & UDP Watchdog Avoidance System: Eliminated Monitoring Conflicts During Disconnection

1. **Instant Cooldown Activation Across All Triggers**
   - **Problem**: When the modem redials (via LuCI Web UI "Redial Now", scheduled cron, or QoS watchdog trigger), the WAN link drops temporarily. Probing UDP targets during this outage caused packet loss, inflated consecutive failure counts, and produced false alarm log errors.
   - **Sub-millisecond Lock**: Redial execution instantly registers an avoidance timestamp into `/tmp/run/modem_redial_cooldown.time` based on the configured `udp_cooldown` setting (default 180s).
   - **Zeroed Failure Counters**: While redialing or in cooldown, consecutive failure counters are strictly reset to 0 to prevent accidental recursive triggers.

2. **1-Second Sliced Sensing & Dynamic Live Countdown**
   - **Instant Interruption**: The watchdog polling interval uses 1-second sleep slicing. As soon as a redial is initiated, the watchdog interrupts its sleep within 1s and engages avoidance protection.
   - **Clear Live Status Display**: Targets in the live log box are rendered with `⏸️ 避让` (Avoidance) status, accompanied by a dynamic countdown `重拨冷却缓冲中 (剩余 X 秒)...`.
   - **Seamless Resumption**: Normal connectivity checks resume automatically once the cooldown buffer completely elapses.

3. **Intelligent UI Probe Interception**
   - Clicking "Single Probe" or "Diagnostics Modal" in the LuCI UI while a redial or cooldown is active is cleanly intercepted with an informative alert, preventing probe attempts against a disconnected link.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.8` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.8-1_all.ipk
```
