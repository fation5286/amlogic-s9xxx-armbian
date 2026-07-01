#!/bin/bash
#===========================================================================
# NAS 专用基础镜像配置
# 控制基础镜像的最小化安装
# 放置在 build-armbian/armbian-files/different-files/wxy-oect/rootfs/etc/
#===========================================================================

# 标记此为 NAS 专用镜像
echo "NAS_MODE=1" > /etc/default/nas-config

# 设置最小化包列表（仅 NAS 必需）
cat > /etc/apt/apt.conf.d/99-nas-minimal << 'EOF'
# 只安装推荐的最小化包
APT::Install-Recommends "0";
APT::Install-Suggests "0";

# 清理时移除更多无用包
APT::AutoRemove::RecommendsImportant "0";
APT::AutoRemove::SuggestsImportant "0";
EOF

# 禁用不必要的 systemd targets
# 确保系统以 multi-user.target (服务器模式) 启动
ln -sf /lib/systemd/system/multi-user.target /etc/systemd/system/default.target

# 创建 NAS 专用服务单元（可选增强）
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
