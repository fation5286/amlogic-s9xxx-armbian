# WXY-OECT NAS 专用启动服务脚本
if [ -f /etc/nas-mode ]; then
    echo "[NAS] 检测到 NAS 模式，执行精简启动..."
    
    if [ ! -f /var/log/nas-first-boot-done ]; then
        bash /etc/init-nas-services.sh
        touch /var/log/nas-first-boot-done
        echo "[NAS] 首次启动精简完成，下次启动将跳过"
    fi
    
    sysctl -p /etc/sysctl.d/99-nas.conf 2>/dev/null || true
    
    systemctl enable --now ssh 2>/dev/null || true
    systemctl enable --now smbd 2>/dev/null || true
    systemctl enable --now nmbd 2>/dev/null || true
    systemctl enable --now docker 2>/dev/null || true
    systemctl enable --now nas-webui 2>/dev/null || true
    
    # 启动 Web UI（如果未通过 systemd 启动）
    if ! systemctl is-active nas-webui &>/dev/null; then
        /opt/nas/webui/nas-webui &>/dev/null &
    fi
    
    mkdir -p /mnt/data /mnt/usb1
    mount -a 2>/dev/null || true
    
    mkdir -p /mnt/data/share /mnt/data/album /mnt/data/docker
    
    echo "[NAS] 启动完成！"
    echo "[NAS] 可用服务: SSH, Samba, Docker, Web UI"
    echo "[NAS] 共享目录: //NAS_IP/share 和 //NAS_IP/album"
    echo "[NAS] Web UI:   http://NAS_IP:8080"
    exit 0
fi