#!/usr/bin/env python3
"""WXY-OECT NAS Web UI Manager - zero-dependency, runs on Python 3."""

import json, os, signal, subprocess, sys, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler

IDLE_TIMEOUT = 30
_last_activity = time.time()
_shutdown = threading.Event()

def _mark():
    global _last_activity
    _last_activity = time.time()

def _idle():
    return time.time() - _last_activity > IDLE_TIMEOUT

def _cmd(c):
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode
    except:
        return "", 1

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _j(self, d):
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())

    def do_GET(self):
        _mark()
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.end_headers()
            self.wfile.write(INDEX.encode())
        elif self.path == "/css":
            self.send_response(200)
            self.send_header("Content-Type","text/css")
            self.end_headers()
            self.wfile.write(CSS.encode())
        elif self.path == "/js":
            self.send_response(200)
            self.send_header("Content-Type","application/javascript")
            self.end_headers()
            self.wfile.write(JS.encode())
        elif self.path == "/status":
            self._j({
                "uptime": uptime(),
                "cpu": cpu(),
                "memory": memory(),
                "storage": storage(),
                "network": network(),
                "services": services(),
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        _mark()
        if self.path == "/restart":
            threading.Thread(target=lambda: (time.sleep(1), os.system("reboot &"))).start()
            self._j({"status":"restarting"})
        elif self.path.startswith("/service"):
            q = dict(p.split("=") for p in self.path.split("?")[1].split("&"))
            ok, _ = _cmd(["systemctl", q["action"], q["service"]])
            self._j({"status":"ok" if ok=="active" or ok=="stopped" else "error", "service":q["service"]})
        elif self.path == "/disk/mount":
            _cmd(["mount","-a"])
            self._j({"status":"ok"})
        else:
            self.send_response(404)
            self.end_headers()

def uptime():
    d = open("/proc/uptime").read().split()[0]
    s = float(d)
    return f"{int(s)//3600}h {int(s)%3600//60}m"

def cpu():
    return open("/proc/loadavg").read().strip()

def memory():
    m = {}
    for line in open("/proc/meminfo"):
        p = line.split()
        k = p[0].rstrip(":")
        if k == "MemTotal": m["total"] = f"{int(p[1])/1024:.0f} MB"
        elif k == "MemAvailable": m["available"] = f"{int(p[1])/1024:.0f} MB"
        elif k == "SwapTotal": m["swap_total"] = f"{int(p[1])/1024:.0f} MB"
        elif k == "SwapFree": m["swap_free"] = f"{int(p[1])/1024:.0f} MB"
    return m

def storage():
    out, _ = _cmd(["df","-h","--output=target,size,used,avail,pcent"])
    r = []
    for i, line in enumerate(out.split("\n")):
        if i == 0 or not line.startswith("/"): continue
        f = line.split()
        if len(f) >= 5: r.append({"mount":f[0],"size":f[1],"used":f[2],"avail":f[3],"use_pct":f[4]})
    return r

def network():
    ip, _ = _cmd(["hostname","-I"])
    out, _ = _cmd(["ip","link","show"])
    ifs = [l.split()[0].rstrip(":") for l in out.split("\n") if "@" not in l and ":" in l and l.split()[0].rstrip(":") != "lo"]
    return {"ip":ip.strip(),"interfaces":", ".join(ifs)}

def services():
    r = []
    for s in ["ssh","smbd","nmbd","docker"]:
        o, _ = _cmd(["systemctl","is-active",s])
        r.append({"name":s,"status":o,"enabled":"yes"})
    return r

def main():
    print("[NAS-WebUI] Starting on :8080")
    srv = HTTPServer(("0.0.0.0", 8080), H)
    def checker():
        while not _shutdown.is_set():
            time.sleep(5)
            if _idle():
                print("[NAS-WebUI] Idle timeout, shutting down.")
                _shutdown.set()
                threading.Thread(target=srv.shutdown).start()
    threading.Thread(target=checker, daemon=True).start()
    srv.serve_forever()

INDEX = """<!DOCTYPE html><html lang=zh-CN><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1"><title>WXY-OECT NAS</title><link rel=stylesheet href=/css></head>
<body><div id=a><header><h1>WXY-OECT NAS</h1><span id=c></span></header><main>
<section class=card><h2>系统状态</h2><div class=grid>
<div class=stat><span class=label>运行时间</span><span class=val id=uptime>--</span></div>
<div class=stat><span class=label>CPU 负载</span><span class=val id=cpu>--</span></div>
<div class=stat><span class=label>内存</span><span class=val id=memory>--</span></div>
<div class=stat><span class=label>网络</span><span class=val id=network>--</span></div>
</div></section>
<section class=card><h2>存储 <button onclick=mountDisks() class=btn-sm>挂载</button></h2>
<table><thead><tr><th>挂载点</th><th>大小</th><th>已用</th><th>可用</th><th>使用率</th></tr></thead>
<tbody id=storage-body></tbody></table></section>
<section class=card><h2>服务管理</h2><div id=services-list></div></section>
<section class=card><h2>磁盘</h2><div id=disks-list></div></section></main>
<footer><button onclick=restartNAS() class=btn-danger>重启系统</button></footer></div>
<script src=/js></script></body></html>"""

CSS = """*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0f1117;--card:#1a1d27;--accent:#4f8cff;--green:#2ecc71;--red:#e74c3c;--text:#e0e0e0;--dim:#888;font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:var(--text)}
body{background:var(--bg);min-height:100vh}
#a{max-width:900px;margin:0 auto;padding:16px}
header{display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid #333;margin-bottom:16px}
header h1{font-size:1.4rem;color:var(--accent)}
#clock{color:var(--dim);font-size:.85rem}
.card{background:var(--card);border-radius:10px;padding:16px;margin-bottom:14px}
.card h2{font-size:1rem;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.stat{background:#222633;border-radius:8px;padding:12px}
.stat .label{display:block;font-size:.75rem;color:var(--dim);margin-bottom:4px}
.stat .val{font-size:1.1rem;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;color:var(--dim);padding:6px 8px;border-bottom:1px solid #333}
td{padding:6px 8px;border-bottom:1px solid #252833}
.btn-sm{background:var(--accent);color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:.75rem;cursor:pointer}
.service-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #252833}
.badge{padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
.badge-active{background:#1a3a2a;color:var(--green)}
.badge-inactive{background:#3a1a1a;color:var(--red)}
.disk-item{padding:6px 0;font-size:.85rem}
.btn-danger{background:var(--red);color:#fff;border:none;border-radius:8px;padding:10px 24px;font-size:.9rem;width:100%;margin-top:8px}
footer{margin-top:8px}"""

JS = """let rt;
function uc(){const d=new Date();document.getElementById('clock').textContent=d.toLocaleDateString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'})+' '+d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}
async function fs(){try{const r=await fetch('/status'),s=await r.json();
document.getElementById('uptime').textContent=s.uptime;
document.getElementById('cpu').textContent=s.cpu;
document.getElementById('memory').textContent=s.memory.available+'/'+s.memory.total;
document.getElementById('network').textContent=s.network.ip;
rs(s.services);rsS(s.storage);rsD(s.devices||[])}catch(e){console.error(e)}}
function rs(svcs){const el=document.getElementById('services-list');
el.innerHTML=svcs.map(s=>{const a=s.status==='active';return'<div class=service-row><span class=service-name>'+s.name+'</span><span class="badge '+(a?'badge-active':'badge-inactive')+'">'+(a?'运行中':'已停止')+'</span></div>'}).join('')}
function rsS(items){const el=document.getElementById('storage-body');
el.innerHTML=items.map(d=>'<tr><td>'+d.mount+'</td><td>'+d.size+'</td><td>'+d.used+'</td><td>'+d.avail+'</td><td>'+d.use_pct+'</td></tr>').join('')}
function rsD(devices){const el=document.getElementById('disks-list');
el.innerHTML=devices.map(d=>'<div class=disk-item><strong>'+d.name+'</strong> '+d.size+' ['+d.type+'] '+d.mount?('-> '+d.mount:'')+'</div>').join('')}
async function mountDisks(){await fetch('/disk/mount',{method:'POST'});setTimeout(fs,1000)}
async function restartNAS(){if(!confirm('确定重启？'))return;await fetch('/restart',{method:'POST'});document.body.innerHTML='<div style=text-align:center;padding:40vh><h1>正在重启...</h1></div>'}
uc();setInterval(uc,1000);fs();rt=setInterval(fs,15000);"""

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown.set()
