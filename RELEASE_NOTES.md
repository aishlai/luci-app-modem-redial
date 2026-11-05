# Release v1.5.0 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🚀 稳定性与升级通道专项验证版本 (Milestone Release)

1. **版本升级与在线更新链路验证**
   - 本版本为重大里程碑版本，用于全面验证 GitHub Releases 在线自动检测更新、升级悬浮层弹出以及一键下载安装覆盖升级的完整闭环；
   - 验证升级过程中用户配置（`/etc/config/modem_redial`）无损继承与服务无缝热重载机制。

2. **UDP QoS 连通性监测自愈与实时日志机制巩固**
   - 巩固了后台守护进程低功耗自愈待机架构，严格遵循用户自定义的检测周期（如 `15 秒`）周期性轮询与内存覆盖刷新；
   - 巩固了「⚡ 立即探测一轮」直通管道流回显，消除任何因权限缓存导致的回显停滞，实现秒级即时测速看板呈现；
   - 完善系统级 `ucitrack` 联动与守护进程独占 PID 锁生命周期管理。

---

## 🇺🇸 English Changelog

### 🚀 Upgrade Channel & Stability Milestone Release

1. **In-Place Upgrade & Release Verification**
   - Milestone release specifically designated to verify GitHub Releases automatic detection, update modal notification, and one-click seamless package installation.
   - Ensures zero-loss preservation of user configuration (`/etc/config/modem_redial`) and automated hot-reload of services post-upgrade.

2. **Consolidation of UDP QoS Watchdog & Live Telemetry**
   - Solidified the self-healing idle standby architecture for the UDP watchdog, strictly adhering to user-configured probe intervals (e.g., `15 seconds`).
   - Hardened the direct pipeline stream for instant probe results, ensuring immediate interactive display in the live monitoring log.
   - Validated system-level `ucitrack` triggers and PID locking lifecycles.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.0-1_all.ipk
```
