# Release v1.5.1 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🐛 重点修复：升级过程「XHR request timed out」彻底根治

1. **一键升级全链路异步守护化重构**
   - **痛点分析**：旧版本执行一键在线升级时，前端以阻塞同步方式等待 `opkg install` 完成；由于安装过程中网络镜像耗时以及系统重载服务可能打断会话，导致前端在 30 秒后抛出 `❌ XHR request timed out` 报错（尽管底层实际已升级成功）；
   - **异步守护架构**：前端触发升级后，后端通过独立守护进程（Daemonized Task）毫秒级立即响应并转入后台运行，彻底切断与网页 XHR 会话的物理阻塞；
   - **实时进度轮询呈现**：前端升级弹窗新增动态进度条与多阶段状态轮询反馈（`20% 准备安装包` -> `45% 高速镜像下载` -> `80% 覆盖安装与配置保护` -> `100% 升级成功`），全面杜绝超时报错假象；
   - **清理 postinst 会话打断**：移除了安装包 postinst 过程中的全局会话重载，避免打断当前浏览器与 rpcd 的正常通讯。

---

## 🇺🇸 English Changelog

### 🐛 Critical Bug Fix: Eliminated "XHR request timed out" During Upgrade

1. **Fully Asynchronous & Daemonized Upgrade Pipeline**
   - **Root Cause**: Previously, in-place upgrades waited synchronously for `opkg install` to terminate. Download latency from upstream mirrors and service reloads occasionally caused HTTP connections to drop or exceed LuCI's 30-second XHR limit, resulting in a false `❌ XHR request timed out` error even though the installation succeeded.
   - **Detached Daemon Pipeline**: The upgrade process is now launched asynchronously in an isolated background daemon via `--start-update`, returning immediately to the caller in milliseconds.
   - **Live Progress Polling & UI Progress Bar**: The upgrade modal now displays a smooth, multi-stage progress bar and telemetry updates (`20% Initializing` -> `45% Downloading` -> `80% Installing & Protecting Config` -> `100% Complete`), eliminating all XHR timeout false alarms.
   - **Postinst Stability**: Removed disruptive session reloads from package post-install scripts to ensure rock-solid frontend communication.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.1-1_all.ipk
```
