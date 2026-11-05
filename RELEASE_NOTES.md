# Release v1.5.3 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🎨 界面视觉与排版优化

1. **精简实时监测控制栏，去除冗余说明文字**
   - 移除了控制栏底部按钮旁冗余的说明文字（`💡 说明: 本日志保存在内存中 (/tmp)...`），由于实时日志框头部已清晰内嵌此项提示，精简后界面更加利落；
   - 操作按钮（`🔄 刷新实时日志`、`⚡ 立即探测一轮`、`📊 详细体检弹窗`）保持统一靠左对齐，间距规整。

---

## 🇺🇸 English Changelog

### 🎨 UI & Layout Enhancements

1. **Simplified Live Telemetry Action Bar**
   - Removed the redundant explanation note next to the action buttons, as the in-memory temporary nature is already explicitly embedded in the log header.
   - Action buttons (`🔄 Refresh Live Log`, `⚡ Probe Round Now`, `📊 Detailed Diagnostics`) are cleanly left-aligned with a compact, uniform layout.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.3` 更新，点击 `🚀 立即一键在线升级` 即可全自动平滑更新，配置与规则自动保留。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.3-1_all.ipk
```
