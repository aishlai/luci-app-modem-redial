# Release v1.6.1 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🚀 升级与交互验证版本 (Maintenance & Verification Release)

1. **版本号同步升级**
   - 全面升级至 `v1.6.1`（安装包版本 `1.6.1-1`），供用户快速验证网页后台一键升级流程与实时首屏秒开体验；
   - 彻底继承 `v1.6.0` 的首屏极速秒开架构：守护进程保底拉起、状态查询与检查更新完全异步脱离，零阻塞首屏渲染与 `uci.get` 批处理。

2. **升级流程平滑性验证**
   - 验证通过 LuCI 网页后台「🚀 立即一键在线升级」的下载、备份配置、重装与平滑自动刷新流程。

---

## 🇺🇸 English Changelog

### 🚀 Maintenance & Upgrade Verification Release

1. **Version Bump to v1.6.1**
   - Bumped to `v1.6.1` (package `1.6.1-1`) for testing and validating the Web UI one-click in-place upgrade pipeline;
   - Fully retains the asynchronous initial page loading architecture introduced in `v1.6.0`, ensuring immediate UI rendering without blocking `uci.get` batch calls.

2. **Seamless Upgrade Pipeline**
   - Verifies automated package download, config preservation, `opkg` reinstallation, and smooth page reload.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.6.1` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.6.1-1_all.ipk
```
