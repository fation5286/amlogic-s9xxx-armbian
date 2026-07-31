#!/usr/bin/env python3
"""WXY-OECT NAS Web UI Manager - 按需启动，闲置退出，节省资源"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# ========== 配置 ==========
IDLE_TIMEOUT = int(os.environ.get('IDLE_TIMEOUT', '180'))  # 闲置 3 分钟后自动退出
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', '8080'))
PID_FILE = "/tmp/nas-webui.pid"
LOG_FILE = "/var/log/nas-webui.log"

# ========== 全局状态 ==========
_last_activity = time.time()
_shutdown = threading.Event()
_server_instance = None

def log(msg):
    """写入日志"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

def _mark():
    global _last_activity
    _last_activity = time.time()

def _idle():
    return time.time() - _last_activity > IDLE_TIMEOUT

def _cmd(c, timeout=10):
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1

def is_running():
    """检查进程是否在运行"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except:
            pass
    return False

def start_webui():
    """启动 Web UI"""
    if is_running():
        log("Web UI 已经在运行")
        return True
    
    log("启动 Web UI...")
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    try:
        pid = os.fork()
        if pid > 0:
            with open(PID_FILE, "w") as f:
                f.write(str(pid))
            log(f"Web UI 已启动，PID: {pid}")
            return True
        else:
            os.setsid()
            sys.stdin = open('/dev/null', 'r')
            sys.stdout = open(LOG_FILE, 'w')
            sys.stderr = open(LOG_FILE, 'w')
            main()
            os._exit(0)
    except Exception as e:
        log(f"启动失败: {e}")
        return False

def stop_webui():
    """停止 Web UI"""
    if not is_running():
        log("Web UI 未在运行")
        return True
    
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        log(f"Web UI 已停止，PID: {pid}")
        return True
    except Exception as e:
        log(f"停止失败: {e}")
        return False

def get_status():
    """获取状态"""
    if is_running():
        try:
            with open(PID_FILE) as f:
                pid = f.read().strip()
            return {"running": True, "pid": pid}
        except:
            return {"running": True, "pid": "unknown"}
    return {"running": False, "pid": None}

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class NASWebUIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        log(f"{self.address_string()} - {format % args}")
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    
    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def _send_css(self, css):
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.end_headers()
        self.wfile.write(css.encode("utf-8"))
    
    def _send_js(self, js):
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.end_headers()
        self.wfile.write(js.encode("utf-8"))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        _mark()
        path = self.path.split("?")[0]
        
        if path == "/":
            self._send_html(INDEX_HTML)
        elif path == "/css":
            self._send_css(STYLE_CSS)
        elif path == "/js":
            self._send_js(APPLICATION_JS)
        elif path == "/api/status":
            self._send_json(self._get_status())
        elif path == "/api/services":
            self._send_json(self._get_services())
        elif path == "/api/storage":
            self._send_json(self._get_storage())
        elif path == "/api/network":
            self._send_json(self._get_network())
        elif path == "/api/docker":
            self._send_json(self._get_docker())
        elif path == "/api/logs":
            self._send_json(self._get_logs())
        elif path == "/api/settings":
            self._send_json(self._get_settings())
        elif path == "/api/control/start":
            start_webui()
            self._send_json({"status": "started"})
        elif path == "/api/control/stop":
            stop_webui()
            self._send_json({"status": "stopped"})
        elif path == "/api/control/restart":
            stop_webui()
            time.sleep(1)
            start_webui()
            self._send_json({"status": "restarted"})
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        _mark()
        path = self.path.split("?")[0]
        
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
        
        try:
            data = json.loads(post_data) if post_data else {}
        except:
            data = {}
        
        if path == "/api/service/control":
            self._send_json(self._control_service(data))
        elif path == "/api/disk/mount":
            self._send_json(self._mount_disk(data))
        elif path == "/api/disk/umount":
            self._send_json(self._umount_disk(data))
        elif path == "/api/container/control":
            self._send_json(self._control_container(data))
        elif path == "/api/reboot":
            self._send_json(self._reboot_system())
        elif path == "/api/restart":
            self._send_json(self._restart_services())
        elif path == "/api/settings/save":
            self._send_json(self._save_settings(data))
        else:
            self._send_json({"error": "Unknown endpoint"}, 404)
    
    # ========== 数据获取方法 ==========
    
    def _get_status(self):
        return {
            "uptime": self._get_uptime_str(),
            "cpu": self._get_cpu(),
            "memory": self._get_memory(),
            "load": self._get_load(),
            "hostname": self._get_hostname(),
            "kernel": self._get_kernel(),
            "webui": get_status()
        }
    
    def _get_services(self):
        services = ["ssh", "smbd", "nmbd", "docker", "nas-webui"]
        result = []
        for svc in services:
            _, status, _ = _cmd(["systemctl", "is-active", svc])
            _, enabled, _ = _cmd(["systemctl", "is-enabled", svc])
            result.append({
                "name": svc,
                "status": status if status in ["active", "inactive", "failed"] else "unknown",
                "enabled": enabled == "enabled"
            })
        return {"services": result}
    
    def _get_storage(self):
        out, _, _ = _cmd(["df", "-h", "--output=target,size,used,avail,pcent,mounted"])
        partitions = []
        for line in out.split("\n")[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5 and parts[0].startswith("/"):
                partitions.append({
                    "device": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "use_pct": parts[4],
                    "mount": parts[5] if len(parts) > 5 else ""
                })
        
        disks = []
        out, _, _ = _cmd(["lsblk", "-J", "-b", "-d", "-o", "NAME,SIZE,TYPE,ROTA,MODEL"])
        try:
            data = json.loads(out)
            for d in data.get("blockdevices", []):
                if d.get("type") == "disk":
                    disks.append({
                        "name": f"/dev/{d['name']}",
                        "size": self._format_size(int(d["size"])) if d.get("size") else "N/A",
                        "model": d.get("model", "Unknown"),
                        "rotational": "HDD" if d.get("rota") == "1" else "SSD"
                    })
        except:
            pass
        
        return {"partitions": partitions, "disks": disks}
    
    def _get_network(self):
        ip, _, _ = _cmd(["hostname", "-I"])
        mac_out, _, _ = _cmd(["ip", "link", "show"])
        
        interfaces = []
        for line in mac_out.split("\n"):
            if ":" in line and "@" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    iface = parts[1].rstrip(":")
                    if iface != "lo":
                        ip_addr, _, _ = _cmd(["ip", "addr", "show", iface])
                        ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_addr)
                        mac_match = re.search(r'link/ether ([0-9a-f:]+)', mac_out)
                        interfaces.append({
                            "name": iface,
                            "ip": ip_match.group(1) if ip_match else "N/A",
                            "mac": mac_match.group(1) if mac_match else "N/A"
                        })
        
        return {"ip": ip.strip(), "interfaces": interfaces}
    
    def _get_docker(self):
        out, _, rc = _cmd(["docker", "ps", "-a", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"])
        containers = []
        if rc == 0:
            for line in out.split("\n")[1:]:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        containers.append({
                            "id": parts[0],
                            "name": parts[1],
                            "status": parts[2],
                            "ports": parts[3] if len(parts) > 3 else ""
                        })
        return {"containers": containers, "running": len([c for c in containers if "Up" in c.get("status", "")])}
    
    def _get_logs(self):
        out, err, rc = _cmd(["journalctl", "-u", "ssh", "-n", "20", "--no-pager"])
        ssh_log = out if rc == 0 else ""
        
        out, _, _ = _cmd(["journalctl", "-u", "smbd", "-n", "20", "--no-pager"])
        smb_active = _cmd(["systemctl", "is-active", "smbd"])[1] == "0"
        smb_log = out if smb_active else ""
        
        return {"ssh": ssh_log, "smb": smb_log, "docker": "", "system": ""}
    
    def _get_settings(self):
        return {
            "hostname": self._get_hostname(),
            "timezone": self._get_timezone(),
            "ntp_enabled": self._check_ntp(),
        }
    
    # ========== 控制方法 ==========
    
    def _control_service(self, data):
        action = data.get("action", "status")
        service = data.get("service", "")
        
        if not service:
            return {"error": "Service name required"}
        
        actions = {"start": "start", "stop": "stop", "restart": "restart", 
                   "enable": "enable", "disable": "disable", "status": "status"}
        
        cmd = ["systemctl", actions.get(action, "status"), service]
        out, err, rc = _cmd(cmd)
        
        _, status, _ = _cmd(["systemctl", "is-active", service])
        return {"service": service, "action": action, "status": status, "output": out, "error": err}
    
    def _mount_disk(self, data):
        device = data.get("device", "")
        if device:
            _, _, rc = _cmd(["mount", device])
            return {"device": device, "status": "mounted" if rc == 0 else "error"}
        _, _, rc = _cmd(["mount", "-a"])
        return {"status": "mounted_all" if rc == 0 else "error"}
    
    def _umount_disk(self, data):
        device = data.get("device", "")
        if device:
            _, _, rc = _cmd(["umount", device])
            return {"device": device, "status": "unmounted" if rc == 0 else "error"}
        return {"error": "Device required"}
    
    def _control_container(self, data):
        action = data.get("action", "status")
        container = data.get("container", "")
        
        if not container:
            return {"error": "Container name required"}
        
        actions = {"start": "start", "stop": "stop", "restart": "restart",
                   "pause": "pause", "unpause": "unpause", "remove": "rm -f"}
        
        cmd = ["docker", actions.get(action, "ps"), container]
        out, err, rc = _cmd(cmd)
        
        _, status, _ = _cmd(["docker", "inspect", "-f", "{{.State.Status}}", container])
        return {"container": container, "action": action, "status": status, "output": out, "error": err}
    
    def _reboot_system(self):
        threading.Thread(target=lambda: (time.sleep(2), os.system("reboot &"))).start()
        return {"status": "rebooting"}
    
    def _restart_services(self):
        _, _, rc = _cmd(["systemctl", "restart", "ssh", "smbd", "nmbd", "docker"])
        return {"status": "restarted" if rc == 0 else "error"}
    
    def _save_settings(self, data):
        hostname = data.get("hostname", "")
        if hostname:
            _cmd(["hostnamectl", "set-hostname", hostname])
        return {"status": "saved"}
    
    # ========== 辅助方法 ==========
    
    def _get_uptime_str(self):
        d = open("/proc/uptime").read().split()[0]
        s = float(d)
        days = int(s) // 86400
        hours = (int(s) % 86400) // 3600
        mins = (int(s) % 3600) // 60
        if days > 0:
            return f"{days}天 {hours}小时 {mins}分钟"
        return f"{hours}小时 {mins}分钟"
    
    def _get_cpu(self):
        with open("/proc/cpuinfo") as f:
            lines = f.readlines()
        model = ""
        cores = 0
        for line in lines:
            if line.startswith("model name"):
                model = line.split(":")[1].strip()
            if line.startswith("processor"):
                cores += 1
        return {"model": model, "cores": cores}
    
    def _get_memory(self):
        m = {}
        for line in open("/proc/meminfo"):
            p = line.split()
            k = p[0].rstrip(":")
            if k in ["MemTotal", "MemAvailable", "SwapTotal", "SwapFree"]:
                m[k] = f"{int(p[1])/1024:.0f} MB"
        return m
    
    def _get_load(self):
        with open("/proc/loadavg") as f:
            return f.read().strip()
    
    def _get_hostname(self):
        out, _, _ = _cmd(["hostname"])
        return out
    
    def _get_kernel(self):
        out, _, _ = _cmd(["uname", "-r"])
        return out
    
    def _get_timezone(self):
        out, _, _ = _cmd(["timedatectl", "show", "--property=Timezone", "--value"])
        return out
    
    def _check_ntp(self):
        out, _, _ = _cmd(["timedatectl", "show", "--property=NTP", "--value"])
        return out.lower() == "yes"
    
    def _format_size(self, bytes_size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} PB"


def idle_checker():
    """闲置检查线程"""
    while not _shutdown.is_set():
        time.sleep(10)
        if _idle():
            log("Web UI 闲置超时，自动退出")
            _shutdown.set()
            if _server_instance:
                threading.Thread(target=_server_instance.shutdown).start()


def main():
    global _server_instance
    
    log("=" * 50)
    log("WXY-OECT NAS Web UI - 按需启动模式")
    log(f"监听端口: {LISTEN_PORT}")
    log(f"闲置超时: {IDLE_TIMEOUT} 秒")
    log("=" * 50)
    
    # 写入 PID 文件
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    try:
        _server_instance = ThreadedHTTPServer(("0.0.0.0", LISTEN_PORT), NASWebUIHandler)
        
        # 启动闲置检查线程
        checker_thread = threading.Thread(target=idle_checker, daemon=True)
        checker_thread.start()
        
        log(f"Web UI 已启动，监听端口 {LISTEN_PORT}")
        _server_instance.serve_forever()
        
    except KeyboardInterrupt:
        log("收到中断信号")
    except Exception as e:
        log(f"启动失败: {e}")
    finally:
        _shutdown.set()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        log("Web UI 已退出")


def print_usage():
    print("""WXY-OECT NAS Web UI Manager

Usage:
  python3 nas-webui.py              # 启动 Web UI（默认，闲置3分钟后自动退出）
  python3 nas-webui.py start        # 启动 Web UI
  python3 nas-webui.py stop         # 停止 Web UI
  python3 nas-webui.py restart      # 重启 Web UI
  python3 nas-webui.py status       # 查看状态
  python3 nas-webui.py --no-idle    # 持久运行模式（不自动退出）

Configuration:
  IDLE_TIMEOUT=300 python3 nas-webui.py   # 设置闲置超时时间（秒）
""")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WXY-OECT NAS Web UI Manager")
    parser.add_argument("command", nargs="?", choices=["start", "stop", "restart", "status"],
                       help="命令: start, stop, restart, status")
    parser.add_argument("--no-idle", action="store_true", help="禁用闲置退出（持久运行模式）")
    parser.add_argument("--port", type=int, default=LISTEN_PORT, help=f"监听端口 (默认: {LISTEN_PORT})")
    parser.add_argument("--timeout", type=int, default=None, help=f"闲置超时时间（秒，默认: {IDLE_TIMEOUT}）")
    
    args = parser.parse_args()
    
    if args.timeout:
        IDLE_TIMEOUT = args.timeout
    if args.port:
        LISTEN_PORT = args.port
    
    if args.command == "start":
        if is_running():
            print("Web UI 已经在运行")
            sys.exit(0)
        start_webui()
    elif args.command == "stop":
        stop_webui()
    elif args.command == "restart":
        stop_webui()
        time.sleep(1)
        start_webui()
    elif args.command == "status":
        status = get_status()
        if status["running"]:
            print(f"Web UI 正在运行 (PID: {status['pid']})")
        else:
            print("Web UI 未运行")
    else:
        # 默认模式
        if args.no_idle:
            IDLE_TIMEOUT = 999999
        
        if is_running():
            print("Web UI 已经在运行，请先停止后重新启动")
            sys.exit(1)
        
        main()
