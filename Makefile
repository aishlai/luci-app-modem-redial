include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-modem-redial
PKG_VERSION:=1.4.2
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=aishlai

LUCI_TITLE:=LuCI Support for Beijing Unicom Huawei V271-20 ONT Auto-Redial Assistant (光猫重拨助手)
LUCI_DEPENDS:=+python3
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
