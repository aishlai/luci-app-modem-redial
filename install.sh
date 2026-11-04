#!/bin/sh
# ==============================================================================
# 华为/联通光猫 V271-20 自动重拨助手 (luci-app-modem-redial)
# 一键极速安装 / 自动检测更新脚本 (内置国内高速镜像加速与配置无损保护)
# ==============================================================================

set -e

REPO="aishlai/luci-app-modem-redial"
TMP_IPK="/tmp/modem_redial_install.ipk"
CFG_FILE="/etc/config/modem_redial"
BAK_FILE="/tmp/_modem_redial_cfg.bak"

echo ""
echo "========================================================"
echo "  ⚡ 开始安装 / 更新光猫自动重拨助手 (luci-app-modem-redial)..."
echo "========================================================"

# 1. 检查运行环境
if [ ! -x "/bin/opkg" ]; then
    echo "[!] 错误: 未检测到 opkg，本脚本仅适用于 OpenWrt / iStoreOS 系统！"
    exit 1
fi

# 2. 检查 python3 依赖
if ! opkg list-installed 2>/dev/null | grep -q "^python3 "; then
    echo "==> [1/4] 正在安装必要依赖 python3..."
    opkg update
    opkg install python3
else
    echo "==> [1/4] 依赖 python3 检查通过。"
fi

# 3. 备份已有用户配置
if [ -f "$CFG_FILE" ]; then
    echo "==> 正在备份现有光猫配置，确保用户参数绝不丢失..."
    cp -f "$CFG_FILE" "$BAK_FILE" 2>/dev/null || true
fi

# 4. 获取最新 Release 版本地址
echo "==> [2/4] 正在检查 GitHub 最新版本..."
LATEST_URL=""
API_DATA=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null || wget -qO- "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null || true)

if [ -n "$API_DATA" ]; then
    LATEST_URL=$(echo "$API_DATA" | grep "browser_download_url.*_all.ipk" | head -n 1 | cut -d '"' -f 4)
fi

if [ -z "$LATEST_URL" ]; then
    VER=$(curl -s "https://ghfast.top/https://raw.githubusercontent.com/$REPO/main/VERSION" 2>/dev/null || wget -qO- "https://ghfast.top/https://raw.githubusercontent.com/$REPO/main/VERSION" 2>/dev/null || echo "1.1.7-1")
    VER=$(echo "$VER" | tr -d '\r\n ')
    TAG="v$(echo "$VER" | cut -d '-' -f 1)"
    LATEST_URL="https://github.com/$REPO/releases/download/$TAG/luci-app-modem-redial_${VER}_all.ipk"
fi

echo "--> 目标安装包: $LATEST_URL"

# 5. 下载安装包
echo "==> [3/4] 正在高速下载安装包..."
rm -f "$TMP_IPK"

DOWNLOAD_OK=0
for DL in "https://ghfast.top/$LATEST_URL" "https://mirror.ghproxy.com/$LATEST_URL" "https://ghproxy.net/$LATEST_URL" "$LATEST_URL"; do
    if wget -q -T 8 -O "$TMP_IPK" "$DL" 2>/dev/null || curl -sL -m 8 -o "$TMP_IPK" "$DL" 2>/dev/null; then
        if [ -s "$TMP_IPK" ] && [ $(wc -c < "$TMP_IPK") -gt 1024 ]; then
            DOWNLOAD_OK=1
            echo "--> 下载成功！"
            break
        fi
    fi
    rm -f "$TMP_IPK"
done

if [ "$DOWNLOAD_OK" -ne 1 ]; then
    echo "[!] 错误: 下载安装包失败，请检查网络连接！"
    exit 1
fi

# 6. 安装与恢复配置
echo "==> [4/4] 正在执行安装并刷新界面..."
opkg install --force-reinstall "$TMP_IPK"
rm -f "$TMP_IPK"

if [ -f "$BAK_FILE" ]; then
    mv -f "$BAK_FILE" "$CFG_FILE" 2>/dev/null || true
fi

# 清除 LuCI 缓存以确保新界面立即生效
rm -f /tmp/luci-indexcache*
rm -rf /tmp/luci-modulecache/
/etc/init.d/modem_redial restart 2>/dev/null || true

echo ""
echo "========================================================"
echo "  🎉 恭喜！光猫自动重拨助手已成功安装/更新至最新版本！"
echo "  请登录或刷新 OpenWrt 网页后台查看：【网络】或【服务】->【光猫重拨助手】"
echo "========================================================"
exit 0
