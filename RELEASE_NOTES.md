# Release v1.4.7 / 版本发布说明

## 🇨🇳 中文更新日志 (Changelog in Chinese)

### 🚀 重点交互与视觉体验优化

1. **“刷新状态”点击即时动效与数据加载反馈**
   - **问题反馈**：用户点击“刷新状态”后界面没有明显变化，若 IP 和连接未变容易误以为按钮未起作用；
   - **交互升级**：
     1. 点击按钮瞬间：按钮禁用并切换为 `⏳ 正在刷新...`，防止重复点击；
     2. 状态卡片联动：上方“当前公网 IP”、“连接状态”、“当前拨号模式”卡片即时变更为 `⏳ 正在读取...` / `⏳ 正在检测...` / `⏳ 正在查询...` 加载态；
     3. 异步数据到达：卡片瞬间渲染最新网络状态与公网 IP，按钮呈现 `✅ 已刷新` 并在 700ms 后平滑恢复为 `🔄 刷新状态`，为用户提供极其清晰有感的即时刷新反馈。

2. **重拨按钮跳闪彻底根治**
   - 优化后端 PID 生命周期与前端防重状态锁，重拨成功后 5 秒倒计时平稳顺畅，绝不跳闪。

3. **进入插件静默自动检查更新**
   - 每次进入插件后台自动静默检测 GitHub Releases 最新版，有新版自动弹出升级弹窗，已是最新版则完全静默不打扰。

---

## 🇺🇸 English Changelog

### 🚀 Key Improvements & Visual Feedback

1. **Enhanced Visual Feedback for "Refresh Status" Button**
   - **User Pain Point**: Clicking "Refresh Status" previously showed little visual difference when IP remained unchanged, making it seem inactive.
   - **Interactive Enhancements**:
     1. Immediate Button State: Button disables and displays `⏳ Refreshing...` to prevent redundant spamming.
     2. Status Cards Loading State: Top cards for Public IP, Connection Status, and Dial Mode instantly switch to interactive loading text (`⏳ Reading...` / `⏳ Detecting...` / `⏳ Querying...`).
     3. Successful Transition: Cards render freshly fetched live telemetry, while the button shows `✅ Refreshed` before gracefully returning to `🔄 Refresh Status`, providing clear and intuitive tactile feedback.

2. **Eliminated Button Flickering**
   - Cleaned up daemon PID lifecycles and added frontend debounce locks to ensure smooth 5-second countdown after redial completes.

3. **Silent Background Update Checks on View Entry**
   - Automatic background version detection upon visiting the page, prompting a modal only when a new release is actually available.

---

### 📦 Installation & Upgrade / 安装与升级说明

**iStoreOS 用户**:
直接在 iStore 商店中点击【手动安装】，上传 `.ipk` 文件即可。

**OpenWrt 命令行安装 / Upgrade via SSH**:
```bash
opkg update && opkg install python3
opkg install --force-reinstall luci-app-modem-redial_1.4.7-1_all.ipk
```
