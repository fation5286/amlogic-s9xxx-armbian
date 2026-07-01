#!/bin/bash
#===========================================================================
# WXY-OECT NAS 一键安装脚本
# 首次启动后运行: bash /opt/nas/install-nas.sh
#===========================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[NAS] $1${NC}"; }
warn() { echo -e "${YELLOW}[NAS] $1${NC}"; }
err()  { echo -e "${RED}[NAS] $1${NC}"; }

echo "=========================================="
echo "  WXY-OECT NAS 一键安装脚本"
echo "=========================================="

# ---- 1. 安装 Samba ----
info "安装 Samba..."
apt-get update -qq
apt-get install -y -qq samba 2>/dev/null

# 备份并替换 smb.conf
if [ -f /etc/samba/smb.conf ]; then
    cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
fi
cp /opt/nas/smb.conf /etc/samba/smb.conf

# 设置 Samba 密码（用于管理）
# smbpasswd -a root  # 取消注释以启用 root 密码

# 启动 Samba
systemctl enable --now smbd nmbd
info "Samba 安装完成"

# ---- 2. 安装 Docker ----
info "安装 Docker..."
curl -fsSL https://get.docker.com | sh -s -- --mirror Aliyun 2>/dev/null || \
    curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
info "Docker 安装完成"

# ---- 3. 创建目录结构 ----
info "创建目录结构..."
mkdir -p /mnt/data/{share,album,downloads,syncthing-config,frp}
mkdir -p /opt/nas

# ---- 4. 设置开机自启 ----
info "设置开机自启..."
touch /etc/nas-mode
systemctl enable ssh smbd nmbd docker 2>/dev/null || true

# ---- 5. 清理缓存 ----
apt-get clean
rm -rf /var/lib/apt/lists/*

echo ""
echo "=========================================="
echo "  NAS 安装完成！"
echo "=========================================="
echo ""
echo "  共享地址:  //$(hostname -I | awk '{print $1}')/share"
echo "  相册地址:  //$(hostname -I | awk '{print $1}')/album"
echo "  Syncthing: http://$(hostname -I | awk '{print $1}'):8384"
echo ""
echo "  下一步:"
echo "  1. 在电脑上访问 \\\\$(hostname -I | awk '{print $1}')\\share 复制文件"
echo "  2. 手机安装 Syncthing App 同步相册到 NAS"
echo "  3. 如需下载器，执行: cd /opt/nas && docker compose up -d"
echo ""
