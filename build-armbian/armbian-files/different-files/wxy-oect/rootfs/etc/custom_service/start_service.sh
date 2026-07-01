#!/bin/bash
#===========================================================================
# WXY-OECT NAS 专用启动服务脚本
# 覆盖 common-files 中的同名脚本
# 在镜像编译时放入 rootfs/etc/custom_service/start_service.sh
#===========================================================================

# 检查是否为 NAS 模式
if [ -f /etc/nas-mode ]; then
    echo "[NAS] 检测到 NAS 模式，执行精简启动..."
    
    # 1. 禁用所有非必要 systemd 服务（首次启动时执行）
    if [ ! -f /var/log/nas-first-boot-done ]; then
        bash /etc/init-nas-services.sh
        
        # 标记首次启动已完成
        touch /var/log/nas-first-boot-done
        echo "[NAS] 首次启动精简完成，下次启动将跳过"
    fi
    
    # 2. 应用 sysctl 优化
    sysctl -p /etc/sysctl.d/99-nas.conf 2>/dev/null || true
    
    # 3. 确保 NAS 必需服务正在运行
    systemctl enable --now ssh 2>/dev/null || true
    systemctl enable --now smbd 2>/dev/null || true
    systemctl enable --now nmbd 2>/dev/null || true
    systemctl enable --now docker 2>/dev/null || true
    
    # 4. 挂载数据盘
    mkdir -p /mnt/data /mnt/usb1
    mount -a 2>/dev/null || true
    
    # 5. 创建默认目录结构
    mkdir -p /mnt/data/share /mnt/data/album /mnt/data/docker
    
    echo "[NAS] 启动完成！"
    echo "[NAS] 可用服务: SSH, Samba, Docker"
    echo "[NAS] 共享目录: //NAS_IP/share 和 //NAS_IP/album"
    exit 0
fi

# ---- 以下是非 NAS 模式的通用启动逻辑 ----
# 保持与原脚本兼容，普通 Armbian 用户不受影响
