# Release v1.5.9 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🎨 界面体验优化：状态面板「连接状态」与「当前拨号模式」全面中文化

1. **状态面板指示值全面中文化**
   - **连接状态**：彻底告别原始英文（如 `Connected` / `Disconnected`），卡片直观显示规范中文：`已连接`（绿色高亮）、`未连接`（红色警告）、`正在连接` / `正在断开` / `重拨中...`（黄色提示）或 `未配置` / `未启用`；
   - **当前拨号模式**：告别底层英文术语（如 `AlwaysOn` / `Manual`），卡片直观呈现中文模式名称：`自动拨号`（AlwaysOn）与 `手动拨号`（Manual）。

2. **前后端双重中文化兼容保障**
   - **后端状态输出优化**：`modem_redial.py --status` 输出的 JSON 数据中，`status` 与 `trigger` 字段直接输出规范中文，同时保留 `raw_status` 与 `raw_trigger` 便于程序化解析；
   - **前端实时自动格式化**：LuCI 页面在首次载入渲染以及用户点击「🔄 刷新状态」或重拨完成自动刷新时，均由前端统一进行双重校验与中文化渲染，彻底杜绝缓存残留导致的英文闪烁。

---

## 🇺🇸 English Changelog

### 🎨 UI Optimization: Localized Status Panel Values

1. **Fully Localized Status Card Values**
   - **Connection Status**: Translated raw ONT status strings to clear Chinese equivalents: `已连接` (Connected, green), `未连接` (Disconnected, red), `正在连接` (Connecting), `正在断开` (Disconnecting), or `重拨中...` (Redialing).
   - **Current Dialing Mode**: Replaced technical parameters (`AlwaysOn` / `Manual`) with intuitive Chinese terms: `自动拨号` (Auto / AlwaysOn) and `手动拨号` (Manual).

2. **Dual-Layer Backend & Frontend Localization**
   - Python status JSON (`--status`) automatically maps `status` and `trigger` to Chinese while retaining `raw_status` and `raw_trigger`.
   - JavaScript frontend safely checks and normalizes values during initial rendering and dynamic refreshes.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.9` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.9-1_all.ipk
```
