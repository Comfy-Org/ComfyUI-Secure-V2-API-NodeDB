// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  Monitor Pixaroma - the sampler                                          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ONE timer for every Monitor node on the canvas, not one each: three monitors
// must not poll the server three times a second. Nodes register here and get
// repainted from the same sample.
//
// It is a setTimeout CHAIN, never setInterval: a slow answer (nvidia-smi on a
// busy machine, or a server mid-model-load) would otherwise stack requests up
// behind each other and the interval would stop meaning anything.
//
// Nothing in here writes node.properties. The readings, the peak and the run
// state are all runtime - see the note at the top of core.mjs.

import { api } from "../../../scripts/api.js";
import { pixApiUrl } from "../shared/api_url.mjs";
import { readState, pickDevice } from "./core.mjs";
import { isLiveNode } from "../shared/live_node.mjs";


const _nodes = new Set();
let _timer = null;
let _inflight = false;
let _sample = null;      // the last successful reading
let _error = "";         // why the last attempt failed, for the face
let _running = false;    // is a workflow running right now
let _listeners = false;

// The peak is per CARD, not per node: two monitors watching the same GPU must
// agree. Keyed by the device index so a two-card machine keeps them apart.
const _peaks = new Map();

export function peakFor(st, sample) {
  const dev = pickDevice(st, sample || _sample);
  if (!dev) return null;
  return _peaks.get(devKey(dev)) || null;
}

function devKey(dev) {
  return String(dev?.index ?? dev?.name ?? 0);
}

export function lastSample() {
  return _sample;
}

export function lastError() {
  return _error;
}

export function isRunning() {
  return _running;
}

export function resetPeak(st) {
  const dev = pickDevice(st, _sample);
  if (dev) _peaks.delete(devKey(dev));
  else _peaks.clear();
  repaintAll();
}

function notePeak(sample) {
  for (const dev of sample?.devices || []) {
    if (!(dev.total > 0) || dev.used == null) continue;
    const k = devKey(dev);
    const cur = _peaks.get(k);
    if (!cur || dev.used > cur.used) {
      _peaks.set(k, { used: dev.used, total: dev.total, pct: (dev.used / dev.total) * 100 });
    }
  }
}

export function addNode(node) {
  _nodes.add(node);
  installRunListeners();
  kick();
}

export function removeNode(node) {
  _nodes.delete(node);
  if (!_nodes.size && _timer != null) {
    clearTimeout(_timer);
    _timer = null;
  }
}

// The registered Monitors that sit on a canvas the user has open. A Ctrl+C /
// Clone / Convert to Subgraph copy, and a Monitor left inside a subgraph by a
// workflow switch, never get onRemoved, so they stay in _nodes (see
// shared/live_node.mjs). Counting them kept this sampler polling after the last
// real Monitor was gone, and a copy set to a fast interval made every real one
// poll at ITS rate. MEASURED 2026-09-26: 19 stats requests in 5 s after a
// workflow switch with no Monitor anywhere, and 11 per 3 s instead of 3 for a
// real 1-second Monitor beside a 250 ms copy. Recomputed on every use (a few
// nodes, once a sample), never cached: a node can join a graph after it registers.
function liveNodes() {
  const out = [];
  for (const node of _nodes) if (isLiveNode(node)) out.push(node);
  return out;
}

function repaintAll() {
  for (const node of liveNodes()) {
    try {
      node._pmRepaint?.();
    } catch (_e) {
      /* one broken face must not stop the others updating */
    }
  }
}

/** The gap until the next sample: the fastest node wins, faster while running. */
function nextDelay() {
  const live = liveNodes();
  let ms = 5000;
  let fast = false;
  for (const node of live) {
    const st = readState(node);
    ms = Math.min(ms, Math.max(250, Number(st.interval) || 1000));
    if (st.fastWhileRunning) fast = true;
  }
  if (!live.length) return 2000;
  // A run is when the numbers actually move, so it is worth watching more
  // closely - and the peak mark is only as good as the sampling behind it.
  if (_running && fast) ms = Math.max(300, Math.round(ms / 3));
  return ms;
}

/** Every node wants to pause while hidden - one that does not keeps us awake. */
function shouldPause() {
  if (typeof document === "undefined" || !document.hidden) return false;
  const live = liveNodes();
  if (!live.length) return true;
  for (const node of live) if (!readState(node).pauseHidden) return false;
  return true;
}

async function tick() {
  _timer = null;
  // Nothing on an open canvas to show a reading: stop the chain. It starts again
  // on the next kick(), and every Monitor that appears on a canvas makes one
  // (addNode + its setup microtask); so do a run starting or ending, the browser
  // tab coming back and a Free VRAM press.
  if (!liveNodes().length) return;
  if (_inflight) {
    schedule();
    return;
  }
  // A hidden tab is not looking at the numbers, and polling in the background is
  // how a monitor earns a reputation for slowing a machine down.
  if (shouldPause()) {
    schedule();
    return;
  }
  _inflight = true;
  // A TIMEOUT IS WHAT KEEPS _inflight FROM LATCHING SHUT (review finding,
  // 2026-08-24). Without one, a request that never settles - a server wedged
  // mid-model-load, a proxy that eats the response - leaves _inflight true
  // forever: the timer keeps rescheduling, so the sampler LOOKS alive, but
  // every tick bails on the inflight guard and every monitor freezes on its
  // last reading until the page is reloaded. The abort lands in the existing
  // catch like any network error, and the next tick retries. Generous on
  // purpose: a model load can stall the server's event loop for a while, and
  // a slow answer is still an answer.
  const aborter = typeof AbortController !== "undefined" ? new AbortController() : null;
  const abortT = aborter ? setTimeout(() => aborter.abort(), 15000) : null;
  try {
    const res = await fetch(pixApiUrl("/pixaroma/api/monitor/stats"), {
      cache: "no-store",
      signal: aborter ? aborter.signal : undefined,
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    if (data && data.ok) {
      _sample = data;
      _error = "";
      notePeak(data);
    } else {
      _error = "no data";
    }
  } catch (e) {
    // Keep the last good reading on screen rather than blanking the node: a
    // single dropped request during a heavy run is normal, and a face that
    // empties itself every time reads as broken.
    _error = String(e?.message || e || "offline");
  } finally {
    if (abortT != null) clearTimeout(abortT);
    _inflight = false;
  }
  repaintAll();
  schedule();
}

function schedule() {
  if (_timer != null || !_nodes.size) return;
  _timer = setTimeout(tick, nextDelay());
}

/** Sample now (after a settings change, a Free press, or a fresh node). */
export function kick() {
  if (_timer != null) {
    clearTimeout(_timer);
    _timer = null;
  }
  tick();
}

function installRunListeners() {
  if (_listeners) return;
  _listeners = true;
  try {
    api.addEventListener("execution_start", () => {
      _running = true;
      // A new run gets a fresh peak, which is what makes the mark mean "this
      // run" rather than "some time since you opened the page".
      _peaks.clear();
      kick();
    });
    const done = () => {
      if (!_running) return;
      _running = false;
      // one last sample so the face settles on the real post-run numbers
      kick();
    };
    api.addEventListener("execution_success", done);
    api.addEventListener("execution_error", done);
    api.addEventListener("execution_interrupted", done);
    api.addEventListener("executing", (e) => {
      // older builds signal the end with a null node id
      const d = e?.detail;
      if (d == null || d?.node == null) done();
    });
  } catch (_e) {
    /* no run events: the monitor still polls, just without the run boost */
  }
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) kick();
    });
  }
}

/**
 * Ask ComfyUI to let go of memory. This is core's OWN /free route - the same
 * one behind "Free model and node cache" in ComfyUI's menu - so it can never do
 * anything ComfyUI would not do to itself.
 *
 *   unloadOnly: drop the models but keep the cached node results, so a rerun
 *               does not recompute the parts that did not change.
 *   otherwise:  also clear the cache, which is the thorough one.
 */
export async function freeMemory({ unloadOnly = false } = {}) {
  const body = unloadOnly
    ? { unload_models: true }
    : { unload_models: true, free_memory: true };
  try {
    // BARE route: fetchApi prefixes it itself, and wrapping it in pixApiUrl
    // would double-prefix (hosted-urls.md §1).
    const res = await api.fetchApi("/free", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
  } catch (e) {
    return { ok: false, message: String(e?.message || e) };
  }
  // The route only raises a flag; ComfyUI's worker acts on it when it next wakes,
  // which is immediate but not synchronous. Sample twice so the face shows the
  // memory actually going down instead of the number it had a moment ago.
  setTimeout(kick, 350);
  setTimeout(kick, 1400);
  return { ok: true };
}
