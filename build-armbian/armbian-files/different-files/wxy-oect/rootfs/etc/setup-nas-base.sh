#===========================================================================
# NAS 专用基础镜像配置
#===========================================================================

echo "NAS_MODE=1" > /etc/default/nas-config

# 配置 apt 最小化安装
cat > /etc/apt/apt.conf.d/99-nas-minimal << 'EOF'
APT::Install-Recommends "0";
APT::Install-Suggests "0";
APT::AutoRemove::RecommendsImportant "0";
APT::AutoRemove::SuggestsImportant "0";
EOF

# 设置默认目标为多用户模式（无图形界面）
ln -sf /lib/systemd/system/multi-user.target /etc/systemd/system/default.target

# 创建 NAS 初始化服务
mkdir -p /etc/systemd/system/nas-setup.service.d
cat > /etc/systemd/system/nas-setup.service.d/override.conf << 'EOF'
[Unit]
Description=NAS Setup Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/opt/nas/install-nas.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
