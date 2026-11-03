// Load Audio Pixaroma - turning a sound file into a picture of itself.
//
// The decode happens in the BROWSER rather than on the server, for three
// reasons: the file is already reachable over http, Web Audio decodes every
// format ComfyUI accepts with no Python dependency of ours, and the same
// decoded buffer is what makes real playback possible. The cost is downloading
// the file once per node, which for a song is a few megabytes over localhost.
//
// The tiny decode wrapper below is deliberately a LOCAL copy rather than an
// import from js/audio_studio/. Reaching into another editor's directory breaks
// the isolation rule in CLAUDE.md, and this is a five-line wrapper around a
// browser API, not shared logic with invariants worth centralising.

const _ctx = { value: null };
// Keyed by filename. Peaks are cheap to keep and expensive to rebuild, and a
// node re-renders on every drag frame.
const _cache = new Map();
const MAX_CACHE = 8;

function audioContext() {
  if (!_ctx.value) {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    _ctx.value = new Ctor();
  }
  return _ctx.value;
}

/** Max absolute amplitude per bucket - enough shape to find a chorus by eye. */
function computePeaks(buffer, buckets) {
  const out = new Float32Array(buckets);
  const channels = Math.min(buffer.numberOfChannels, 2);
  if (!channels || !buffer.length) return out;
  const per = buffer.length / buckets;
  for (let c = 0; c < channels; c++) {
    const data = buffer.getChannelData(c);
    for (let i = 0; i < buckets; i++) {
      const from = Math.floor(i * per);
      const to = Math.min(data.length, Math.floor((i + 1) * per));
      let peak = 0;
      // Step through long buckets rather than reading every sample: a
      // three-minute song at 48k is 8.6M samples and this runs per node.
      const stride = Math.max(1, Math.floor((to - from) / 400));
      for (let j = from; j < to; j += stride) {
        const v = data[j] < 0 ? -data[j] : data[j];
        if (v > peak) peak = v;
      }
      if (peak > out[i]) out[i] = peak;
    }
  }
  // Normalise so a quiet recording still fills the box. Guarded: an all-silent
  // file would otherwise divide by zero and paint NaN, which draws nothing at
  // all and reads as "the node is broken".
  let max = 0;
  for (let i = 0; i < buckets; i++) if (out[i] > max) max = out[i];
  if (max > 0.0001) for (let i = 0; i < buckets; i++) out[i] /= max;
  return out;
}

/**
 * { peaks, duration, error } for a file, decoded once and remembered.
 * Never rejects - a failure comes back as { error } so the face can say so.
 *
 * The cache holds the IN-FLIGHT PROMISE, not the settled result. Writing it
 * only on resolve meant every concurrent caller missed: a workflow open renders
 * the face up to five times before the first decode lands (onConfigure, two
 * queued microtasks, the ResizeObserver self-heal and the first upstream poll),
 * so one file was downloaded and decoded five times over. Measured: 5 calls, 5
 * downloads. A 3-minute song is megabytes each pass.
 *
 * A FAILURE is cached too - otherwise a bad file re-downloads on every render -
 * but only briefly. Cached forever, a transient miss (a file still being
 * written, a momentary 404) became permanent: re-picking the same file returned
 * the stale error and the only ways out were a re-upload or F5. Measured.
 */
const ERROR_TTL_MS = 10000;

export function loadPeaks(name, url, buckets = 240) {
  if (!name || !url) {
    return Promise.resolve({ peaks: null, duration: 0, error: false, empty: true });
  }
  const key = `${name}|${buckets}`;
  const hit = _cache.get(key);
  if (hit && !(hit.failedAt && Date.now() - hit.failedAt > ERROR_TTL_MS)) return hit.promise;
  if (hit) _cache.delete(key);                 // stale failure: let it try again

  const entry = { promise: null, failedAt: 0 };
  entry.promise = (async () => {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const bytes = await res.arrayBuffer();
      const ctx = audioContext();
      if (!ctx) throw new Error("no Web Audio");
      const buffer = await ctx.decodeAudioData(bytes);
      return { peaks: computePeaks(buffer, buckets), duration: buffer.duration, error: false };
    } catch (_e) {
      entry.failedAt = Date.now();
      return { peaks: null, duration: 0, error: true };
    }
  })();

  if (_cache.size >= MAX_CACHE) _cache.delete(_cache.keys().next().value);
  _cache.set(key, entry);
  return entry.promise;
}

/** Drop a file's cached peaks - call after a re-upload under the same name. */
export function forgetPeaks(name) {
  if (!name) { _cache.clear(); return; }
  for (const key of [..._cache.keys()]) {
    if (key.startsWith(`${name}|`)) _cache.delete(key);
  }
}

/**
 * Paint the waveform with the selected window highlighted.
 * `sel` is { from, to } as fractions of the whole file, or null for none.
 */
/**
 * `marks` carries the two cursors, both as fractions of the whole file:
 *   cue  where Play will start from. Always drawn, so you can see it before
 *        you press anything.
 *   play where playback has reached. Only while something is playing.
 */
export function drawWave(canvas, peaks, sel, accent, backing = 1, marks = null) {
  if (!canvas) return;
  const cssW = canvas.clientWidth || 1;
  const cssH = canvas.clientHeight || 1;
  const w = Math.max(1, Math.round(cssW * backing));
  const h = Math.max(1, Math.round(cssH * backing));
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(backing, 0, 0, backing, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  if (!peaks || !peaks.length) {
    ctx.fillStyle = "rgba(255,255,255,0.28)";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("click Upload to add a sound file", cssW / 2, cssH / 2);
    return;
  }

  const from = sel ? Math.max(0, Math.min(1, sel.from)) : 0;
  const to = sel ? Math.max(from, Math.min(1, sel.to)) : 1;
  const xFrom = from * cssW;
  const xTo = to * cssW;

  if (sel && xTo > xFrom) {
    ctx.fillStyle = "rgba(255,255,255,0.06)";
    ctx.fillRect(xFrom, 0, xTo - xFrom, cssH);
  }

  const n = peaks.length;
  const bw = cssW / n;
  const mid = cssH / 2;
  for (let i = 0; i < n; i++) {
    const x = i * bw;
    const inSel = !sel || (x + bw / 2 >= xFrom && x + bw / 2 <= xTo);
    ctx.fillStyle = inSel ? accent : "#5a5a5a";
    const bh = Math.max(1, peaks[i] * (cssH - 6));
    ctx.fillRect(x + bw * 0.15, mid - bh / 2, Math.max(0.7, bw * 0.7), bh);
  }

  // The edge handles. Deliberately drawn WIDER than a hairline and with a grip,
  // because they are drag targets: a 2px line is findable by eye but not by
  // mouse, which is exactly what made the first version feel broken.
  //
  // TWO TONES, and the reason matters: the tall bar is the selection BOUNDARY
  // so it carries the accent, while the grip is the AFFORDANCE and is white.
  // With both in accent they vanished against the orange bars inside the
  // selection - the edge was invisible exactly where you most need to find it.
  if (sel && xTo > xFrom) {
    for (const x of [xFrom, xTo]) {
      ctx.fillStyle = accent;
      ctx.fillRect(Math.max(0, Math.min(cssW - 3, x - 1.5)), 0, 3, cssH);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(Math.max(0, Math.min(cssW - 5, x - 2.5)), cssH * 0.36, 5, cssH * 0.28);
    }
  }

  // The cue: where Play will start. Drawn dimmer than the playhead, and with a
  // small tab on top so it reads as something you placed rather than an edge of
  // the selection.
  const cue = marks && marks.cue;
  if (cue != null && cue >= 0 && cue <= 1) {
    const px = cue * cssW;
    const x = Math.max(0, Math.min(cssW - 1, px));
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fillRect(x - 0.5, 0, 1, cssH);
    ctx.beginPath();
    ctx.moveTo(x - 3.5, 0);
    ctx.lineTo(x + 3.5, 0);
    ctx.lineTo(x, 5);
    ctx.closePath();
    ctx.fill();
  }

  // The playhead, only while something is actually playing.
  const playAt = marks && marks.play;
  if (playAt != null && playAt >= 0 && playAt <= 1) {
    const px = playAt * cssW;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(Math.max(0, Math.min(cssW - 2, px - 1)), 0, 2, cssH);
  }
}

/** An <audio> element pointed at the file, for the play button. */
export function makePlayer(url) {
  const el = new Audio();
  el.preload = "none";
  el.src = url;
  return el;
}
