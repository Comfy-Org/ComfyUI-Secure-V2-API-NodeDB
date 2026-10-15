/**
 * The secure extension host: ONE shared sandboxed iframe, ONE worker per pack.
 *
 * Installed into ComfyUI_frontend via the generic `provideExtensionHost` seam,
 * so core knows nothing about any of this.
 *
 * Arrangement (measured — see docs/frontend_sandbox_design.md §D0):
 *
 *     <iframe sandbox="allow-scripts">        one, opaque origin, ~124MB once
 *       ├── Worker(pack A)                    ~1.8MB each
 *       ├── Worker(pack B)
 *       └── …
 *
 * The iframe provides the opaque origin (no cookies, no host storage, no
 * credentialed API calls). The per-pack worker provides the realm/thread
 * boundary that makes per-pack capability grants enforceable.
 */

const SANDBOX_HTML = `<!doctype html><meta charset="utf-8"><script type="module">
const workers = new Map()
addEventListener('message', async (e) => {
  const m = e.data
  if (!m || !m.__sn) return
  if (m.t === 'spawn') {
    try {
      // The bootstrap arrives as SOURCE, not a URL. This document has an
      // opaque origin, so it cannot create a Worker from a cross-origin script
      // URL — a blob: URL minted here inherits this opaque origin, which is
      // both what works and what we want.
      const blobUrl = URL.createObjectURL(
        new Blob([m.bootstrapSource], { type: 'text/javascript' }))
      // The pack is imported by its real http URL when the asset origin
      // answers CORS — every module fetch from this opaque origin is
      // cross-origin — because a URL import is what lets a MULTI-FILE pack
      // resolve its relative imports. The entry SOURCE still crosses as a
      // fallback: a blob: minted here is same-origin to this document, so a
      // single-file pack loads even against a server with no CORS headers.
      const packBlobUrl = m.packSource != null
        ? URL.createObjectURL(new Blob([m.packSource], { type: 'text/javascript' }))
        : null
      // CLASSIC worker, deliberately: Chromium refuses to start a *module*
      // worker from a blob: URL at an opaque origin (Firefox and WebKit allow
      // it). The bootstrap therefore uses no static imports and reaches the
      // pack via dynamic import(), which works in classic workers everywhere.
      const w = new Worker(blobUrl)
      workers.set(m.pack, w)
      w.onmessage = (ev) => {
        const bitmap = ev.data?.bitmap
        const transfer = (ev.data?.t === 'nodecanvasframe' || ev.data?.t === 'canvasbitmap') &&
          bitmap instanceof ImageBitmap ? [bitmap] : []
        try {
          parent.postMessage(
            { __sn: true, t: 'from', pack: m.pack, payload: ev.data }, '*', transfer)
        } catch (error) {
          for (const item of transfer) item.close()
          throw error
        }
      }
      w.onerror = (ev) => parent.postMessage(
        { __sn: true, t: 'error', pack: m.pack, error: String(ev.message || ev) }, '*')
      w.postMessage({ t: 'init', packUrl: m.packUrl, packBlobUrl, name: m.pack,
                      capabilities: m.capabilities, boot: m.boot })
      parent.postMessage({ __sn: true, t: 'spawned', pack: m.pack }, '*')
    } catch (err) {
      parent.postMessage({ __sn: true, t: 'error', pack: m.pack,
                           error: String(err && err.message || err) }, '*')
    }
  }
  if (m.t === 'to') {
    const w = workers.get(m.pack)
    if (w) w.postMessage(m.payload)
  }
  if (m.t === 'kill') {
    const w = workers.get(m.pack)
    if (w) { w.terminate(); workers.delete(m.pack) }
  }
})
parent.postMessage({ __sn: true, t: 'ready' }, '*')
<\/script>`

export class SandboxHost {
  /**
   * @param bootstrapUrl  URL of the guest bootstrap module. Fetched by the HOST
   *   (same-origin) and passed into the sandbox as source — an opaque-origin
   *   document cannot construct a Worker from a cross-origin URL.
   */
  constructor({ bootstrapUrl, onPackMessage, onError, loadTimeoutMs = 20000 } = {}) {
    this.bootstrapUrl = bootstrapUrl
    this.loadTimeoutMs = loadTimeoutMs
    this._bootstrapSource = null
    this.onPackMessage = onPackMessage || (() => {})
    this.onError = onError || ((pack, err) =>
      console.error(`[secure-nodes] pack '${pack}':`, err))
    this._iframe = null
    this._ready = null
    this._packs = new Map()   // pack -> { resolveSpawn }
  }

  /** Create the single shared iframe (idempotent). */
  ensureIframe() {
    if (this._ready) return this._ready
    this._ready = new Promise((resolve, reject) => {
      const f = document.createElement('iframe')
      // allow-scripts only: opaque origin. NEVER add allow-same-origin —
      // that would hand the pack the host's origin and defeat the boundary.
      f.setAttribute('sandbox', 'allow-scripts')
      f.setAttribute('aria-hidden', 'true')
      f.style.display = 'none'
      f.srcdoc = SANDBOX_HTML

      const onMsg = (e) => {
        const m = e.data
        if (!m || !m.__sn) return
        if (e.source !== f.contentWindow) return
        if (m.t === 'ready') { resolve(f); return }
        if (m.t === 'spawned') {
          const rec = this._packs.get(m.pack)
          if (rec && rec.resolveSpawn) rec.resolveSpawn()
          return
        }
        if (m.t === 'error') {
          // A worker that dies must not leave any pending load() hanging.
          const rec = this._packs.get(m.pack)
          if (rec) {
            for (const [, pendingLoad] of rec.loads) {
              pendingLoad.reject(new Error(m.error))
            }
            rec.loads.clear()
          }
          this.onError(m.pack, m.error)
          return
        }
        if (m.t === 'from') {
          // Module-evaluation completion is intercepted here rather than passed
          // through: `load()` must not resolve until the module's top-level
          // code has run, because `comfy.defs.extend` registrations are only
          // applied when node types are registered — which happens right after
          // loadExtensions() returns. Resolving early loses every hook.
          //
          // Keyed by URL: one pack is one worker, but a pack ships many entry
          // modules (KJNodes ships 26), each with its own pending load.
          const p = m.payload
          const rec = this._packs.get(m.pack)
          if (p && (p.t === 'loaded' || p.t === 'loaderror')) {
            const pendingLoad = rec && rec.loads.get(p.url)
            if (pendingLoad) {
              rec.loads.delete(p.url)
              p.t === 'loaded'
                ? pendingLoad.resolve(p)
                : pendingLoad.reject(new Error(p.error))
            }
            return
          }
          this.onPackMessage(m.pack, p)
        }
      }
      window.addEventListener('message', onMsg)
      this._onMsg = onMsg
      this._iframe = f
      document.body.appendChild(f)
      setTimeout(() => reject(new Error('sandbox iframe did not become ready')), 15000)
    })
    return this._ready
  }

  async _bootstrap() {
    if (this._bootstrapSource == null) {
      const r = await fetch(this.bootstrapUrl)
      if (!r.ok) throw new Error(`bootstrap fetch failed: ${r.status}`)
      this._bootstrapSource = await r.text()
    }
    return this._bootstrapSource
  }

  /**
   * Start one worker for a pack and load its entry module inside it.
   *
   * Resolves only once the pack's module has finished evaluating, so this is a
   * drop-in for the `await import(url)` it replaces (see the `loaded` handling
   * in ensureIframe). Rejects if the pack throws while loading.
   */
  /**
   * Load one entry module into a pack's worker, spawning the worker on the
   * pack's first entry. One pack is ONE worker: a pack that ships many entry
   * modules shares a single `comfy`, registration table and capability grant,
   * which is also what lets its modules import each other.
   */
  async loadPack(pack, packUrl, capabilities = [], packSource = null,
                 boot = {}) {
    const [f, bootstrapSource] = await Promise.all([
      this.ensureIframe(), this._bootstrap(),
    ])

    let rec = this._packs.get(pack)
    const trackLoad = () => {
      const p = {}
      p.promise = new Promise((res, rej) => { p.resolve = res; p.reject = rej })
      rec.loads.set(packUrl, p)
      return p
    }

    if (!rec) {
      rec = { loads: new Map() }
      const spawned = new Promise((res) => { rec.resolveSpawn = res })
      this._packs.set(pack, rec)
      const pendingLoad = trackLoad()
      f.contentWindow.postMessage({
        __sn: true, t: 'spawn', pack, packUrl, packSource, bootstrapSource,
        capabilities, boot,
      }, '*')
      await spawned
      return this._awaitLoad(pack, packUrl, pendingLoad)
    }

    const pendingLoad = trackLoad()
    this.send(pack, { t: 'load', packUrl,
                      packSource: packSource != null ? packSource : null })
    return this._awaitLoad(pack, packUrl, pendingLoad)
  }

  async _awaitLoad(pack, packUrl, pendingLoad) {
    const outcome = await Promise.race([
      pendingLoad.promise,
      new Promise((_, rej) => setTimeout(
        () => rej(new Error(`'${pack}' entry did not finish loading: ${packUrl}`)),
        this.loadTimeoutMs)),
    ])
    return outcome
  }

  /** Send a message into a pack's worker. */
  send(pack, payload) {
    if (!this._iframe) return
    this._iframe.contentWindow.postMessage(
      { __sn: true, t: 'to', pack, payload }, '*')
  }

  /** Send the same message into every pack's worker (epoch and graph feed). */
  sendAll(payload) {
    for (const pack of this._packs.keys()) this.send(pack, payload)
  }

  kill(pack) {
    if (!this._iframe) return
    this._iframe.contentWindow.postMessage({ __sn: true, t: 'kill', pack }, '*')
    this._packs.delete(pack)
  }

  destroy() {
    if (this._onMsg) window.removeEventListener('message', this._onMsg)
    if (this._iframe) this._iframe.remove()
    this._iframe = null
    this._ready = null
    this._packs.clear()
  }

  /** Diagnostics: how many packs are live (used by scaling assertions). */
  get packCount() { return this._packs.size }
}
