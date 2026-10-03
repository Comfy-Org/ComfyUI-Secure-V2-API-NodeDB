import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// ===== 辉光管样式(7 色主题, CSS 变量)=====
const style = document.createElement("style");
style.textContent = `
.nixie-node-body{--nc:#ff7a1a;--ng1:#ff4d00;--ng2:#e63a00;--nb:#331407;--nborder:#4a3520;--nlabel:#c98a4a;--nshadow:rgba(255,110,0,.18);background:linear-gradient(180deg,rgba(26,20,14,.95),rgba(11,8,5,.95));border:2px solid var(--nborder);border-radius:8px;padding:6px 8px 7px;box-shadow:inset 0 0 16px var(--nshadow);box-sizing:border-box;pointer-events:auto;overflow:hidden}
.nixie-node-body[data-theme="green"]{--nc:#52ff6e;--ng1:#1bff48;--ng2:#00d13a;--nb:#0d3314;--nborder:#1e4a2c;--nlabel:#5ec98a;--nshadow:rgba(80,255,120,.18)}
.nixie-node-body[data-theme="blue"]{--nc:#4da6ff;--ng1:#1a7bff;--ng2:#0059e6;--nb:#0d1f33;--nborder:#1e3a4a;--nlabel:#5ea9c9;--nshadow:rgba(80,160,255,.18)}
.nixie-node-body[data-theme="amber"]{--nc:#ffb52e;--ng1:#ff9200;--ng2:#e66f00;--nb:#33240d;--nborder:#4a3a1e;--nlabel:#c9a75e;--nshadow:rgba(255,170,60,.18)}
.nixie-node-body[data-theme="purple"]{--nc:#c77dff;--ng1:#a44dff;--ng2:#7a1ae6;--nb:#251233;--nborder:#3a1e4a;--nlabel:#a56ec9;--nshadow:rgba(180,110,255,.18)}
.nixie-node-body[data-theme="cyan"]{--nc:#3affd4;--ng1:#00e6b0;--ng2:#00b38a;--nb:#0d332b;--nborder:#1e4a40;--nlabel:#5ec9b4;--nshadow:rgba(60,255,210,.18)}
.nixie-node-body[data-theme="white"]{--nc:#f2f2f2;--ng1:#cfcfff;--ng2:#9f9fe6;--nb:#1a1a26;--nborder:#33334a;--nlabel:#9a9ac9;--nshadow:rgba(200,200,255,.18)}
.nixie-row{display:flex;align-items:center;justify-content:center;gap:2px;white-space:nowrap}
.nixie-clock-row{margin-bottom:5px}
.nixie-label{color:var(--nlabel);font-size:8px;letter-spacing:2px;text-align:center;margin:1px 0 4px;text-transform:uppercase;font-family:"Consolas","Courier New",monospace}
.nixie-tube{position:relative;background:radial-gradient(circle at 50% 28%,var(--nb) 0%,#170803 55%,#0a0402 100%);border-radius:4px;padding:2px 3px 3px;min-width:1.02em;text-align:center;color:var(--nc);font-weight:700;line-height:1;font-family:"Consolas","Courier New",monospace;text-shadow:0 0 5px var(--nc),0 0 11px var(--ng1),0 0 22px var(--ng2);box-shadow:inset 0 0 8px var(--nshadow)}
.nixie-tube::before{content:"";position:absolute;left:12%;right:12%;top:0;height:2px;background:rgba(120,60,20,.5);border-radius:2px}
.nixie-tube::after{content:"";position:absolute;left:18%;right:18%;bottom:-1px;height:2px;background:repeating-linear-gradient(90deg,rgba(140,80,30,.6) 0 2px,transparent 2px 4px)}
.nixie-tube.clock{font-size:13px;padding:2px 3px 3px}
.nixie-tube.timer{font-size:21px;min-width:1.1em;padding:3px 4px 4px}
.nixie-sep{color:var(--nc);font-weight:700;font-family:"Consolas","Courier New",monospace;text-shadow:0 0 6px var(--nc),0 0 12px var(--ng1);padding:0 1px;animation:nixie-blink 1s steps(1) infinite}
.nixie-sep.clock{font-size:13px}
.nixie-sep.timer{font-size:17px}
.nixie-sep.off{animation:none;opacity:.35}
@keyframes nixie-blink{50%{opacity:.15}}
#nixie-timer.paused .nixie-sep{animation:none;opacity:.35}
#nixie-timer.paused .nixie-tube{opacity:.7}
`;
document.head.appendChild(style);

// ===== 基准尺寸(节点宽 320 时 scale=1)=====
const BASE_W = 320;
const BASE_H = 104;
const TITLE_H = 34;

// ===== 颜色选项 -> 主题 key =====
const THEME_MAP = {
  "红色": "red", "绿色": "green", "蓝色": "blue", "琥珀": "amber",
  "紫色": "purple", "青色": "cyan", "白色": "white",
};

function applyTheme(parts, label) {
  parts.panelEl.dataset.theme = THEME_MAP[label] || "red";
}

// ===== 辉光管渲染 =====
function makeTubes(text, cls) {
  const frag = document.createDocumentFragment();
  for (const ch of text) {
    if (ch === " ") { frag.appendChild(document.createTextNode(" ")); continue; }
    if (ch === ":") {
      const s = document.createElement("span");
      s.className = "nixie-sep" + (cls ? " " + cls : "");
      s.textContent = ":";
      frag.appendChild(s);
      continue;
    }
    if (ch === "-" || ch === ".") {
      const s = document.createElement("span");
      s.className = "nixie-sep off" + (cls ? " " + cls : "");
      s.textContent = ch;
      frag.appendChild(s);
      continue;
    }
    const t = document.createElement("span");
    t.className = "nixie-tube" + (cls ? " " + cls : "");
    t.textContent = ch;
    frag.appendChild(t);
  }
  return frag;
}

// ===== 全局计时状态 =====
let running = false;
let startTs = 0;
let elapsed = 0; // 结束后保留的耗时
const instances = new Set(); // { clockEl, timerEl, panelEl }

function startTimer() {
  running = true;
  startTs = performance.now();
  elapsed = 0; // 下次推理重新计时
  for (const inst of instances) inst.panelEl.classList.remove("paused");
}

function stopTimer() {
  if (!running) return;
  running = false;
  elapsed = performance.now() - startTs; // 保留本次耗时,不清零
  for (const inst of instances) inst.panelEl.classList.add("paused");
}

function tick() {
  const now = new Date();
  const p = (n) => String(n).padStart(2, "0");
  const clockText = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}-` +
                    `${p(now.getHours())}:${p(now.getMinutes())}:${p(now.getSeconds())}`;
  const total = Math.floor(running ? performance.now() - startTs : elapsed);
  const s = Math.floor(total / 1000);
  const timerText = (running || elapsed > 0 || startTs > 0)
    ? `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`
    : "00:00:00";
  for (const inst of instances) {
    inst.clockEl.replaceChildren(makeTubes(clockText, "clock"));
    inst.timerEl.replaceChildren(makeTubes(timerText, "timer"));
  }
}

// ===== 多语言 =====
const TRANSLATIONS = {
  zh: { clock: "世界时钟", timer: "推理耗时" },
  en: { clock: "World Clock", timer: "Inference Time" },
  ja: { clock: "ワールドクロック", timer: "推論時間" },
  ko: { clock: "월드 시계", timer: "추론 시간" },
  ru: { clock: "Мировые часы", timer: "Время вывода" },
  de: { clock: "Weltuhr", timer: "Inferenzzeit" },
  fr: { clock: "Horloge", timer: "Temps d'inférence" },
  es: { clock: "Reloj mundial", timer: "Tiempo de inferencia" },
  pt: { clock: "Relógio mundial", timer: "Tempo de inferência" },
  it: { clock: "Orologio", timer: "Tempo di inferenza" },
};
const FALLBACK = TRANSLATIONS.en;

function getLocale() {
  try {
    const v = app?.ui?.settings?.getSettingValue?.("Comfy.Locale");
    if (v) return String(v).split("-")[0].toLowerCase();
  } catch {}
  try {
    const g = window?.comfyAPI?.app?.Ui?.global?.locale?.value;
    if (g) return String(g).split("-")[0].toLowerCase();
  } catch {}
  return "en";
}

let lastLocale = null;
function applyLang() {
  const loc = getLocale();
  if (loc === lastLocale) return;
  lastLocale = loc;
  const tr = TRANSLATIONS[loc] ?? FALLBACK;
  for (const inst of instances) {
    for (const el of inst.panelEl.querySelectorAll("[data-i18n]")) {
      const k = el.dataset.i18n;
      if (tr[k] !== undefined) el.textContent = tr[k];
    }
  }
}

// ===== 构建节点内嵌面板 =====
function buildPanel() {
  const panel = document.createElement("div");
  panel.className = "nixie-node-body";
  panel.id = "nixie-timer";
  panel.dataset.theme = "red";
  panel.innerHTML = `
    <div class="nixie-label" data-i18n="clock"></div>
    <div class="nixie-row nixie-clock-row"></div>
    <div class="nixie-label" style="margin-top:4px" data-i18n="timer"></div>
    <div class="nixie-row"></div>`;
  return {
    panelEl: panel,
    clockEl: panel.querySelector(".nixie-clock-row"),
    timerEl: panel.querySelector(".nixie-row:last-child"),
  };
}

// ===== 注册扩展 =====
app.registerExtension({
  name: "NixieTimerNode",
  async setup() {
    // 计时钩子:点击 Queue 开始,队列清空/出错停止
    const origQueuePrompt = app.queuePrompt.bind(app);
    app.queuePrompt = function (...args) {
      startTimer();
      return origQueuePrompt(...args);
    };
    api.addEventListener("status", ({ detail }) => {
      if (running && detail?.exec_info?.queue_remaining === 0) stopTimer();
    });
    api.addEventListener("execution_error", () => stopTimer());

    // 语言:初始读取一次 + 监听设置变化事件(不轮询)
    try {
      app.ui.settings?.addEventListener?.("settingsChanged", () => applyLang());
    } catch {}
    applyLang();

    setInterval(tick, 100);
    tick();
  },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "NixieTimer") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function (...args) {
      const res = onNodeCreated?.apply(this, args);

      const parts = buildPanel();
      const widget = this.addDOMWidget("display", "html", parts.panelEl, {
        hideOnZoom: false,
        serialize: false,
      });
      widget.computeSize = () => [this.size?.[0] ?? BASE_W, BASE_H];
      this.nixieInst = parts;
      instances.add(parts);
      applyLang(); // 新节点立即按当前语言填充文案

      // 颜色选择联动
      const colorWidget = this.widgets?.find((w) => w.name === "tube_color");
      if (colorWidget) {
        this.tubeColorWidget = colorWidget;
        colorWidget.callback = () => applyTheme(parts, colorWidget.value);
        applyTheme(parts, colorWidget.value);
      }

      // ---- 自动等比缩放:监听容器尺寸,transform scale 面板 ----
      // 注意:宽度必须以节点自身 size[0] 为准(容器 clientWidth = 节点宽-边框,
      // 若用容器宽会导致每轮-2px 的递减循环,节点越缩越小)
      let applying = false;
      const applyScale = () => {
        if (applying) return;
        applying = true;
        requestAnimationFrame(() => {
          try {
            const w = Math.max(180, this.size[0] || BASE_W);   // 节点宽(用户拖拽目标)
            const c = parts.panelEl.parentElement;
            const cw = c && c.clientWidth > 0 ? c.clientWidth : w; // 实际可用宽(节点宽-边框)
            const scale = cw / BASE_W;                            // 按可用宽缩放,渲染正好贴容器,不溢出
            const h = Math.max(BASE_H, Math.round(BASE_H * scale));
            parts.panelEl.style.transform = `scale(${scale})`;
            parts.panelEl.style.transformOrigin = "top left";
            parts.panelEl.style.width = BASE_W + "px";
            parts.panelEl.style.height = BASE_H + "px";
            widget.computeSize = () => [w, h];
            if (this.size[0] !== w || this.size[1] !== TITLE_H + h) {
              this.setSize([w, TITLE_H + h]);
            }
          } finally {
            applying = false;
          }
        });
      };

      const ro = new ResizeObserver(applyScale);
      const startObserve = () => {
        const c = parts.panelEl.parentElement;
        if (c) { ro.observe(c); applyScale(); }
        else setTimeout(startObserve, 100);
      };
      setTimeout(startObserve, 50);

      // 初始尺寸
      this.size = [BASE_W, TITLE_H + BASE_H];
      this.setSize(this.size);

      // workflow 加载/复制后重新应用主题
      const onConfigure = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function (...a) {
        const r = onConfigure?.apply(this, a);
        if (this.tubeColorWidget) applyTheme(parts, this.tubeColorWidget.value);
        return r;
      };

      // 节点删除时清理
      const onRemoved = this.onRemoved;
      this.onRemoved = function (...a) {
        ro.disconnect();
        instances.delete(parts);
        return onRemoved?.apply(this, a);
      };
      return res;
    };
  },
});
