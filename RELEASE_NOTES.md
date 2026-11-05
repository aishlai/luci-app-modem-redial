# Release v1.4.9 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🐛 重点修复与后台守护自愈机制

1. **彻底解决 UDP 连通性监测未自动按设定周期运行的问题**
   - **自愈待机架构**：监测守护进程优化为低功耗待机轮询模式。当插件或监测暂时未开启时自动待机，用户在网页端开启或修改检测周期（例如设置为 `15 秒`）并保存后，守护进程无需重启即可在 5 秒内自动唤醒，严格遵循用户设定的周期间隔周期性探测；
   - **双向联动与 ucitrack 注册**：在系统级注册 `ucitrack` 联动与 `init.d reload_service`，确保网页端点击「保存并应用」时无缝触发服务重载；
   - **页面访问智能自启**：进入插件管理页面时自动检测并保底唤醒监测守护进程，彻底杜绝后台进程脱管沉睡。

2. **彻底解决点击「⚡ 立即探测一轮」后日志回显卡死的问题**
   - **解除主开关限制**：单轮连通性测试解除主开关拦截，无论当前插件是否开启，点击即可随时对各目标发起即时网络体检；
   - **JSON 直通管道回显**：探测结束后，后端直接将格式化终端看板文本通过 JSON 管道回传前端，不再依赖脆弱的直接文件读取；
   - **命令行回读兜底**：前端日志更新全面升级为 `/usr/bin/modem_redial --show-live-qos-log` 权限直通调用，彻底解决因 rpcd 权限缓存导致日志框停留在 `>>> 正在向所有目标节点发送 UDP 探测包...` 的卡死假象。

---

## 🇺🇸 English Changelog

### 🐛 Critical Bug Fixes & Watchdog Self-Healing

1. **Resolved Watchdog Failing to Automatically Run at Configured Interval**
   - **Self-Healing Standby Architecture**: Refactored the watchdog daemon to run continuously in an ultra-low-power idle loop when disabled. As soon as the feature is enabled or the interval is updated (e.g., set to `15s`), the watchdog automatically activates within 5 seconds and strictly adheres to the custom period.
   - **ucitrack & init.d Service Integration**: Registered system `ucitrack` triggers and `reload_service` so clicking "Save & Apply" in LuCI reliably reloads configuration in real time.
   - **Fail-Safe View Activation**: Visiting the WebUI automatically verifies and wakes up the background monitoring daemon if needed.

2. **Fixed "⚡ Probe Round Now" Getting Stuck on Progress Text**
   - **Unrestricted Instant Probing**: Manual probe rounds can now be executed anytime without being blocked by the global enable toggle.
   - **Direct JSON Pipe Delivery**: Single-round telemetry reports are directly delivered to the frontend in the JSON response payload, eliminating reliance on raw file read calls.
   - **Robust Command Fallback**: Upgraded polling and log refresh to use `/usr/bin/modem_redial --show-live-qos-log` to bypass rpcd ACL caching issues, ensuring instantaneous display of live probe metrics.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.4.9-1_all.ipk
```
