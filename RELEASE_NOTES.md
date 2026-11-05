# Release v1.6.0 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### ⚡ 页面加载极速突破：彻底解决进入卡顿与 ubus 批处理阻塞

1. **彻底解耦 `--start-watchdog`，根除 ubus 批处理卡死（解决用户捕获的阻塞点）**
   - **痛点定位**：此前在 `render()` 同步流程中调用了 `fs.exec('/usr/bin/modem_redial', ['--start-watchdog'])`。由于 LuCI 底层的 JSON-RPC 自动合并机制，该命令与 `session access`、`uci get modem_redial`、`uci changes` 被合并打包到了**同一个 ubus 请求体**中（即用户网络面板抓取到的 `--data-raw '[{"id":7,...,"file","exec",{"command":"...","params":["--start-watchdog"]}},{"id":8,...},{"id":9,...,"uci","get",...}]'`）。服务端 `rpcd` 必须等待子进程执行完毕后才返回 `uci get`，导致首屏数据迟迟无法返回，界面严重卡死 2~3 秒；
   - **完全异步解耦**：将守护进程保底拉起放入独立的 `setTimeout(..., 2000)` 后台执行，完全脱离首屏渲染上下文，首屏 `uci get` 批处理耗时瞬间缩短至 10 毫秒以内。

2. **视图 `load()` 路由阶段彻底纯内存化（耗时从 3 秒降至 2 毫秒）**
   - **移除阻塞级 `--status`**：旧版本在 `load()` 中同步等待 Python 登录光猫查询状态，阻塞了 LuCI 路由切换；现改为直接读取 `/tmp/log/modem_redial_status_cache.json` 内存文件，`load()` 执行时间从 3 秒骤降至 2 毫秒；
   - **进入即刻秒开**：页面秒级瞬间展示，首屏渲染完成后延时 100 毫秒在后台无感刷新最新光猫状态，彻底拥有与 OpenWrt 原生页面一致的丝滑秒开体验。

3. **关于 `android-icon-144x144.png` 404 的诊断说明**
   - 经排查，该 404 请求是浏览器（Chrome/Edge）检测 OpenWrt / iStoreOS 当前主题的 Web App Manifest 时发起的 PWA 图标请求，由路由器当前主题模板触发；
   - 该图标请求耗时极短且浏览器不会阻断页面渲染，此前真正卡死页面的是上述 `--start-watchdog` 挤占了 `uci.get` 批处理管线。本次更新已彻底铲除真正的卡死元凶！

---

## 🇺🇸 English Changelog

### ⚡ Blazing Fast Page Load: Decoupled Watchdog Launch from Ubus UCI Batching

1. **Decoupled `--start-watchdog` from Ubus Batch Pipeline**
   - **Root Cause**: Synchronous invocation of `fs.exec('--start-watchdog')` inside `render()` caused LuCI to bundle it into the identical JSON-RPC batch payload alongside `session access` and `uci get modem_redial`. The server blocked returning UCI configuration data until the command finished.
   - **Asynchronous Execution**: Deferred watchdog startup check to a detached `setTimeout(..., 2000)` background call, letting `uci get` resolve in under 10ms.

2. **Sub-2ms Lightweight `view.load()` Phase**
   - Replaced the blocking `--status` ONT login query in `load()` with instant RAM cache reading (`/tmp/log/modem_redial_status_cache.json`).
   - Page renders instantly with zero latency, triggering background status refreshes 100ms later.

3. **Analysis of `android-icon-144x144.png` 404**
   - Verified that this 404 is a standard PWA manifest icon probe from the browser directed at the router's current theme, which does not block UI rendering. The actual bottleneck was the blocked ubus batch call, which is now completely resolved.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.6.0` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.6.0-1_all.ipk
```
