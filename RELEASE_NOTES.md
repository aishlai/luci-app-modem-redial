# Release v1.4.6 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🐛 重点 Bug 修复

1. **彻底修复“立即重新拨号换IP”按钮状态跳闪问题**
   - **问题现象**：点击“立即重新拨号换IP”成功换 IP 后，悬浮层处于 5 秒倒计时准备自动关闭期间，背景中的“立即重新拨号换IP”按钮会在“正在重拨中...”与“立即重拨号换IP”两种状态下来回跳闪，倒计时也会被错误重置；
   - **原因分析**：重拨成功注销光猫后，后端因 Ntfy 10 秒缓冲延时机制仍在后台睡眠，导致状态刷新接口持续返回 `running: True`，前端状态异步回调因此错误拉起新一轮轮询；
   - **解决措施**：
     1. 后端优化：重拨与光猫会话注销完毕的瞬间立即释放 PID 锁文件，确保状态查询立即返回真实的连通状态与新 IP；
     2. 前端优化：加入双重防抖状态锁（`_redialJustFinished` 与 `_autoCloseModalTimer`），倒计时关闭期间坚决拦截任何重复轮询，彻底消灭跳闪现象。

### 🚀 界面与核心功能优化

1. **全新 UI 布局架构升级**
   - **顶部独立状态区**：提炼公网 IP、连接状态、当前拨号模式、目标 WAN 为顶部独立卡片，免去多余标题，紧凑精致；
   - **精简菜单路径**：彻底移除多余的「服务」菜单入口，统一收敛至 **【网络】->【光猫重拨助手】**，更符合 OpenWrt 规范；
   - **全新 4 大功能 Tab**：将底层功能规整为「光猫配置」、「定时重拨」、「监测重拨」、「消息推送」，去除了各 Tab 下方多余的说明文字，界面更加纯粹干练；
   - **操作按钮顺序优化**：按钮依次为 `⚡ 立即重拨号换IP`、`🔄 刷新状态`、`📜 查看日志`、`🚀 检查更新`，一行整齐排列，操作顺手。

2. **日志悬浮模态层智能关闭机制**
   - 点击「立即重拨号换IP」后直接弹起悬浮模态日志层，实时流式滚动输出后台执行进度；
   - **重拨成功**：自动开启 5 秒动态倒计时并自动关闭悬浮窗，主界面状态自动同步刷新；
   - **重拨失败**：坚决不自动关闭，状态栏标红提醒，完整保留错误日志便于快速定位排查原因；
   - 点击「查看日志」仅作浏览，不触发自动关闭。

3. **进入插件静默自动检查更新**
   - 每次进入插件页面，后台自动执行静默版本检测；
   - **已是最新版**：静默不打扰用户；
   - **发现新版本**：自动弹出更新模态悬浮层，展示新版特性并支持一键在线覆盖升级。

4. **Ntfy 消息通知全面支持**
   - 原生集成 [ntfy.sh](https://ntfy.sh) 与自建实例，零第三方依赖；
   - 支持自定义按需订阅事件（手动重拨、定时重拨、QoS 阻断重拨、重拨失败告警）；
   - 消息体全面升级为优雅的纯文本 Markdown 格式排版；
   - 内置 10 秒联网缓冲延时机制，确保通知必达。

5. **配置数据防丢保护**
   - 全局 UCI 选项注入 `retain = true`，关闭插件开关或保存时，所有定时、QoS 监测与 Ntfy 配置数据永久保留，绝不丢失。

---

## 🇺🇸 English Changelog

### 🐛 Bug Fixes

1. **Fixed Redial Button State Flickering**
   - **Issue**: After redial successfully changed the public IP and before the modal auto-closed, the "Immediate Redial" button kept flickering back and forth between "Redialing..." and "Immediate Redial".
   - **Root Cause**: The 10-second post-dial Ntfy stabilization delay kept the process alive, causing background status queries to return `running: True` and repeatedly re-triggering polling timers.
   - **Fix**:
     1. Released PID file immediately once the modem session log-out succeeds, ensuring accurate status responses.
     2. Implemented frontend debounce guards (`_redialJustFinished` and `_autoCloseModalTimer`) to block unintended polling and eliminate UI button state flickering completely.

### 🚀 Key Features & Improvements

1. **Redesigned UI Architecture**
   - **Top Standalone Status Cards**: Compact cards displaying Public IP, Connection Status, Dial Mode, and Target WAN right below the header.
   - **Unified Menu Entry**: Removed the redundant entry under "Services" and unified all navigation under **Network -> Modem Redial Assistant** (`admin/network/modem_redial`).
   - **4 Clean Tabs**: Streamlined tabs ("Modem Config", "Scheduled Redial", "Monitoring Redial", "Notifications") without verbose subtitles for a clean, minimalist layout.
   - **Intuitive Button Layout**: Left-aligned single-row buttons: `Manual Redial`, `Refresh Status`, `View Logs`, `Check Updates`.

2. **Smart Auto-Close Floating Log Modal**
   - Clicking "Immediate Redial" opens an elegant floating modal layer streaming live real-time output.
   - **On Success**: Dynamic 5-second countdown banner (`Closing in X seconds...`) and automatically closes the modal;
   - **On Failure**: Modal remains open with prominent error indicators, preserving full traceback and logs for troubleshooting;
   - Viewing logs via "View Logs" is non-intrusive and never auto-closes.

3. **Silent Background Update Check on View Entry**
   - Automatically checks GitHub Releases whenever you open the plugin page.
   - **Up to date**: Stays completely silent with zero interruptions;
   - **New release detected**: Automatically pops up the upgrade modal with changelog notes and one-click in-place upgrade.

4. **Ntfy Push Notification Integration**
   - Native integration with [ntfy.sh](https://ntfy.sh) and self-hosted instances (zero external Python dependencies).
   - Event-level subscriptions: Manual Redial, Scheduled Redial, UDP QoS Auto-Recovery, and Failure Alerts.
   - Pure Markdown formatting for clean, structured mobile push cards.
   - Built-in 10-second post-dial network stabilization buffer to ensure notification delivery.

5. **UCI Configuration Retention**
   - Config options preserve `retain = true`, ensuring no loss of cron schedules, watchdog settings, or Ntfy configurations when toggling the plugin master switch.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.4.6-1_all.ipk
```
