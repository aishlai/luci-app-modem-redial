# Release v1.5.2 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🎨 界面视觉与交互排版优化

1. **实时连通性监测日志看板高度调优**
   - 将「监测重拨」标签页中的实时监测黑底终端看板高度由 `190px` 适度调高至 `310px`；
   - 完美适配 16 行完整探测报告（表头、网络状态诊断、全部公共节点延迟与详情），无需手动上下滚动即可一览全貌。

2. **操作按钮左对齐与说明文本顺序调整**
   - 调换底部控制栏顺序：将三个操作按钮（`🔄 刷新实时日志`、`⚡ 立即探测一轮`、`📊 详细体检弹窗`）靠左统一对齐放置；
   - 内存免磨损说明文本（`💡 说明: 本日志保存在内存中 (/tmp)，每轮检测自动刷新覆盖，不消耗闪存寿命。`）紧随按钮之后展示，布局层级更清晰，点击更顺手。

---

## 🇺🇸 English Changelog

### 🎨 UI & Layout Enhancements

1. **Expanded Live Telemetry Log View Height**
   - Increased the height of the live telemetry terminal box from `190px` to `310px`.
   - Comfortably renders the full 16-line telemetry report (headers, network diagnosis, all probe targets, and latencies) without requiring manual scrolling.

2. **Left-Aligned Action Buttons & Reordered Legend**
   - Reordered the control footer: action buttons (`🔄 Refresh Live Log`, `⚡ Probe Round Now`, `📊 Detailed Diagnostics`) are now neatly left-aligned for quicker access.
   - The memory-only zero-flash-wear notice is positioned following the buttons, providing a clean and intuitive layout.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.2-1_all.ipk
```
