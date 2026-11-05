# Release v1.5.7 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### ⚡ 页面加载极速优化：彻底解决首次进入卡顿与更新检测阻塞

1. **静默更新检测完全异步化与 30 分钟内存缓存**
   - **痛点分析**：旧版本在页面载入 1 秒后便立即向 GitHub 发起更新请求；因国内直连 GitHub API 经常遭遇 GFW 丢包或 6 秒超时挂起，导致占用 `rpcd` 进程并严重阻塞网页的初次渲染和交互体验；特别是在刚升级完成自动刷新时，卡顿感知尤为明显；
   - **30 分钟内存极速缓存**：在 `/tmp/log/modem_redial_update_cache.json` 中建立非持久化内存缓存，首次进入优先读取缓存（0 毫秒即时返回），杜绝频繁请求 GitHub；
   - **延时 3.5 秒后台异步触发**：若无缓存或缓存过期，延时至页面各区块完全渲染展示 3.5 秒后才在后台以非阻塞 Promise 执行静默检测，保障初次进入页面瞬间完成渲染；
   - **升级后即时注入最新态**：一键升级成功后，底层立即就地写入「已是最新版」缓存，页面刷新后零延迟秒开。

2. **加速镜像智能优先与超时收紧**
   - 彻底摒弃优先直连 `api.github.com`（易超时 6 秒）的落后设计，改为优先通过极速加速镜像（`ghfast.top`）在 2.5 秒内极速探测版本号，彻底根除 GFW 造成的数秒级挂起。

3. **光猫状态 5 秒短时防挤占缓存**
   - 为光猫登录状态查询增加 5 秒短时防抖缓存，避免浏览器快速重载时反复与光猫握手建立会话，进一步提升初次进入与页面刷新的流畅度。

---

## 🇺🇸 English Changelog

### ⚡ Page Load Optimization: Resolved Initial Load Lag & Decoupled Update Check

1. **Fully Asynchronous Silent Update Check & 30-Minute RAM Cache**
   - **Root Cause**: Previously, the plugin fired a synchronous-style GitHub update check just 1 second after page load. In regions where direct access to `api.github.com` is throttled or dropped, the 6-second TCP timeout tied up `rpcd` workers, causing noticeable UI freeze—especially on the first page load right after an upgrade.
   - **30-Minute RAM Cache**: Implemented in-memory caching (`/tmp/log/modem_redial_update_cache.json`). Silent auto-checks now return within 0.001 seconds from cache.
   - **Deferred Background Execution (3.5s)**: If cache is absent, silent checks run asynchronously 3.5 seconds after page render, ensuring 100% smooth initial user interaction.
   - **Instant Post-Upgrade Cache Injection**: Upon successful in-place upgrade, the cache is immediately written with the newest version status, allowing instant page reloads.

2. **Mirror Acceleration Priority & Tighter Timeouts**
   - Prioritizes domestic mirror routes (`ghfast.top`) with 2.5s timeouts, eliminating the classic 6s GFW hangs.

3. **5-Second Debounce Cache for Modem Status Query**
   - Prevents consecutive HTTP handshake storms to the Huawei ONT upon page reloads.

---

### 📦 安装与升级说明 (Installation & Upgrade)

**通过 LuCI 网页后台一键升级 / Web UI In-place Upgrade**:
1. 进入 OpenWrt 后台 -> `网络` -> `光猫重拨助手`；
2. 页面右上角将自动检测到 `v1.5.7` 更新，点击 `🚀 立即一键在线升级` 即可极速完成升级。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.5.7-1_all.ipk
```
