# WXY-OECT NAS 专用镜像

## 概述

为 WXY-OECT (IDL WXY-OEC-turbo-4g, Rockchip RK3566) 设备构建的**极致精简 NAS 专用 Armbian 镜像**。

## 镜像特点

| 特性 | 规格 |
|------|------|
| 基础系统 | Armbian Resolute (最小化 Debian) |
| 内核 | Rockchip RK35xx 6.1.y LTS (可自选) |
| 开机内存 | ~100MB (原版 ~230MB) |
| 磁盘占用 | ~1.0GB (原版 ~2.5GB) |
| 预装服务 | SSH, Samba, Docker, Web UI |
| Web UI | 轻量 Go 服务，50秒空闲自动退出 |

## 精简清单

### 禁用的服务
ModemManager, bluetooth, cups, thermald, colord, pulseaudio, avahi-daemon, snapd, systemd-logind, unattended-upgrades, NetworkManager 相关服务, 以及所有桌面相关服务

### 精简的包
modemmanager, bluez, cups-common, thermald, whoopsie, apport, landscape-common, cloud-guest-utils, colord, pulseaudio

### 保留的服务
- **SSH** — 远程管理
- **Samba** — 文件共享
- **Docker** — 容器运行时
- **Web UI** — 轻量管理面板 (端口 8080)

## 快速开始

### 1. 刷入镜像

1. 从 GitHub Releases 下载 `.img.gz` 文件
2. 解压: `gunzip WXY-OECT_NAS_*.img.gz`
3. 使用 **RKDevTool** 刷入 eMMC 或 TF 卡

### 2. 首次启动

```bash
# SSH 登录 (默认 root/1234)
ssh root@NAS_IP

# 运行一键安装脚本
bash /opt/nas/install-nas.sh
```

### 3. 访问 NAS

| 服务 | 地址 |
|------|------|
| 文件共享 | `\<NAS_IP>\share` 或 `\<NAS_IP>\album` |
| Web UI | `http://<NAS_IP>:8080` |
| Docker (后续) | Syncthing :8384, qBittorrent :8080 |

## Web UI 功能

轻量级 NAS 管理面板，无需安装任何依赖：

- **系统状态** — 运行时间、CPU 负载、内存使用
- **存储管理** — 磁盘使用情况、一键挂载
- **服务管理** — SSH/Samba/Docker/Web UI 状态和启停
- **磁盘管理** — 连接磁盘列表
- **系统重启** — 远程重启

### 自动退出机制

Web UI 服务在无请求 **50 秒**后自动退出，释放内存。下次访问时自动重新启动。

## 目录结构

```
/mnt/data/
├── share/          ← Samba 主共享目录
├── album/          ← 手机相册备份目录
├── downloads/      ← 下载目录
├── syncthing-config/ ← Syncthing 配置
├── docker/         ← Docker 数据
└── frp/            ← 内网穿透配置
```

## Docker 服务管理

```bash
# 启动 Syncthing (相册同步)
cd /opt/nas && docker compose up -d syncthing

# 启动 qbittorrent (下载器)
cd /opt/nas && docker compose up -d qbittorrent

# 查看所有运行中的容器
docker ps
```

## 手机相册同步

### Android
1. 安装 Syncthing App
2. 添加设备: `nas-wxy-oect`
3. 将 `/DCIM/Camera` 同步到 NAS 的 `/album` 目录

### iOS
1. 安装 Syncthing 或 Syncthing-Fork
2. 添加设备后同步相册目录
3. 或在 iOS 文件 App 中直接访问 `smb://NAS_IP/album`

## 系统维护

### 查看内存占用
```bash
free -h
```

### 更新内核
```bash
armbian-update
```

### 查看 Web UI 日志
```bash
journalctl -u nas-webui -f
```

## 常见问题

**Q: 如何更新内核？**
A: 运行 `armbian-update` 选择最新内核

**Q: Web UI 打不开？**
A: 确认已运行 `bash /opt/nas/install-nas.sh`，且端口 8080 未被防火墙阻止

**Q: 磁盘没有自动挂载？**
A: 在 Web UI 点击"挂载"按钮，或运行 `mount -a`