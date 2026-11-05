# Release v1.5.4 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🐛 重点修复：一键升级「XHR request timed out」假报错彻底根治

1. **前端升级进度轮询与执行解耦架构**
   - **痛点分析**：旧版本在触发升级时，进度轮询定时器嵌套在 `fs.exec` 的回调函数内；若底层因守护进程脱离管道稍有延迟或网络代理响应滞后，前端便一直阻塞在初试状态，直到 30 秒后触发 LuCI 原生 XHR 限制并抛出 `❌ XHR request timed out` 弹窗（即便此时后台早已静默升级成功）；
   - **立即启动轻量轮询**：点击升级后，前端立即并行启动内存级状态轮询（使用开销近乎为 0 的 `fs.read` 直接读取 tmpfs 中的状态，不再频繁调用 Python 进程）；
   - **报错智能鉴别过滤**：在 `fs.exec` 捕获到网络超时或断开时，自动回查后台状态文件；若升级已在进行或已完成，直接静默放行并交由进度条接管，全面杜绝超时报错弹窗扰民。

2. **后端脱离管道强化 (start-stop-daemon / nohup)**
   - 在快捷脚本透传层中使用 OpenWrt 原生 `start-stop-daemon`（或 `nohup` 兜底）彻底切断子进程与 `rpcd` 管道文件描述符之间的继承关系，实现真正的微秒级即时响应返回。

### 🎨 界面视觉排版优化

1. **日志看板宽度与单行 100 字符硬性约束**
   - 为「实时连通性监测日志」与「QoS 触发重拨历史日志」增加宽度硬性约束：设置 `min-width: 100ch`、`cols="100"`，并开启 `wrap="off"` 与 `white-space: pre`；
   - 彻底杜绝因窄屏或侧边栏挤压导致的自动折行现象，确保表格各项指标（目标节点、协议、延迟、状态、诊断详情）始终严格对齐单行呈现；外层容器自适应横向平滑滚动。

---

## 🇺🇸 English Changelog

### 🐛 Critical Bug Fix: Completely Eliminated False "XHR request timed out" Popup

1. **Decoupled Asynchronous Upgrade Pipeline & Zero-Overhead Polling**
   - **Root Cause**: Previously, the status polling timer was nested inside the `fs.exec` promise resolution. Any pipe lag or RPC session wait could delay the promise until LuCI's 30-second XHR timeout fired, triggering a false error modal even though the background upgrade succeeded.
   - **Instant Polling via `fs.read`**: The progress polling timer now starts immediately upon clicking, utilizing ultra-lightweight `fs.read` on tmpfs without repeatedly launching Python processes.
   - **Intelligent Error Suppression**: If `fs.exec` catches an XHR timeout, it verifies whether the background task is running or completed. If active/succeeded, the false alarm is silenced and the progress bar smoothly completes.

2. **Robust Daemon Detachment**
   - Utilizes OpenWrt's native `start-stop-daemon` (with `nohup` fallback) to fully sever standard pipes and file descriptors from `rpcd`, guaranteeing immediate execution return.

### 🎨 UI & Layout Enhancements

1. **Strict 100-Character Minimum Line Width for Logs**
   - Added `min-width: 100ch`, `cols="100"`, `wrap="off"`, and `white-space: pre` to both live and historical QoS log viewports.
   - Prevents premature word wrapping on narrower viewports or custom themes, ensuring table columns (target, protocol, latency, status, details) remain perfectly aligned in a single line with smooth horizontal scrolling.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.4` 更新，点击 `🚀 立即一键在线升级` 即可全自动平滑更新，配置与规则自动保留。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.4-1_all.ipk
```
