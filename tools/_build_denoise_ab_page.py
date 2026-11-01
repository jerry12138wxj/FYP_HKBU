"""Build the offline A/B listening page for the *denoise* board (step 09).

Input  04_reports/02_denoising/data/denoise_ab_manifest.json
       (+ the wav files it references under 03_outputs/_denoise_ab/)
Output 04_reports/02_denoising/html/denoise_ab_listen.html

The page is fully self-contained: the manifest is inlined into the HTML (so it
works over file:// as well as through the Range-capable listener server), and
audio is referenced by the relative paths already stored in the manifest.

Serves `start_listen.bat` -> http://127.0.0.1:8123/04_reports/02_denoising/html/denoise_ab_listen.html
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import quote

ROOT = r"E:\FYP_HKBU"
JSON_IN = os.path.join(ROOT, "04_reports", "02_denoising", "data", "denoise_ab_manifest.json")
OUT_HTML = os.path.join(ROOT, "04_reports", "02_denoising", "html", "denoise_ab_listen.html")

# Two clearly-labelled families -- the whole point of the page is that the two
# behave differently on the same input.
FAMILY = {
    "valentini": ("真实录制噪声（Valentini 测试集）",
                  "DNS-Challenge 真实噪声 + 干净语音，共 10 条。三条输入 SI-SDR 档位各取「denoiser 碾压 / mel 反超 / 中位」。",
                  "#2563eb"),
    "synth": ("冲击/瞬态噪声（合成集 · door 类）",
              "Valentini 干净语音 + freesound 冲击噪声（以敲门声为主），共 6 条。这是两个模型分野最大的场景。",
              "#b45309"),
}

CLIP_TITLE = {
    "valentini": "真实噪声",
    "synth": "冲击噪声",
}


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def js_json(obj) -> str:
    """Inline JSON safe to drop inside a <script> block."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def main() -> int:
    if not os.path.isfile(JSON_IN):
        print("[FATAL] manifest not found:", JSON_IN)
        print("        run: python tools/_export_denoise_ab.py")
        return 2
    with open(JSON_IN, encoding="utf-8") as fh:
        db = json.load(fh)

    clips = db["clips"]
    models = db["models"]

    # sanity: every referenced wav must exist (loud failure beats a page of 404s)
    missing = []
    for c in clips:
        for r in list(c["refs"]) + list(c["models"]):
            p = os.path.normpath(os.path.join(
                ROOT, "04_reports", "02_denoising", "html",
                r["src"].replace("/", os.sep)))
            if not os.path.isfile(p):
                missing.append(r["src"])
    if missing:
        print("[FATAL] %d referenced audio file(s) missing, first 5:" % len(missing))
        for m in missing[:5]:
            print("   ", m)
        return 2

    # Media URLs must be origin-absolute, not relative to the project root.
    # The page is served by tools/_denoise_live_server.py at /ab, so
    # "/media/<clip>/<file>" resolves on the same origin as the page itself --
    # relative "../../../03_outputs/..." only worked if the page happened to be
    # served by a server rooted at the project (it was not: a preview pane that
    # serves the single HTML file made every audio request 404).
    for c in clips:
        for r in list(c["refs"]) + list(c["models"]):
            r["src"] = "/media/%s/%s" % (quote(c["id"], safe=""), quote(
                r["src"].rsplit("/", 1)[-1], safe=""))

    # Inline payload: strips nothing, keeps every number traceable to the JSON.
    payload = {
        "task": db.get("task"),
        "generated": db.get("generated"),
        "play_sr": db.get("play_sr"),
        "metric_sr": db.get("metric_sr"),
        "caveats": db.get("caveats", []),
        "models": models,
        "families": {k: {"title": v[0], "note": v[1], "color": v[2]} for k, v in FAMILY.items()},
        "clips": clips,
    }

    html = TEMPLATE.replace("/*__DB__*/", js_json(payload))
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8", newline="") as fh:
        fh.write(html.replace("\n", "\r\n"))

    n_wav = sum(1 for c in clips for _ in (list(c["refs"]) + list(c["models"])))
    print("html :", OUT_HTML)
    print("clips:", len(clips), "| models/clip:", len(models), "| wav refs:", n_wav)
    print("bytes:", os.path.getsize(OUT_HTML))
    _ = esc, quote  # kept for future inline-HTML snippets
    return 0


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>降噪 A/B 试听 · Step 09（Valentini 真实噪声 + 冲击噪声）</title>
<style>
:root{
  --bg:#f6f7f9; --card:#fff; --ink:#1f2328; --dim:#6b7280; --line:#e5e7eb;
  --acc:#2563eb; --warn:#b45309; --ok:#15803d; --bad:#b91c1c; --chip:#f3f4f6;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
a{color:var(--acc)}
.wrap{max-width:1180px;margin:0 auto;padding:20px 18px 120px}
h1{font-size:20px;margin:0 0 4px}
h1 small{font-weight:400;color:var(--dim);font-size:12px;margin-left:8px}
.meta{color:var(--dim);font-size:12px;margin-bottom:14px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;margin-bottom:14px}
.panel h2{font-size:13px;margin:0 0 8px;color:var(--dim);font-weight:600;
  letter-spacing:.03em;text-transform:uppercase}
.caveats{margin:0;padding-left:18px;color:#374151;font-size:12.5px}
.caveats li{margin:3px 0}
.hl{background:#fffbeb;border-left:3px solid #f59e0b;padding:8px 10px;
  border-radius:0 6px 6px 0;font-size:12.5px;margin-top:8px}

/* ---- family + clip tabs ---- */
.fam{margin-bottom:6px}
.famhead{display:flex;align-items:center;gap:8px;margin:14px 0 8px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.famhead b{font-size:14px}
.famhead span{color:var(--dim);font-size:12px}
.tabs{display:flex;flex-wrap:wrap;gap:6px}
.tab{border:1px solid var(--line);background:#fff;border-radius:999px;
  padding:5px 11px;font-size:12.5px;cursor:pointer;color:#374151;white-space:nowrap}
.tab:hover{border-color:#c7d2fe}
.tab.on{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.tab .sd{opacity:.75;font-size:11px;margin-left:5px}

/* ---- transport ---- */
.transport{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.96);
  backdrop-filter:blur(6px);border:1px solid var(--line);border-radius:10px;
  padding:10px 12px;margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
button{font:inherit;border-radius:8px;cursor:pointer}
.btn{border:1px solid var(--line);background:#fff;padding:6px 12px}
.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn.on{background:#eef2ff;border-color:#c7d2fe;color:#3730a3;font-weight:600}
.seek{flex:1 1 220px;min-width:180px;display:flex;align-items:center;gap:8px}
.rail{position:relative;flex:1;height:6px;background:#e5e7eb;border-radius:999px;cursor:pointer}
.rail i{position:absolute;left:0;top:0;bottom:0;width:0;background:var(--acc);border-radius:999px}
.rail b{position:absolute;top:50%;width:11px;height:11px;margin:-5.5px 0 0 -5.5px;
  border-radius:50%;background:#fff;border:2px solid var(--acc);left:0}
.tm{font-variant-numeric:tabular-nums;color:var(--dim);font-size:12px;min-width:96px;text-align:right}

/* ---- clip ---- */
.cliphead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.cliphead h3{margin:0;font-size:16px}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:2px 9px;
  font-size:11.5px;color:#374151;margin-left:6px}
.why{color:var(--dim);font-size:12.5px;margin:0 0 10px}

.row{display:grid;grid-template-columns:34px 190px 1fr 92px;gap:10px;align-items:center;
  padding:7px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;margin-bottom:6px}
.row.ref{background:#fafafa}
.row.on{border-color:#c7d2fe;box-shadow:0 0 0 2px #eef2ff inset}
.row.playing{border-color:var(--acc)}
.pb{width:30px;height:30px;border-radius:50%;border:1px solid var(--line);background:#fff;
  display:flex;align-items:center;justify-content:center;font-size:12px}
.row.on .pb{border-color:var(--acc);color:var(--acc)}
.nm{font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nm .rt{font-weight:400;color:var(--dim);font-size:11.5px;display:block;margin-top:1px}
.bar{position:relative;height:6px;background:#eef0f3;border-radius:999px;overflow:hidden}
.bar i{position:absolute;left:0;top:0;bottom:0;width:0;background:#93c5fd}
.row.playing .bar i{background:var(--acc)}
.mt{display:flex;gap:4px;justify-content:flex-end;flex-wrap:wrap}
.k{font-variant-numeric:tabular-nums;font-size:11px;padding:1px 6px;border-radius:5px;
  background:var(--chip);color:#374151;white-space:nowrap}
.k.p{background:#dcfce7;color:#166534}
.k.n{background:#fee2e2;color:#991b1b}
.k.z{background:#f3f4f6;color:#6b7280}
.k.s{background:#e0e7ff;color:#3730a3}

/* ---- metrics table ---- */
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:12px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right}
th:first-child,td:first-child{text-align:left}
th{color:var(--dim);font-weight:600;background:#fafafa;position:sticky;top:0}
tr.best td{background:#f0fdf4}
.cap{color:var(--dim);font-size:11.5px;margin-top:6px}
.hidden{display:none}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:#111827;
  color:#fff;padding:9px 14px;border-radius:8px;font-size:12.5px;opacity:0;
  transition:opacity .2s;pointer-events:none;z-index:99;max-width:80vw}
.toast.on{opacity:.94}
body.blind .realname{display:none}
.codename{display:none;color:var(--acc);font-weight:700}
body.blind .codename{display:inline}
</style>
</head>
<body>
<div class="wrap">
  <h1>降噪 A/B 试听 <small>Step 09 · 板 2（denoise）</small></h1>
  <div class="meta" id="meta"></div>
  <div class="meta">想上传自己的含噪信号当场跑模型？打开
    <a href="/">实时试听页</a> · 分离模型对比：
    <a href="/04_reports/01_separation/html/listen_compare.html">分离开听页</a></div>

  <div class="panel">
    <h2>怎么听</h2>
    <ul class="caveats">
      <li><b>输入（noisy）</b>= 模型看到的信号，<b>参考（clean）</b>= 真值，只用来算指标；先听这两个建立基准。</li>
      <li>点某一行 ▶ 播放；点<b>叠听：开</b>后可以同时点亮多行 → 所有音轨在同一时间轴上对齐播放，便于 A/B。</li>
      <li>点<b>盲听：开</b>会隐藏模型名（换成随机代号），先纯听感判断，再关掉对照指标 —— 避免被名字带跑。</li>
      <li>指标口径：<b>16 kHz</b>（PESQ 只在该采样率合法）；播放音频是 <b>44.1 kHz</b> 契约率。</li>
    </ul>
    <div class="hl" id="denoiserNote"></div>
    <div class="hl" id="synthNote" style="background:#fef2f2;border-left-color:#dc2626"></div>
  </div>

  <div class="panel" id="caveatPanel"><h2>口径与可复现性声明</h2>
    <ul class="caveats" id="caveatList"></ul></div>

  <div class="transport">
    <button class="btn pri" id="pp">▶ 播放</button>
    <button class="btn" id="stop">■ 停止</button>
    <button class="btn" id="mode">▢ 叠听：关</button>
    <button class="btn" id="blind">👁 盲听：关</button>
    <button class="btn" id="loop">↻ 循环：关</button>
    <div class="seek"><div class="rail" id="rail"><i></i><b></b></div>
      <div class="tm" id="time">0:00 / 0:00</div></div>
  </div>

  <div id="host"></div>
</div>
<div class="toast" id="toast"></div>

<script>
const DB = /*__DB__*/;
const S = {cur:null, els:new Map(), active:new Set(), head:0, playing:false, sync:true,
           blind:false, loop:false, raf:null};
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmt = t => { if(!isFinite(t)||t<0) t=0; return Math.floor(t/60)+":"+String(Math.floor(t%60)).padStart(2,"0"); };

function toast(msg){ const t=$("#toast"); t.textContent=msg; t.classList.add("on");
  clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove("on"), 2600); }

function chip(v, unit, good){
  if(v===null||v===undefined) return '<span class="k z">n/a</span>';
  const s = (v>=0?"+":"") + (Math.abs(v)>=1? v.toFixed(2) : (unit==="stoi"? v.toFixed(4): v.toFixed(3)));
  const cls = (good===null||good===undefined)? "k" : (good? "k p":"k n");
  return '<span class="'+cls+'" title="'+unit+'">'+s+(unit?" "+unit:"")+'</span>';
}

/* deterministic per-clip shuffle so 盲听 codes are stable but uninformative */
function codeMap(clip){
  const keys = DB.models.map(m=>m.key);
  let seed = 2166136261;
  for(const ch of clip.id) seed = ((seed ^ ch.charCodeAt(0)) * 16777619) >>> 0;
  const rnd = n => { seed = (seed*1664525 + 1013904223) >>> 0; return seed % n; };
  const order = keys.slice();
  for(let i=order.length-1;i>0;i--){ const j=rnd(i+1); [order[i],order[j]]=[order[j],order[i]]; }
  const out = {};
  DB.models.forEach(m=>{ out[m.key] = "样本 " + String.fromCharCode(65+order.indexOf(m.key)); });
  return out;
}

function metricsHTML(mt){
  return [
    chip(mt.si_sdr_improve, "dB", mt.si_sdr_improve>0),
    chip(mt.pesq_improve, "PESQ", mt.pesq_improve>0),
    '<span class="k s" title="level_ratio">L '+mt.level_ratio.toFixed(3)+'</span>',
  ].join("");
}

function renderClip(id){
  const c = DB.clips.find(x=>x.id===id);
  if(!c) return;
  const cm = codeMap(c);
  const fam = DB.families[c.kind] || {title:c.kind,note:"",color:"#6b7280"};
  let h = `<div class="cliphead"><h3>${c.id}</h3>
    <span class="chip" style="background:${fam.color}1a;color:${fam.color}">${fam.title}</span>
    <span class="chip">${c.dur_s.toFixed(2)} s</span>
    ${c.target_snr_db!==null&&c.target_snr_db!==undefined?`<span class="chip">目标 SNR ${c.target_snr_db} dB</span>`:""}
    ${c.snr_bin?`<span class="chip">输入档 ${c.snr_bin}</span>`:""}
    ${c.noise_name?`<span class="chip">噪声：${c.noise_name}</span>`:""}</div>
    <p class="why">${c.why}</p>`;

  const rows = [];
  c.refs.forEach(r=>rows.push({r, ref:true}));
  c.models.forEach(m=>rows.push({r:m, ref:false, key:m.key, code:cm[m.key]}));

  rows.forEach(({r, ref, key, code})=>{
    const rid = c.id+"::"+(ref?r.role:key);
    const nm = ref
      ? `<span class="nm">${r.label}<span class="rt">${r.sr} Hz · ${r.ch}ch · ${r.dur.toFixed(2)} s</span></span>`
      : `<span class="nm"><span class="realname">${r.label}</span><span class="codename">${code}</span>
         <span class="rt">${r.note} · ${(r.params/1e6).toFixed(1)} M · ${r.infer_s.toFixed(2)} s</span></span>`;
    const mt = ref ? "" : metricsHTML(r.metrics);
    h += `<div class="row ${ref?"ref":""}" data-id="${rid}" data-src="${r.src}" data-dur="${r.dur}">
      <button class="pb" data-play="${rid}">▶</button>
      ${nm}
      <div class="bar"><i></i></div>
      <div class="mt">${mt}</div></div>`;
  });

  /* metric table: one row per model, best ΔSI-SDR highlighted */
  const vals = c.models.map(m=>m.metrics.si_sdr_improve);
  const best = Math.max(...vals);
  h += `<table><thead><tr><th>模型</th><th>ΔSI-SDR (dB)</th><th>ΔPESQ</th><th>ΔSTOI</th>
    <th>level_ratio</th><th>推理 (s)</th><th>参数 (M)</th></tr></thead><tbody>`;
  c.models.forEach(m=>{
    const x=m.metrics;
    h += `<tr class="${x.si_sdr_improve===best?"best":""}">
      <td>${m.label}${x.si_sdr_improve===best?' <span class="chip">ΔSDR 最高</span>':""}</td>
      <td>${x.si_sdr_improve.toFixed(2)}</td>
      <td>${x.pesq_improve===null?"n/a":x.pesq_improve.toFixed(3)}</td>
      <td>${x.stoi_improve===null?"n/a":x.stoi_improve.toFixed(4)}</td>
      <td>${x.level_ratio.toFixed(3)}</td>
      <td>${m.infer_s.toFixed(2)}</td>
      <td>${(m.params/1e6).toFixed(1)}</td></tr>`;
  });
  h += `</tbody></table>
    <p class="cap">Δ 指标 = 输出 − 输入（正 = 变好）。level_ratio = 输出 RMS / 参考 RMS（≈1 表示电平未被压缩）。
    推理时间含前端处理，未计首次模型加载（加载耗时见各模型的 note）。</p>`;

  $("#host").innerHTML = h;
  S.els.clear(); S.active.clear(); S.head=0; S.playing=false;
  updateMeta(c);
  paintUI();
}

function updateMeta(c){
  const fam = DB.families[c.kind];
  $("#meta").innerHTML = `生成于 ${DB.generated} · ${DB.clips.length} 条片段 × ${DB.models.length} 个模型
    · 指标 ${DB.metric_sr/1000} kHz / 播放 ${DB.play_sr/1000} kHz`;
  $("#synthNote").innerHTML = c.kind==="synth"
    ? "<b>注意</b>：合成集每次重合成会换噪声窗口（评测脚本用了不可复现的 hash() 种子）；本页数字是在<b>导出音频上重算</b>的，因此与报告里的 manifest 旧值不同 —— 但结论一致（mel ≈ 0 dB，denoiser +9~+22 dB）。"
    : "";
  $("#synthNote").classList.toggle("hidden", c.kind!=="synth");
}

/* ------------------------------------------------------------- audio --- */
/* Media URLs are origin-absolute ("/media/..."): they resolve on whatever
   origin served this page.  If the page was opened straight from disk (file://)
   that origin cannot serve audio, so fall back to the local app server and tell
   the user once, instead of failing silently 112 times. */
const ORIGIN_FALLBACK = "http://127.0.0.1:8123";
let warnedOrigin = false;
function failed(row, src){
  if(!warnedOrigin){
    warnedOrigin = true;
    const b = document.createElement("div");
    b.className = "hl";
    b.style.cssText += ";background:#fef2f2;border-left-color:#dc2626;margin:0 0 12px";
    b.innerHTML = "<b>音频无法加载</b>：本页需要由本地服务托管。请双击项目根目录的 "
      + "<code>start_listen.bat</code>，然后从它打印的地址打开本页（<code>/ab</code>）。"
      + " 已尝试回退到 <code>" + ORIGIN_FALLBACK + "</code>。";
    const host = $("#host"); if(host) host.parentNode.insertBefore(b, host);
  }
  row.querySelector(".nm").insertAdjacentHTML("beforeend",
    ' <span class="chip" style="background:#fee2e2;color:#991b1b">加载失败</span>');
  toast("音频加载失败：" + (src||"").split("/").pop());
}
function audioFor(id){
  let a = S.els.get(id);
  if(a) return a;
  const row = $(`.row[data-id="${CSS.escape(id)}"]`);
  if(!row) return null;
  a = new Audio(); a.preload="metadata"; a.src = row.dataset.src;
  a.addEventListener("play", ()=>row.classList.add("playing"));
  a.addEventListener("pause", ()=>row.classList.remove("playing"));
  a.addEventListener("error", ()=>{
    /* one retry against the known local server before giving up */
    if(!a.dataset.retried && !/^https?:/i.test(a.src)){
      a.dataset.retried = "1";
      a.src = ORIGIN_FALLBACK + (a.src.replace(/^file:\/\/[^/]*/i, "") || row.dataset.src);
      a.load();
      return;
    }
    failed(row, row.dataset.src);
  });
  S.els.set(id, a);
  return a;
}
function activeList(){ return [...S.active].map(id=>({id,a:audioFor(id)})).filter(x=>x.a); }

function ensureRAF(){
  if(S.raf) return;
  const tick = ()=>{
    const live = activeList().filter(x=>!x.a.paused);
    if(!live.length){ S.raf=null; S.playing=false; paintUI(); return; }
    const lead = live[0].a; S.head = lead.currentTime;
    live.forEach(({a})=>{ if(a!==lead && Math.abs(a.currentTime-S.head)>0.12) a.currentTime=S.head; });
    paintUI();
    if(S.loop && lead.duration && lead.currentTime>=lead.duration-0.06){
      S.head=0; live.forEach(({a})=>a.currentTime=0);
    }
    S.raf = requestAnimationFrame(tick);
  };
  S.raf = requestAnimationFrame(tick);
}
function playActive(){
  const list = activeList();
  if(!list.length){ toast("先点亮一行（▶）"); return; }
  list.forEach(({a})=>{ if(Math.abs(a.currentTime-S.head)>0.15) a.currentTime=S.head;
    const pr=a.play(); if(pr&&pr.catch) pr.catch(()=>{}); });
  S.playing=true; ensureRAF(); paintUI();
}
function pauseAll(){ activeList().forEach(({a})=>a.pause());
  S.playing=false; if(S.raf){cancelAnimationFrame(S.raf); S.raf=null;} paintUI(); }
function hardStop(){ pauseAll(); [...S.els.values()].forEach(a=>{ a.pause(); a.currentTime=0; });
  S.active.clear(); S.head=0;
  $$(".row").forEach(r=>{ r.classList.remove("on","playing");
    const f=r.querySelector(".bar i"); if(f) f.style.width="0%"; }); paintUI(); }
function toggleRow(id, exclusive){
  const a=audioFor(id); if(!a) return;
  if(!S.sync || exclusive){
    const wasActive = S.active.has(id) && !a.paused;
    S.active.clear();
    if(wasActive && exclusive){ a.pause(); S.playing=false; syncRows(); paintUI(); return; }
    S.active.add(id);
  } else {
    if(S.active.has(id)){ S.active.delete(id); a.pause(); syncRows(); paintUI();
      if(!activeList().some(x=>!x.a.paused)) pauseAll(); return; }
    S.active.add(id);
  }
  a.currentTime=S.head; playActive(); syncRows();
}
function syncRows(){ $$(".row").forEach(r=>r.classList.toggle("on", S.active.has(r.dataset.id))); }

function paintUI(){
  const c = DB.clips.find(x=>x.id===S.cur); const dur = c? c.dur_s : 0;
  $("#time").textContent = fmt(S.head)+" / "+fmt(dur);
  const pct = dur? (S.head/dur*100):0;
  const rail=$("#rail"); rail.querySelector("i").style.width=pct+"%";
  rail.querySelector("b").style.left=pct+"%";
  $("#pp").textContent = S.playing? "⏸ 暂停":"▶ 播放";
  activeList().forEach(({id,a})=>{
    const row=$(`.row[data-id="${CSS.escape(id)}"]`); if(!row) return;
    const d=a.duration||dur||1;
    row.querySelector(".bar i").style.width=(a.currentTime/d*100)+"%";
  });
  $("#mode").textContent = S.sync? "▣ 叠听：开":"▢ 叠听：关";
  $("#mode").classList.toggle("on", S.sync);
  $("#blind").textContent = S.blind? "👁 盲听：开":"👁 盲听：关";
  $("#blind").classList.toggle("on", S.blind);
  $("#loop").textContent = S.loop? "↻ 循环：开":"↻ 循环：关";
  $("#loop").classList.toggle("on", S.loop);
}
function seekTo(t){
  const c=DB.clips.find(x=>x.id===S.cur); const dur=c?c.dur_s:0;
  S.head=Math.max(0, Math.min(t, dur? dur-0.05:t));
  activeList().forEach(({a})=>{ a.currentTime=S.head; }); paintUI();
}

/* ------------------------------------------------------------ events --- */
document.addEventListener("click", e=>{
  const p = e.target.closest("[data-play]");
  if(p){ toggleRow(p.dataset.play, e.shiftKey||!S.sync); return; }
  const t = e.target.closest(".tab");
  if(t){ S.cur=t.dataset.id; $$(".tab").forEach(x=>x.classList.toggle("on", x===t)); renderClip(S.cur); return; }
});
document.addEventListener("keydown", e=>{
  if(e.code==="Space"){ e.preventDefault(); S.playing? pauseAll():playActive(); }
  if(e.code==="ArrowRight") seekTo(S.head+2);
  if(e.code==="ArrowLeft") seekTo(S.head-2);
});
$("#pp").onclick = ()=> S.playing? pauseAll():playActive();
$("#stop").onclick = hardStop;
$("#mode").onclick = ()=>{ S.sync=!S.sync; if(!S.sync) S.active.clear();
  syncRows(); paintUI(); };
$("#blind").onclick = ()=>{ S.blind=!S.blind; document.body.classList.toggle("blind",S.blind); paintUI(); };
$("#loop").onclick = ()=>{ S.loop=!S.loop; paintUI(); };
$("#rail").onclick = e=>{ const r=e.currentTarget.getBoundingClientRect();
  const c=DB.clips.find(x=>x.id===S.cur); const dur=c?c.dur_s:0;
  seekTo((e.clientX-r.left)/r.width*dur); };

/* -------------------------------------------------------------- boot --- */
(function boot(){
  DB.caveats.forEach(x=>{ const li=document.createElement("li"); li.textContent=x;
    $("#caveatList").appendChild(li); });
  $("#denoiserNote").innerHTML = "<b>denoiser 是 16 kHz 原生模型</b>：8 kHz 以上没有内容，听感偏「闷」是带宽上限（P19 采样率契约已修），<b>不是</b>降噪把高频削掉了。";

  const host=$("#host"); let h="";
  ["valentini","synth"].forEach(k=>{
    const fam=DB.families[k]; const cs=DB.clips.filter(c=>c.kind===k);
    if(!cs.length) return;
    h += `<div class="fam"><div class="famhead"><span class="dot" style="background:${fam.color}"></span>
      <b>${fam.title}</b><span>· ${cs.length} 条 · ${fam.note}</span></div><div class="tabs">`;
    cs.forEach(c=>{ h += `<button class="tab" data-id="${c.id}">${c.id}
      <span class="sd">${c.dur_s.toFixed(1)}s</span></button>`; });
    h += `</div></div>`;
  });
  host.innerHTML = h;

  const first=DB.clips[0].id;
  S.cur=first;
  const t=document.querySelector('.tab[data-id="'+CSS.escape(first)+'"]'); if(t) t.classList.add("on");
  renderClip(first);
  toast("提示：Shift+点击 = 单独播放该行；空格 = 播放/暂停");
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
