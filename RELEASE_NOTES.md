# Release v1.5.6 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🚀 版本验证与升级稳定性保障

1. **一键在线升级功能验证版本**
   - 本版本用于全面检验 `v1.5.5` 还原的极速直连在线升级机制；
   - 用户在 OpenWrt / iStoreOS 后台点击 `🚀 立即一键在线升级`，即可毫秒级拉取安装包并在 2~3 秒内平滑完成升级；
   - 升级全程自动保护用户光猫地址、密码、WAN 接口名与定时设置等所有自定义配置，升级完成后自动弹出提示并刷新页面。

2. **完整保留排版与单行 100 字符约束**
   - 监测日志看板继续保持最低单行容纳 100 字符设计，禁用非必要换行折行，保持表格列完美纵向对齐，支持横向平滑滚动。

---

## 🇺🇸 English Changelog

### 🚀 Version Verification & Upgrade Stability

1. **In-place Upgrade Verification Milestone**
   - This release serves to verify the restored high-speed direct upgrade pipeline from `v1.5.5`.
   - In OpenWrt / iStoreOS LuCI, clicking `🚀 立即一键在线升级` downloads and installs the update within 2–3 seconds.
   - Preserves all user configurations (modem URL, credentials, WAN name, schedules) throughout the upgrade, presenting a success modal and refreshing smoothly.

2. **Full Log Formatting & 100-Char Width Maintained**
   - Telemetry logs retain strict 100-character single-line width, preventing unwanted text wrapping and ensuring perfect column alignment with horizontal scrolling.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.6` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.6-1_all.ipk
```
