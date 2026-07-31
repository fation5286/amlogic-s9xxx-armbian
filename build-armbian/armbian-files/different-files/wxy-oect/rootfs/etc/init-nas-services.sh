#!/bin/bash
#===========================================================================
# WXY-OECT NAS 专用精简服务脚本 v3
#===========================================================================

set -e

echo "[NAS] 开始精简 systemd 服务..."

# ---- 1. 禁用所有桌面/无关服务 ----
SERVICES_TO_DISABLE=(
    ModemManager
    accounts-daemon
    bluetooth
    cups
    thermald
    systemd-logind
    unattended-upgrades
    apt-daily.service
    apt-daily-upgrade.service
    serial-getty@ttyS0.service
    snapd.service
    snapd.autoimport.service
    snapd.seeded.service
    avahi-daemon
    dbus-org.freedesktop.resolve1.service
    dbus-org.freedesktop.nm-dispatcher
    NetworkManager-wait-online.service
    NetworkManager-dispatcher.service
    keyboard-setup.service
    systemd-udevd.service
    colord
    gvfs-daemon
    pulseaudio
    bluetooth.service
    systemd-resolved
    systemd-timesyncd
    whoopsie
)

for svc in "${SERVICES_TO_DISABLE[@]}"; do
    if systemctl list-unit-files "${svc}" &>/dev/null 2>&1; then
        systemctl disable --now "${svc}" 2>/dev/null || true
    fi
done

# ---- 2. 创建 systemd preset 文件 ----
mkdir -p /etc/systemd/system-preset
cat > /etc/systemd/system-preset/99-nas-disable-defaults << 'EOF'
# WXY-OECT NAS 专用 preset
disable ModemManager
disable accounts-daemon
disable bluetooth
disable cups
disable thermald
disable systemd-logind
disable unattended-upgrades
disable apt-daily
disable apt-daily-upgrade
disable serial-getty@ttyS0
disable snapd
disable avahi-daemon
disable NetworkManager-wait-online
disable NetworkManager-dispatcher
disable keyboard-setup
disable systemd-resolved
disable systemd-timesyncd
disable colord
disable gvfs-daemon
disable pulseaudio
disable whoopsie
EOF

echo "[NAS] 已创建 systemd preset 文件"

# ---- 3. 禁用多余 cron 任务 ----
rm -f /etc/cron.daily/apt-compat
rm -f /etc/cron.daily/apt
rm -f /etc/cron.daily/unattended-upgrades
rm -f /etc/cron.weekly/apt
rm -f /etc/cron.monthly/apt

echo "[NAS] 已清理 cron 任务"

# ---- 4. 应用 sysctl 优化 ----
if [ ! -f /etc/sysctl.d/99-nas-applied ]; then
    cat > /etc/sysctl.d/99-nas.conf << 'EOF'
# WXY-OECT NAS 专用 sysctl 优化
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_tw_reuse = 1
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 20
vm.dirty_background_ratio = 5
EOF
    sysctl -p /etc/sysctl.d/99-nas.conf 2>/dev/null || true
    touch /etc/sysctl.d/99-nas-applied
    echo "[NAS] 已应用 sysctl 优化"
fi

# ---- 5. 清理不需要的包 ----
DEBIAN_PACKAGES_TO_PURGE=(
    modemmanager
    bluez
    cups-common
    thermald
    whoopsie
    apport
    landscape-common
    cloud-guest-utils
    colord
    pulseaudio
)

for pkg in "${DEBIAN_PACKAGES_TO_PURGE[@]}"; do
    if dpkg -l "$pkg" &>/dev/null 2>&1; then
        apt-get purge -y "$pkg" 2>/dev/null || true
    fi
done

apt-get autoremove -y 2>/dev/null || true

echo "[NAS] 服务精简完成！"
