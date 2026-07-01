// WXY-OECT NAS Web UI Client
let refreshTimer;

function updateClock(){
  const d=new Date();
  document.getElementById('clock').textContent=
    d.toLocaleDateString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'})+' '+
    d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

async function fetchStatus(){
  try{
    const r=await fetch('/status');
    const s=await r.json();
    document.getElementById('uptime').textContent=s.uptime;
    document.getElementById('cpu').textContent=s.cpu;
    document.getElementById('memory').textContent=s.memory.available+'/'+s.memory.total;
    document.getElementById('network').textContent=s.network.ip;
    renderServices(s.services);
    renderStorage(s.storage);
    renderDisks(s.devices||[]);
  }catch(e){console.error(e)}
}

function renderServices(svcs){
  const el=document.getElementById('services-list');
  if(!svcs.length){el.innerHTML='<p style="color:#888">暂无服务</p>';return}
  el.innerHTML=svcs.map(s=>{
    const active=s.status==='active';
    return `<div class="service-row">
      <span class="service-name">${s.name}</span>
      <span class="badge ${active?'badge-active':'badge-inactive'}">${active?'运行中':'已停止'}</span>
      ${!active?`<button class="btn-sm" onclick="toggleService('${s.name}','start')">启动</button>`:''}
    </div>`;
  }).join('');
}

function renderStorage(items){
  const el=document.getElementById('storage-body');
  if(!items.length){el.innerHTML='<tr><td colspan="5" style="color:#888">无数据</td></tr>';return}
  el.innerHTML=items.map(d=>`<tr>
    <td>${d.mount}</td><td>${d.size}</td><td>${d.used}</td><td>${d.avail}</td>
    <td><progress value="${parseInt(d.use_pct)}" max="100" style="width:60px"></progress>${d.use_pct}</td>
  </tr>`).join('');
}

function renderDisks(devices){
  const el=document.getElementById('disks-list');
  if(!devices.length){el.innerHTML='<p style="color:#888">无磁盘</p>';return}
  el.innerHTML=devices.map(d=>`<div class="disk-item">
    <strong>${d.name}</strong> ${d.size} [${d.type}] ${d.mount?'-> '+d.mount:''}
  </div>`).join('');
}

async function toggleService(name,action){
  await fetch(`/service?service=${name}&action=${action}`);
  setTimeout(fetchStatus,1000);
}

async function mountDisks(){
  await fetch('/disk/mount','{method:"POST"}');
  setTimeout(fetchStatus,1000);
}

async function restartNAS(){
  if(!confirm('确定重启系统？'))return;
  await fetch('/restart',{method:'POST'});
  document.body.innerHTML='<div style="text-align:center;padding:40"><h1>正在重启...</h1><p>请稍候</p></div>';
}

updateClock();
setInterval(updateClock,1000);
fetchStatus();
refreshTimer=setInterval(fetchStatus,15000);