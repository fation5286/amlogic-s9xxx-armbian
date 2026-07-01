#!/bin/bash
#===========================================================================
# NAS 专用基础镜像配置
#===========================================================================

echo "NAS_MODE=1" > /etc/default/nas-config

cat > /etc/apt/apt.conf.d/99-nas-minimal << 'EOF'
APT::Install-Recommends "0";
APT::Install-Suggests "0";
APT::AutoRemove::RecommendsImportant "0";
APT::AutoRemove::SuggestsImportant "0";
EOF

ln -sf /lib/systemd/system/multi-user.target /etc/systemd/system/default.target

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