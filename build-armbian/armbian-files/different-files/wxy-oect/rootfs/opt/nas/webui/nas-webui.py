#!/usr/bin/env python3
"""WXY-OECT NAS Web UI Manager - 类 iStoreOS 风格管理面板"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

IDLE_TIMEOUT = 30
_last_activity = time.time()
_shutdown = threading.Event()


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


class NASWebUIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
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
            "uptime": self._get_uptime(),
            "cpu": self._get_cpu(),
            "memory": self._get_memory(),
            "load": self._get_load(),
            "hostname": self._get_hostname(),
            "kernel": self._get_kernel(),
        }
    
    def _get_services(self):
        services = ["ssh", "smbd", "nmbd", "docker", "nginx", "syncthing", "nas-webui"]
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
        
        # 获取磁盘列表
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
        
        return {
            "ssh": ssh_log,
            "smb": smb_log,
            "docker": "",
            "system": ""
        }
    
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
        
        actions = {
            "start": "start",
            "stop": "stop",
            "restart": "restart",
            "enable": "enable",
            "disable": "disable",
            "status": "status"
        }
        
        cmd = ["systemctl", actions.get(action, "status"), service]
        out, err, rc = _cmd(cmd)
        
        _, status, _ = _cmd(["systemctl", "is-active", service])
        return {
            "service": service,
            "action": action,
            "status": status,
            "output": out,
            "error": err
        }
    
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
        
        actions = {
            "start": "start",
            "stop": "stop",
            "restart": "restart",
            "pause": "pause",
            "unpause": "unpause",
            "remove": "rm -f"
        }
        
        cmd = ["docker", actions.get(action, "ps"), container]
        out, err, rc = _cmd(cmd)
        
        _, status, _ = _cmd(["docker", "inspect", "-f", "{{.State.Status}}", container])
        return {
            "container": container,
            "action": action,
            "status": status,
            "output": out,
            "error": err
        }
    
    def _reboot_system(self):
        threading.Thread(target=lambda: (time.sleep(2), os.system("reboot &"))).start()
        return {"status": "rebooting"}
    
    def _restart_services(self):
        _, _, rc = _cmd(["systemctl", "restart", "ssh", "smbd", "nmbd", "docker", "nas-webui"])
        return {"status": "restarted" if rc == 0 else "error"}
    
    def _save_settings(self, data):
        hostname = data.get("hostname", "")
        if hostname:
            _cmd(["hostnamectl", "set-hostname", hostname])
        return {"status": "saved"}
    
    # ========== 辅助方法 ==========
    
    def _get_uptime(self):
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


def main():
    print("[NAS-WebUI] Starting on port 8080...")
    srv = HTTPServer(("0.0.0.0", 8080), NASWebUIHandler)
    
    def checker():
        while not _shutdown.is_set():
            time.sleep(5)
            if _idle():
                print("[NAS-WebUI] Idle timeout, shutting down.")
                _shutdown.set()
                threading.Thread(target=srv.shutdown).start()
    
    threading.Thread(target=checker, daemon=True).start()
    
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown.set()


# ========== HTML 界面 ==========
INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WXY-OECT NAS 管理面板</title>
    <link rel="stylesheet" href="/css">
</head>
<body>
    <div class="container">
        <aside class="sidebar">
            <div class="logo">
                <h1>WXY-OECT NAS</h1>
                <span class="version">v1.0</span>
            </div>
            <nav class="nav-menu">
                <a href="#" class="nav-item active" data-tab="dashboard"><span class="icon">📊</span> 概览</a>
                <a href="#" class="nav-item" data-tab="services"><span class="icon">⚙️</span> 服务</a>
                <a href="#" class="nav-item" data-tab="storage"><span class="icon">💾</span> 存储</a>
                <a href="#" class="nav-item" data-tab="network"><span class="icon">🌐</span> 网络</a>
                <a href="#" class="nav-item" data-tab="docker"><span class="icon">🐳</span> Docker</a>
                <a href="#" class="nav-item" data-tab="logs"><span class="icon">📝</span> 日志</a>
                <a href="#" class="nav-item" data-tab="settings"><span class="icon">🔧</span> 设置</a>
            </nav>
            <div class="sidebar-footer">
                <button class="btn-reboot" onclick="rebootSystem()">重启系统</button>
            </div>
        </aside>
        
        <main class="main-content">
            <header class="top-bar">
                <div class="status-info">
                    <span class="status-item"><span class="label">运行时间:</span> <span id="uptime">--</span></span>
                    <span class="status-item"><span class="label">主机名:</span> <span id="hostname">--</span></span>
                    <span class="status-item"><span class="label">内核:</span> <span id="kernel">--</span></span>
                </div>
                <div class="clock" id="clock">--</div>
            </header>
            
            <div id="tab-dashboard" class="tab-content active">
                <div class="cards-grid">
                    <div class="card">
                        <div class="card-header"><span class="card-icon">🖥️</span><h3>CPU</h3></div>
                        <div class="card-body"><p class="card-value" id="cpu-model">--</p><p class="card-sub" id="cpu-cores">--</p></div>
                    </div>
                    <div class="card">
                        <div class="card-header"><span class="card-icon">🧠</span><h3>内存</h3></div>
                        <div class="card-body"><p class="card-value" id="memory-used">--</p><p class="card-sub" id="memory-total">--</p></div>
                    </div>
                    <div class="card">
                        <div class="card-header"><span class="card-icon">📈</span><h3>负载</h3></div>
                        <div class="card-body"><p class="card-value" id="load">--</p><p class="card-sub">1/5/15分钟</p></div>
                    </div>
                    <div class="card">
                        <div class="card-header"><span class="card-icon">🌐</span><h3>网络 IP</h3></div>
                        <div class="card-body"><p class="card-value" id="ip-address">--</p><p class="card-sub">以太网</p></div>
                    </div>
                </div>
                
                <div class="quick-actions">
                    <h3>快捷操作</h3>
                    <div class="action-buttons">
                        <button class="btn-primary" onclick="refreshData()">🔄 刷新数据</button>
                        <button class="btn-secondary" onclick="restartAllServices()">🔁 重启服务</button>
                        <button class="btn-warning" onclick="mountDisks()">💽 挂载磁盘</button>
                    </div>
                </div>
            </div>
            
            <div id="tab-services" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>系统服务</h3><button class="btn-small" onclick="refreshServices()">刷新</button></div>
                    <div class="card-body">
                        <table class="data-table">
                            <thead><tr><th>服务名</th><th>状态</th><th>开机自启</th><th>操作</th></tr></thead>
                            <tbody id="services-table"></tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div id="tab-storage" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>磁盘分区</h3><button class="btn-small" onclick="refreshStorage()">刷新</button></div>
                    <div class="card-body">
                        <table class="data-table">
                            <thead><tr><th>设备</th><th>挂载点</th><th>大小</th><th>已用</th><th>可用</th><th>使用率</th><th>操作</th></tr></thead>
                            <tbody id="storage-table"></tbody>
                        </table>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header"><h3>物理磁盘</h3></div>
                    <div class="card-body"><div id="disk-list"></div></div>
                </div>
            </div>
            
            <div id="tab-network" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>网络接口</h3></div>
                    <div class="card-body">
                        <table class="data-table">
                            <thead><tr><th>接口</th><th>IP 地址</th><th>MAC 地址</th></tr></thead>
                            <tbody id="network-table"></tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div id="tab-docker" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>Docker 容器</h3><button class="btn-small" onclick="refreshDocker()">刷新</button></div>
                    <div class="card-body">
                        <div id="docker-status"><p>检查 Docker 状态...</p></div>
                        <table class="data-table" id="docker-table" style="display:none;">
                            <thead><tr><th>容器名</th><th>状态</th><th>端口映射</th><th>操作</th></tr></thead>
                            <tbody id="docker-list"></tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div id="tab-logs" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>系统日志</h3><button class="btn-small" onclick="refreshLogs()">刷新</button></div>
                    <div class="card-body">
                        <div class="log-tabs">
                            <button class="log-tab active" onclick="showLog('ssh')">SSH</button>
                            <button class="log-tab" onclick="showLog('smb')">Samba</button>
                        </div>
                        <pre class="log-content" id="log-content">--</pre>
                    </div>
                </div>
            </div>
            
            <div id="tab-settings" class="tab-content">
                <div class="card">
                    <div class="card-header"><h3>系统设置</h3></div>
                    <div class="card-body">
                        <div class="form-group">
                            <label>主机名</label>
                            <input type="text" id="setting-hostname" placeholder="输入主机名">
                            <button class="btn-small" onclick="saveHostname()">保存</button>
                        </div>
                        <div class="form-group"><label>时区</label><p id="setting-timezone">--</p></div>
                        <div class="form-group"><label>NTP 同步</label><p id="setting-ntp">--</p></div>
                    </div>
                </div>
            </div>
        </main>
    </div>
    <script src="/js"></script>
</body>
</html>"""


# ========== CSS 样式 ==========
STYLE_CSS = """*{margin:0;padding:0;box-sizing:border-box}
:root{--bg-primary:#0f1419;--bg-secondary:#1a1f26;--bg-card:#222832;--bg-hover:#2a313c;
--text-primary:#e8eaed;--text-secondary:#9aa0a6;--text-muted:#5f6368;--accent:#8ab4f8;
--accent-hover:#aecbfa;--success:#137333;--warning:#ea8600;--danger:#c5221f;
--border:#3c4043;--shadow:0 2px 8px rgba(0,0,0,0.3);--radius:8px;--radius-sm:4px}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg-primary);color:var(--text-primary);min-height:100vh;display:flex}
.sidebar{width:240px;background:var(--bg-secondary);border-right:1px solid var(--border);
display:flex;flex-direction:column;position:fixed;height:100vh;overflow-y:auto}
.logo{padding:24px 20px;border-bottom:1px solid var(--border)}
.logo h1{font-size:18px;font-weight:600;color:var(--text-primary)}
.logo .version{font-size:12px;color:var(--text-muted)}
.nav-menu{flex:1;padding:12px 0}
.nav-item{display:flex;align-items:center;padding:12px 20px;color:var(--text-secondary);
text-decoration:none;transition:all 0.2s}
.nav-item:hover{background:var(--bg-hover);color:var(--text-primary)}
.nav-item.active{background:var(--bg-hover);color:var(--accent);border-left:3px solid var(--accent)}
.nav-item .icon{margin-right:12px;font-size:18px}
.sidebar-footer{padding:20px;border-top:1px solid var(--border)}
.btn-reboot{width:100%;padding:10px;background:var(--danger);color:white;border:none;
border-radius:var(--radius-sm);cursor:pointer;font-size:14px}
.btn-reboot:hover{background:#d93025}
.main-content{flex:1;margin-left:240px;padding:20px;overflow-y:auto}
.top-bar{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;
background:var(--bg-card);border-radius:var(--radius);margin-bottom:20px}
.status-info{display:flex;gap:24px}
.status-item{display:flex;align-items:center;gap:8px;font-size:14px}
.status-item .label{color:var(--text-muted)}
.clock{font-size:14px;color:var(--text-secondary)}
.tab-content{display:none}
.tab-content.active{display:block}
.card{background:var(--bg-card);border-radius:var(--radius);margin-bottom:20px;box-shadow:var(--shadow)}
.card-header{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;
border-bottom:1px solid var(--border)}
.card-header h3{font-size:16px;font-weight:500}
.card-body{padding:20px}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:20px}
.cards-grid .card{margin-bottom:0}
.card-icon{font-size:24px}
.card-value{font-size:20px;font-weight:600;color:var(--text-primary);margin-bottom:4px}
.card-sub{font-size:13px;color:var(--text-muted)}
.quick-actions{background:var(--bg-card);border-radius:var(--radius);padding:20px}
.quick-actions h3{margin-bottom:16px;font-size:16px}
.action-buttons{display:flex;gap:12px;flex-wrap:wrap}
.btn-primary,.btn-secondary,.btn-warning,.btn-small{padding:8px 16px;border:none;border-radius:var(--radius-sm);
cursor:pointer;font-size:14px;transition:all 0.2s}
.btn-primary{background:var(--accent);color:var(--bg-primary)}
.btn-primary:hover{background:var(--accent-hover)}
.btn-secondary{background:var(--bg-hover);color:var(--text-primary)}
.btn-secondary:hover{background:var(--border)}
.btn-warning{background:var(--warning);color:var(--bg-primary)}
.btn-small{padding:4px 12px;font-size:12px;background:var(--bg-hover);color:var(--text-primary)}
.btn-small:hover{background:var(--border)}
.btn-small:disabled{opacity:0.5;cursor:not-allowed}
.data-table{width:100%;border-collapse:collapse;font-size:14px}
.data-table th,.data-table td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}
.data-table th{color:var(--text-muted);font-weight:500}
.data-table tr:hover{background:var(--bg-hover)}
.status-badge{display:inline-block;padding:4px 8px;border-radius:var(--radius-sm);font-size:12px;font-weight:500}
.status-badge.active{background:var(--success);color:#b2fab4}
.status-badge.inactive,.status-badge.failed{background:var(--danger);color:#ff8a80}
.form-group{margin-bottom:16px}
.form-group label{display:block;margin-bottom:8px;color:var(--text-secondary);font-size:14px}
.form-group input{width:300px;padding:8px 12px;background:var(--bg-primary);border:1px solid var(--border);
border-radius:var(--radius-sm);color:var(--text-primary);font-size:14px}
.form-group input:focus{outline:none;border-color:var(--accent)}
.log-tabs{display:flex;gap:8px;margin-bottom:12px}
.log-tab{padding:6px 12px;background:var(--bg-hover);border:none;border-radius:var(--radius-sm);
color:var(--text-secondary);cursor:pointer}
.log-tab.active{background:var(--accent);color:var(--bg-primary)}
.log-content{background:var(--bg-primary);padding:16px;border-radius:var(--radius-sm);
font-family:"SF Mono",Monaco,monospace;font-size:12px;line-height:1.6;max-height:400px;
overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.disk-item{padding:12px;background:var(--bg-primary);border-radius:var(--radius-sm);margin-bottom:8px}
.disk-item strong{color:var(--accent)}
@media(max-width:768px){.sidebar{width:60px}.sidebar .logo h1,.sidebar .nav-item span:not(.icon),
.sidebar .version{display:none}.main-content{margin-left:60px}.status-info{flex-direction:column;gap:8px}}"""


# ========== JavaScript ==========
APPLICATION_JS = """let refreshTimer=null,currentLog='ssh';
document.addEventListener('DOMContentLoaded',function(){initNavigation();updateClock();loadData();
refreshTimer=setInterval(loadData,15000)});

function initNavigation(){document.querySelectorAll('.nav-item').forEach(item=>{
item.addEventListener('click',function(e){e.preventDefault();switchTab(this.dataset.tab)})})}

function switchTab(tabName){document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
document.querySelector('.nav-item[data-tab="'+tabName+'"]').classList.add('active');
document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
document.getElementById('tab-'+tabName).classList.add('active');
loadTabData(tabName)}

function loadTabData(tab){switch(tab){case'dashboard':loadData();break;case'services':refreshServices();break;
case'storage':refreshStorage();break;case'network':refreshNetwork();break;case'docker':refreshDocker();break;
case'logs':refreshLogs();break;case'settings':loadSettings();break}}

function updateClock(){const n=new Date();
document.getElementById('clock').textContent=n.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',
day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
setInterval(updateClock,1000);

async function loadData(){try{const r=await fetch('/api/status'),d=await r.json();
document.getElementById('uptime').textContent=d.uptime;
document.getElementById('hostname').textContent=d.hostname;
document.getElementById('kernel').textContent=d.kernel;
document.getElementById('cpu-model').textContent=d.cpu.model||'--';
document.getElementById('cpu-cores').textContent=(d.cpu.cores||0)+' 核心';
const memUsed=parseInt(d.memory['MemTotal'])-parseInt(d.memory['MemAvailable']);
document.getElementById('memory-used').textContent=(memUsed/1024).toFixed(0)+' MB';
document.getElementById('memory-total').textContent=(parseInt(d.memory['MemTotal'])/1024).toFixed(0)+' MB 总计';
document.getElementById('load').textContent=d.load;
const nr=await fetch('/api/network'),nd=await nr.json();
document.getElementById('ip-address').textContent=nd.ip||'--'}catch(e){console.error(e)}}

function refreshData(){loadData()}
function restartAllServices(){if(!confirm('确定重启所有服务?'))return;
fetch('/api/restart',{method:'POST'}).then(()=>setTimeout(refreshServices,2000))}
function mountDisks(){fetch('/api/disk/mount',{method:'POST',headers:{"Content-Type":"application/json"},
body:JSON.stringify({})}).then(()=>setTimeout(refreshStorage,1000))}
function rebootSystem(){if(!confirm('确定重启系统?'))return;
fetch('/api/reboot',{method:'POST'}).then(()=>{document.body.innerHTML='<div style="text-align:center;padding:40vh"><h1>正在重启...</h1></div>'})}

async function refreshServices(){try{const r=await fetch('/api/services'),d=await r.json();
const t=document.getElementById('services-table');
t.innerHTML=d.services.map(s=>`<tr><td>${s.name}</td>
<td><span class="status-badge ${s.status}">${s.status==='active'?'运行中':'已停止'}</span></td>
<td>${s.enabled?'是':'否'}</td>
<td><button class="btn-small" onclick="controlService('${s.name}','start')" ${s.status==='active'?'disabled':''}>启动</button>
<button class="btn-small" onclick="controlService('${s.name}','stop')" ${s.status!=='active'?'disabled':''}>停止</button>
<button class="btn-small" onclick="controlService('${s.name}','restart')">重启</button></td></tr>`).join('')}
catch(e){console.error(e)}}

async function controlService(name,action){try{await fetch('/api/service/control',{method:'POST',
headers:{"Content-Type":"application/json"},body:JSON.stringify({service:name,action:action})});
setTimeout(refreshServices,1000)}catch(e){alert('操作失败')}}

async function refreshStorage(){try{const r=await fetch('/api/storage'),d=await r.json();
const t=document.getElementById('storage-table');
t.innerHTML=d.partitions.map(p=>`<tr><td>${p.device}</td><td>${p.mount||'-'}</td><td>${p.size}</td>
<td>${p.used}</td><td>${p.avail}</td><td>${p.use_pct}</td>
<td>${p.mount?`<button class="btn-small" onclick="umountDisk('${p.device}')">卸载</button>`:'-'}</td></tr>`).join('');
const dl=document.getElementById('disk-list');
dl.innerHTML=d.disks.map(dd=>`<div class="disk-item"><strong>${dd.name}</strong> ${dd.size} [${dd.model}] ${dd.rotational}</div>`).join('')}
catch(e){console.error(e)}}

async function mountDisk(device){try{await fetch('/api/disk/mount',{method:'POST',
headers:{"Content-Type":"application/json"},body:JSON.stringify({device:device})});refreshStorage()}
catch(e){alert('挂载失败')}}
async function umountDisk(device){try{await fetch('/api/disk/umount',{method:'POST',
headers:{"Content-Type":"application/json"},body:JSON.stringify({device:device})});refreshStorage()}
catch(e){alert('卸载失败')}}

async function refreshNetwork(){try{const r=await fetch('/api/network'),d=await r.json();
const t=document.getElementById('network-table');
t.innerHTML=d.interfaces.map(i=>`<tr><td>${i.name}</td><td>${i.ip}</td><td>${i.mac}</td></tr>`).join('')}
catch(e){console.error(e)}}

async function refreshDocker(){try{const r=await fetch('/api/docker'),d=await r.json();
const s=document.getElementById('docker-status'),t=document.getElementById('docker-table');
if(!d.containers||d.containers.length===0){s.innerHTML='<p>Docker 未运行或没有容器</p>';t.style.display='none';return}
s.style.display='none';t.style.display='table';
const dl=document.getElementById('docker-list');
dl.innerHTML=d.containers.map(c=>`<tr><td>${c.name}</td><td>${c.status}</td><td>${c.ports||'-'}</td>
<td><button class="btn-small" onclick="controlContainer('${c.name}','start')" ${c.status.includes('Up')?'disabled':''}>启动</button>
<button class="btn-small" onclick="controlContainer('${c.name}','stop')" ${!c.status.includes('Up')?'disabled':''}>停止</button>
<button class="btn-small" onclick="controlContainer('${c.name}','restart')">重启</button>
<button class="btn-small" onclick="controlContainer('${c.name}','remove')" style="background:var(--danger)">删除</button></td></tr>`).join('')}
catch(e){document.getElementById('docker-status').innerHTML='<p>Docker 未安装</p>'}}

async function controlContainer(name,action){try{await fetch('/api/container/control',{method:'POST',
headers:{"Content-Type":"application/json"},body:JSON.stringify({container:name,action:action})});
setTimeout(refreshDocker,1000)}catch(e){alert('操作失败')}}

async function refreshLogs(){try{const r=await fetch('/api/logs'),d=await r.json();
document.getElementById('log-content').textContent=d[currentLog]||'暂无日志'}catch(e){
document.getElementById('log-content').textContent='加载失败'}}

function showLog(type){currentLog=type;document.querySelectorAll('.log-tab').forEach(t=>t.classList.remove('active'));
event.target.classList.add('active');refreshLogs()}

async function loadSettings(){try{const r=await fetch('/api/settings'),d=await r.json();
document.getElementById('setting-hostname').value=d.hostname;
document.getElementById('setting-timezone').textContent=d.timezone;
document.getElementById('setting-ntp').textContent=d.ntp_enabled?'已启用':'未启用'}catch(e){console.error(e)}}

async function saveHostname(){const h=document.getElementById('setting-hostname').value;if(!h)return;
try{await fetch('/api/settings/save',{method:'POST',headers:{"Content-Type":"application/json"},
body:JSON.stringify({hostname:h})});alert('主机名已更新，请重启后生效')}catch(e){alert('保存失败')}}"""


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown.set()
