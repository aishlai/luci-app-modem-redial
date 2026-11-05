# Release v1.5.5 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🚀 升级机制还原与极速体验保障 (回归 v1.5.0 经典稳定架构)

1. **全面回归 v1.5.0 直连极速升级机制，根除 UI 挂起卡顿**
   - **问题复盘**：近期版本引入的多阶段状态轮询与守护分离机制导致在部分 OpenWrt / iStoreOS 环境下 `rpcd` 管道等待，导致前端 UI 卡住或超时；而用户验证在 `v1.5.0` 版本时升级体验本就非常丝滑；
   - **架构回归**：彻底移除冗余的后台分叉与轮询等待，全面回归 `v1.5.0` 经过严密验证的高速直连架构；
   - **秒级极速完成**：前端通过直连通道触发 `--do-update`，依赖国内顶级加速镜像（18KB 安装包仅需 0.3 秒下载 + 1 秒静默安装），全程 2~3 秒即可返回结果，界面直接弹出「🎉 升级成功」并自动刷新，再无任何 UI 悬挂与卡死。

### 🎨 界面视觉与排版优化

1. **日志看板宽度与单行 100 字符硬性约束 (继续保留)**
   - 「实时连通性监测日志」及「QoS 触发重拨历史日志」维持硬性宽度约束（`min-width: 100ch`、`cols="100"`、`wrap="off"`、`white-space: pre`）；
   - 彻底杜绝日志在窄屏下的意外换行折行，确保探测报告（目标节点、协议、延迟、状态、诊断详情）始终严格对齐单行呈现，超出部分横向平滑滚动。

---

## 🇺🇸 English Changelog

### 🚀 Upgrade Architecture Restored (Reverting to Proven v1.5.0 Pipeline)

1. **Restored Classic Direct Fast-Upgrade Architecture**
   - **Background**: Complex daemon detachment and status polling introduced in recent iterations caused UI hangs in certain OpenWrt environments. The direct pipeline in `v1.5.0` was proven to be fast and completely stable.
   - **Direct Pipeline Reinstated**: Fully restored `v1.5.0`'s clean and direct execution model (`--do-update`). By leveraging top upstream acceleration mirrors, the 18KB package downloads in ~0.3s and installs in ~1s. The entire process finishes in 2–3 seconds, immediately presenting the "🎉 Upgrade Successful" modal and refreshing cleanly without UI freeze.

### 🎨 UI & Layout Enhancements

1. **100-Character Minimum Line Width for Logs (Preserved)**
   - Both live and historical QoS log viewports retain `min-width: 100ch`, `cols="100"`, `wrap="off"`, and `white-space: pre`.
   - Prevents table columns from wrapping prematurely, guaranteeing single-line alignment with horizontal scrolling.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.5` 更新，点击 `🚀 立即一键在线升级` 即可 2~3 秒极速平滑完成，配置与规则自动保留。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.5-1_all.ipk
```
