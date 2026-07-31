#!/bin/bash
#===========================================================================
# WXY-OECT NAS 一键安装脚本 v3
#===========================================================================

set -e

info() { echo -e "\033[0;32m[NAS] $1\033[0m"; }
warn() { echo -e "\033[1;33m[NAS] $1\033[0m"; }

echo "=========================================="
echo "  WXY-OECT NAS 一键安装脚本 v3"
echo "=========================================="

# ---- 1. 安装基础工具 ----
info "安装基础工具..."
apt-get update -qq
apt-get install -y -qq procps iproute2 pciutils usbutils lshw 2>/dev/null || true
info "基础工具安装完成"

# ---- 2. 安装 Samba ----
info "安装 Samba..."
apt-get install -y -qq samba 2>/dev/null

# 创建共享目录
mkdir -p /mnt/data/{share,album,downloads,syncthing-config,frp,docker}

# 复制 Samba 配置
if [ -f /opt/nas/webui/smb.conf ]; then
    cp /opt/nas/webui/smb.conf /etc/samba/smb.conf
fi

systemctl enable --now smbd nmbd 2>/dev/null || { smbd; nmbd 2>/dev/null || true; }
info "Samba 安装完成"

# ---- 3. 安装 Docker ----
info "安装 Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh -s -- --mirror Aliyun 2>/dev/null || curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker 2>/dev/null || { dockerd &>/dev/null &; }
info "Docker 安装完成"

# ---- 4. 配置 Web UI ----
info "配置 Web UI..."
# 确保 Web UI 脚本有执行权限
chmod +x /opt/nas/webui/nas-webui.py

# 设置默认环境变量
cat > /etc/default/nas-webui << 'EOF'
# WXY-OECT NAS Web UI 配置
IDLE_TIMEOUT=180
LISTEN_PORT=8080
EOF

# 启用服务
systemctl daemon-reload
systemctl enable nas-webui 2>/dev/null || true
info "Web UI 配置完成"

# ---- 5. 创建目录结构 ----
info "创建目录结构..."
mkdir -p /mnt/data/{share,album,downloads,syncthing-config,frp,docker}
mkdir -p /opt/nas
mkdir -p /var/log

# ---- 6. 设置开机自启 ----
info "设置开机自启..."
touch /etc/nas-mode
systemctl enable ssh smbd nmbd docker nas-webui 2>/dev/null || true

# ---- 7. 清理缓存 ----
info "清理缓存..."
apt-get clean
rm -rf /var/lib/apt/lists/*

echo ""
echo "=========================================="
echo "  NAS 安装完成！"
echo "=========================================="
IP=$(hostname -I | awk '{print $1}')
echo "  Samba:     //${IP}/share"
echo "  Web UI:    http://${IP}:8080 (闲置3分钟后自动退出)"
echo "  SSH:       ssh root@${IP}"
echo ""
echo "=========================================="
echo "  Web UI 使用说明"
echo "=========================================="
echo "  访问 http://${IP}:8080 打开管理面板"
echo "  闲置 3 分钟不操作会自动退出，节省资源"
echo "  再次访问时会自动重新启动"
echo ""
echo "  手动控制:"
echo "    systemctl status nas-webui  # 查看状态"
echo "    systemctl restart nas-webui # 重启"
echo ""
