/**
 * Guest bootstrap — runs inside the per-pack worker.
 *
 * Builds the pack's entire world:
 *   comfy.*        RPC proxy onto the real V2 API
 *   comfy.defs     declare-then-apply bridge for `extend` (see below)
 *   comfy.ui       node-body UI panels (markup + declared events)
 *   comfy.element  element handles for imperative control (video, canvas, img)
 *
 * NOTE: no static imports. This file is delivered as SOURCE and started as a
 * CLASSIC worker, because Chromium will not start a module worker from a blob:
 * URL at an opaque origin. The pack itself is reached via dynamic import(),
 * which works in classic workers in all engines.
 *
 * ── Why `defs.extend` cannot be a plain RPC ──────────────────────────────────
 * `comfy.defs.extend(selector, builder)` takes a FUNCTION, and functions do not
 * survive structured clone. So the builder callback runs HERE, in the worker,
 * against a RECORDING builder: declarative calls (setTitle, addWidget…) are
 * captured as data, and lifecycle hooks are captured as local closures whose
 * NAMES are sent to the host. The host registers a real extension whose hooks
 * simply message us back, and we invoke the closure the pack actually wrote.
 *
 * The pack writes ordinary V2 code; only data crosses the boundary.
 */
;(() => {
  let seq = 1
  const pending = new Map()
  const elemHandlers = new Map() // `${name}:${event}` -> fn[]
  const uiHandlers = new Map()   // packKey -> (action, detail) => void
  const registrations = new Map() // regId -> { hooks: {name: fn} }
  const workflowImporters = new Map() // id -> worker-owned closures
  const comboPreviewRegistrations = new Set()
  const localizationRegistrations = new Set()
  const openDialogs = new Map()
  const registrationPromises = new Set()
  const pendingExtensions = []
  let capabilities = []
  let regSeq = 1
  let dialogSeq = 1

  // ---- scoped document/window (module-scope survival) ---------------------
  //
  // 14 of KJNodes' 28 files touch document/window, and eight of them do it at
  // module scope — which is registration, not rendering: global key/pointer
  // listeners, a `window.<pack>` namespace, and stylesheet injection. Those
  // idioms must not kill module evaluation, so this is a RECORDING facade:
  // the common operations succeed against inert local state and are tallied
  // in `__domOps` (the measured input for the Remote-DOM allowlist), while
  // an operation this facade does not know stays a visible TypeError naming
  // the member — never a silent no-op that reads as "covered".
  //
  // What this deliberately is NOT: a synthetic browser. Nothing here renders,
  // measures, or dispatches host events. Rendering is the Remote-DOM /
  // OffscreenCanvas lanes; host input reaches the listener registries below
  // via capture/replay when those lanes land.
  const domOps = new Map()
  const record = (name) => domOps.set(name, (domOps.get(name) || 0) + 1)
  self.__domOps = domOps

  const globalListeners = new Map() // `${target}:${type}` -> fn[]
  const listen = (target) => ({
    addEventListener(type, fn) {
      record(`${target}.addEventListener:${type}`)
      const k = `${target}:${type}`
      const list = globalListeners.get(k) || []
      list.push(fn)
      globalListeners.set(k, list)
    },
    removeEventListener(type, fn) {
      const k = `${target}:${type}`
      globalListeners.set(k, (globalListeners.get(k) || []).filter((f) => f !== fn))
    },
  })
  self.__domGlobalListeners = globalListeners

  const ZERO_RECT = Object.freeze({
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0,
  })

  /**
   * Last host-reported geometry per stub — the plan's materialized
   * measurement. Layout lives host-side and cannot be asked synchronously,
   * so the host ships each mounted stub's rect after every flush and the
   * facade answers reads from that. Stale by at most one frame, which is
   * what `getBoundingClientRect()` in a pointer handler actually needs: the
   * corpus idiom is `(e.clientX - rect.left) * (canvas.width / rect.width)`,
   * and a zero rect silently turns every editor coordinate into garbage.
   */
  const stubRects = new Map() // stubId -> rect
  const stubPaths = new Map() // stubId -> { length, points: [[x,y], …] }

  /** Set by any stub mutation; mounted trees reflush on the next microtask. */
  let flushDirtyUI = null
  const markDirty = () => { flushDirtyUI?.() }

  /**
   * Workers have no `Image`, and the corpus idiom is
   * `img.src = URL.createObjectURL(blob); img.onload = …; ctx.drawImage(img)`.
   * This shim keeps that source shape: `src` fetches and decodes to an
   * ImageBitmap, and the wrapped 2D contexts below unwrap `__bitmap` when a
   * shim is handed to drawImage.
   */
  class ImageShim {
    set src(url) {
      this.__src = url
      fetch(url)
        .then((r) => r.blob())
        .then((blob) => createImageBitmap(blob))
        .then((bitmap) => {
          this.__bitmap = bitmap
          this.width = this.naturalWidth = bitmap.width
          this.height = this.naturalHeight = bitmap.height
          this.complete = true
          this.onload?.()
        })
        .catch((err) => { this.onerror?.(err) })
    }
    get src() { return this.__src }
  }
  self.Image = ImageShim

  /** Unwraps ImageShim arguments so pack code can drawImage(img, …) as-is. */
  const wrapContext = (ctx) => new Proxy(ctx, {
    get(target, p) {
      const v = target[p]
      if (typeof v !== 'function') return v
      return (...args) => v.apply(target, args.map((a) => a?.__bitmap ?? a))
    },
    set(target, p, v) { target[p] = v; return true },
  })

  let stubSeq = 1
  function makeStubElement(tagName) {
    const state = {
      stubId: `u${stubSeq++}`,
      tagName: String(tagName).toUpperCase(),
      childNodes: [],
      attributes: new Map(),
      listeners: new Map(),
      classes: new Set(),
      style: new Proxy({ setProperty() {}, removeProperty() {}, getPropertyValue: () => '' }, {
        get: (t, p) => (p in t ? t[p] : ''),
        set: (t, p, v) => ((t[p] = v), markDirty(), true),
      }),
      dataset: {},
      props: new Map(),
      offscreen: null,
    }
    const ensureOffscreen = () => {
      if (!state.offscreen) {
        const w = Number(state.props.get('width')) || 300
        const h = Number(state.props.get('height')) || 150
        state.offscreen = new OffscreenCanvas(w, h)
      }
      return state.offscreen
    }
    const methods = {
      appendChild(c) { state.childNodes.push(c); if (c && typeof c === 'object') c.parentNode = el; markDirty(); return c },
      removeChild(c) { state.childNodes = state.childNodes.filter((x) => x !== c); markDirty(); return c },
      insertBefore(c, ref) {
        const i = state.childNodes.indexOf(ref)
        i === -1 ? state.childNodes.push(c) : state.childNodes.splice(i, 0, c)
        if (c && typeof c === 'object') c.parentNode = el
        markDirty()
        return c
      },
      append(...cs) { for (const c of cs) methods.appendChild(c) },
      prepend(...cs) { state.childNodes.unshift(...cs); markDirty() },
      remove() { state.props.set('parentNode', null); markDirty() },
      replaceChildren(...cs) { state.childNodes = [...cs]; markDirty() },
      replaceChild(next, old) {
        const i = state.childNodes.indexOf(old)
        if (i === -1) state.childNodes.push(next)
        else state.childNodes[i] = next
        if (next && typeof next === 'object') next.parentNode = el
        markDirty()
        return old
      },
      setAttribute(k, v) {
        state.attributes.set(String(k), String(v))
        // A path's geometry changed: ask the host to re-measure it. The
        // answer lands before the next frame's reads.
        if (String(k) === 'd') {
          void rpc('measurepath', { stubId: state.stubId, d: String(v) })
            .then((m) => { if (m) stubPaths.set(state.stubId, m) }, () => {})
        }
        markDirty()
      },
      getAttribute(k) { return state.attributes.has(String(k)) ? state.attributes.get(String(k)) : null },
      removeAttribute(k) { state.attributes.delete(String(k)); markDirty() },
      hasAttribute(k) { return state.attributes.has(String(k)) },
      addEventListener(type, fn) {
        record(`element.addEventListener:${type}`)
        const list = state.listeners.get(type) || []
        list.push(fn)
        state.listeners.set(type, list)
        markDirty()
      },
      removeEventListener(type, fn) {
        state.listeners.set(type, (state.listeners.get(type) || []).filter((f) => f !== fn))
      },
      dispatchEvent() { return false },
      querySelector() { return null },
      querySelectorAll() { return [] },
      getElementsByClassName() { return [] },
      getElementsByTagName() { return [] },
      closest() { return null },
      contains() { return false },
      getBoundingClientRect() {
        return stubRects.get(state.stubId) ?? ZERO_RECT
      },
      getClientRects() { return [] },
      focus() {}, blur() {}, click() {},
      cloneNode() { return makeStubElement(state.tagName) },
      matches() { return false },
      // SVG path arithmetic is real geometry, not markup: the sampler sets a
      // `d` and asks for arc length and points along it. A facade cannot
      // compute that, and faking it silently would put spline samples in the
      // wrong places. The host owns an offscreen <path> per stub and answers
      // synchronously from the last measurement — the same materialized shape
      // as getBoundingClientRect, and `setAttribute('d', …)` is what refreshes
      // it, so a sampler that sets then reads is one frame behind at worst.
      getTotalLength() {
        record('element.getTotalLength')
        return stubPaths.get(state.stubId)?.length ?? 0
      },
      getPointAtLength(len) {
        record('element.getPointAtLength')
        const pts = stubPaths.get(state.stubId)?.points
        if (!pts || !pts.length) return { x: 0, y: 0 }
        const total = stubPaths.get(state.stubId).length || 1
        const t = Math.max(0, Math.min(1, len / total))
        const i = Math.min(pts.length - 1, Math.round(t * (pts.length - 1)))
        return { x: pts[i][0], y: pts[i][1] }
      },
      // A stub <canvas> is backed by a real OffscreenCanvas: the pack draws
      // real pixels here, and the mount flush ships them as an ImageBitmap
      // the host paints into the rendered canvas. The wrap lets the pack
      // hand an ImageShim straight to drawImage.
      getContext(type) {
        record('element.getContext')
        if (state.tagName !== 'CANVAS') return null
        return wrapContext(ensureOffscreen().getContext(type || '2d'))
      },
    }
    const el = new Proxy(state.props, {
      get(props, p) {
        if (typeof p !== 'string') return undefined
        if (p === 'then') return undefined
        if (p === '__stub') return state
        record(`element.${p}`)
        if (p in methods) return methods[p]
        switch (p) {
          case 'tagName': return state.tagName
          case 'childNodes': case 'children': return state.childNodes
          case 'firstChild': return state.childNodes[0] ?? null
          case 'lastChild': return state.childNodes.at(-1) ?? null
          case 'style': return state.style
          case 'dataset': return state.dataset
          case 'classList': return {
            add: (...cs) => cs.forEach((c) => state.classes.add(c)),
            remove: (...cs) => cs.forEach((c) => state.classes.delete(c)),
            toggle: (c) => (state.classes.has(c) ? state.classes.delete(c) : state.classes.add(c)),
            contains: (c) => state.classes.has(c),
          }
          case 'className': return [...state.classes].join(' ')
          case 'ownerDocument': return documentStub
          case 'offsetWidth': case 'clientWidth': case 'scrollWidth':
            return stubRects.get(state.stubId)?.width ?? 0
          case 'offsetHeight': case 'clientHeight': case 'scrollHeight':
            return stubRects.get(state.stubId)?.height ?? 0
        }
        return props.has(p) ? props.get(p) : undefined
      },
      set(props, p, v) {
        if (p === 'className' && typeof v === 'string') {
          state.classes = new Set(v.split(/\s+/).filter(Boolean))
          markDirty()
          return true
        }
        props.set(p, v)
        if (state.tagName === 'CANVAS' && (p === 'width' || p === 'height')) {
          if (state.offscreen) state.offscreen[p] = Number(v) || 0
        }
        // DOM semantics: writing either replaces the children wholesale.
        if (p === 'textContent' || p === 'innerHTML') state.childNodes = []
        markDirty()
        return true
      },
      has(props, p) { return typeof p === 'string' && (p in methods || props.has(p)) },
    })
    return el
  }

  const documentStub = (() => {
    const head = makeStubElement('head')
    const body = makeStubElement('body')
    const documentElement = makeStubElement('html')
    const docListen = listen('document')
    return new Proxy(Object.create(null), {
      get(_t, p) {
        if (typeof p !== 'string' || p === 'then') return undefined
        record(`document.${p}`)
        switch (p) {
          case 'createElement': case 'createElementNS':
            return (...args) => makeStubElement(args.at(-1))
          case 'createTextNode':
            return (text) => ({ textContent: String(text), nodeType: 3 })
          case 'createDocumentFragment':
            return () => makeStubElement('#fragment')
          case 'head': return head
          case 'body': return body
          case 'documentElement': return documentElement
          case 'addEventListener': return docListen.addEventListener
          case 'removeEventListener': return docListen.removeEventListener
          case 'getElementById': return () => null
          case 'querySelector': return () => null
          case 'querySelectorAll': return () => []
          case 'getElementsByClassName': return () => []
          case 'getElementsByTagName': return () => []
          case 'visibilityState': return 'visible'
          case 'hidden': return false
          case 'activeElement': return null
          case 'defaultView': return windowStub
          case 'fonts': return { ready: Promise.resolve(), addEventListener() {} }
          case 'dispatchEvent': return () => false
        }
        return undefined
      },
    })
  })()

  const windowStub = (() => {
    const winProps = new Map()
    const winListen = listen('window')
    return new Proxy(winProps, {
      get(props, p) {
        if (typeof p !== 'string' || p === 'then') return undefined
        record(`window.${p}`)
        switch (p) {
          case 'addEventListener': return winListen.addEventListener
          case 'removeEventListener': return winListen.removeEventListener
          case 'document': return documentStub
          case 'location': return self.location
          case 'navigator': return self.navigator
          case 'devicePixelRatio': return 1
          case 'innerWidth': return 1920
          case 'innerHeight': return 1080
          case 'matchMedia': return () => ({
            matches: false, media: '',
            addEventListener() {}, removeEventListener() {},
            addListener() {}, removeListener() {},
          })
          case 'getComputedStyle': return () => ({ getPropertyValue: () => '' })
          case 'requestAnimationFrame':
            return self.requestAnimationFrame
              ? self.requestAnimationFrame.bind(self)
              : (cb) => self.setTimeout(() => cb(self.performance.now()), 16)
          case 'cancelAnimationFrame':
            return self.cancelAnimationFrame
              ? self.cancelAnimationFrame.bind(self)
              : self.clearTimeout.bind(self)
          case 'setTimeout': return self.setTimeout.bind(self)
          case 'clearTimeout': return self.clearTimeout.bind(self)
          case 'setInterval': return self.setInterval.bind(self)
          case 'clearInterval': return self.clearInterval.bind(self)
          case 'dispatchEvent': return () => false
        }
        // `window.<pack> = {…}` namespaces and similar pack-owned globals.
        return props.has(p) ? props.get(p) : undefined
      },
      set(props, p, v) { props.set(p, v); return true },
      has(props, p) { return typeof p === 'string' && props.has(p) },
    })
  })()

  self.document = documentStub
  self.window = windowStub
  // Layout happens host-side; the host's own observer measures mounted trees
  // and reports upward. A worker-side observer has nothing to observe, but
  // its ABSENCE kills module evaluation — inert, like the rest of the facade.
  self.ResizeObserver = class {
    observe() { record('ResizeObserver.observe') }
    unobserve() {}
    disconnect() {}
  }
  self.MutationObserver = class {
    observe() { record('MutationObserver.observe') }
    disconnect() {}
    takeRecords() { return [] }
  }

  const rpc = (t, payload) =>
    new Promise((resolve, reject) => {
      const id = seq++
      pending.set(id, { resolve, reject })
      self.postMessage({ t, id, ...payload })
    })

  const trackRegistration = (promise) => {
    registrationPromises.add(promise)
    promise.then(
      () => registrationPromises.delete(promise),
      () => registrationPromises.delete(promise),
    )
    return promise
  }

  // ---- comfy.* path proxy -------------------------------------------------
  const proxy = (path) => {
    const fn = (...args) => rpc('call', { path: path.join('.'), args })
    return new Proxy(fn, {
      get(_t, p) {
        if (typeof p !== 'string' || p === 'then') return undefined
        return proxy([...path, p])
      },
      apply(_t, _s, args) { return rpc('call', { path: path.join('.'), args }) },
    })
  }

  // ---- comfy.defs: extend is local, everything else is RPC ----------------
  //
  // Hooks whose RETURN VALUE the host consumes synchronously (a veto, a
  // serialized payload) cannot work over an async boundary. They are rejected
  // loudly rather than silently doing nothing — a hook that never fires is a
  // bug the pack author cannot see. See DEBT.md F4.
  const VOID_HOOKS = [
    'onCreated', 'onExecuted', 'onConfigured', 'onConnectionsChanged',
    'onRemoved', 'onResized', 'onHover', 'onDoubleClick', 'onPropertyChanged',
    'onPreview',
  ]
  const UNSUPPORTED_HOOKS = [
    'onDragOver', 'onDrop', 'onBeforeConnect', 'onUnplacedLink',
  ]
  // onSerialize is NOT in that list: the host consumes its return value
  // synchronously, but the value is a pure function of pack state, so it is a
  // materialized view like rects and path geometry — recomputed after every
  // dispatch that could have changed the state, cached host-side, read
  // synchronously when serialization happens. See `serializeHooks` below.
  const SERIALIZE_HOOK = 'onSerialize'
  // Prompt serialization is different: graphToPrompt is already async, so the
  // host refreshes this worker's replica and awaits the exact current answer.
  const PROMPT_SERIALIZE_HOOK = 'onPromptSerialize'
  const DECLARATIVE = ['setTitle', 'setCategory', 'hideWidget']

  // The def catalogue, shipped by the host at init. This is what makes
  // registration WORKER-LOCAL: selectors — including predicate functions,
  // which only exist in this realm — are evaluated here, and the pack's
  // builder runs once per matched def with `b.def` populated, exactly the
  // real registry's semantics. What crosses the boundary is one exact-name
  // registration per matched def: recorded declarations plus hook names.
  let defCatalogue = []
  let defsByType = new Map()

  /** Mirrors the host registry's DefSelector semantics, member for member. */
  function matchesSelector(selector, def) {
    if (typeof selector === 'function') return !!selector(def)
    if (typeof selector === 'string') return def.type === selector
    if (selector instanceof RegExp) return selector.test(def.type)
    if (selector && typeof selector === 'object' && 'length' in selector) {
      return selector.includes(def.type)
    }
    const category = selector && selector.category
    return category instanceof RegExp
      ? category.test(def.category)
      : def.category === category
  }

  function makeRecorder(def) {
    const rec = { def, hooks: {}, declared: [], widgets: [],
                  menuItems: [], menuWhen: new Map(), menuRun: new Map(),
                  menuDynamic: new Map(), dynamicMenuTokens: new Set() }
    const b = { def }
    for (const m of DECLARATIVE) b[m] = (v) => { rec.declared.push([m, v]) }
    b.addWidget = (w) => { rec.widgets.push(w) }
    b.addMenuItem = (item) => {
      // `label` as a function is still read synchronously at every display
      // and stays evaluated-once (see commands). `when` and `items` are
      // supported: `when` is a pure predicate over node state this worker
      // already replicates, so it is evaluated here and its ANSWER is
      // materialized host-side; `items` is nested data whose `run` closures
      // trampoline exactly like top-level ones.
      if (typeof item?.label !== 'string') {
        throw new Error(
          'comfy.defs.extend: a sandboxed addMenuItem needs a string label — ' +
          'the host reads a label function synchronously each time the menu opens.')
      }
      const record1 = (entry, path) => {
        const menuId = `m${path}`
        const out = { menuId, label: entry.label, order: entry.order }
        if (typeof entry.when === 'function') {
          rec.menuWhen.set(menuId, entry.when)
          out.hasWhen = true
        }
        if (typeof entry.run === 'function') rec.menuRun.set(menuId, entry.run)
        if (Array.isArray(entry.items)) {
          out.items = entry.items.map((child, i) =>
            record1(child, `${path}_${i}`))
        } else if (typeof entry.items === 'function') {
          rec.menuDynamic.set(menuId, entry.items)
          out.hasDynamicItems = true
        }
        return out
      }
      rec.menuItems.push(record1(item, String(rec.menuItems.length)))
    }
    for (const h of VOID_HOOKS) b[h] = (fn) => { rec.hooks[h] = fn }
    // Captured like a void hook — the difference is where its RETURN goes:
    // ship() pulls it out of `hooks` into the materialized serialize view
    // rather than sending its name to the host as a dispatch target.
    b[SERIALIZE_HOOK] = (fn) => { rec.hooks[SERIALIZE_HOOK] = fn }
    b[PROMPT_SERIALIZE_HOOK] = (fn) => {
      rec.hooks[PROMPT_SERIALIZE_HOOK] = fn
    }
    for (const h of UNSUPPORTED_HOOKS) {
      b[h] = () => {
        throw new Error(
          `comfy.defs.extend: '${h}' is not available to a sandboxed pack ` +
          `because the host consumes its return value synchronously.`)
      }
    }
    return { b, rec }
  }

  function ship(selector, rec) {
    const regId = `r${regSeq++}`
    const serialize = rec.hooks[SERIALIZE_HOOK]
    const promptSerialize = rec.hooks[PROMPT_SERIALIZE_HOOK]
    const hooks = { ...rec.hooks }
    delete hooks[SERIALIZE_HOOK]
    delete hooks[PROMPT_SERIALIZE_HOOK]
    registrations.set(regId, {
      hooks,
      menus: rec.menuRun,
      when: rec.menuWhen,
      dynamic: rec.menuDynamic,
      dynamicTokens: rec.dynamicMenuTokens,
      serialize,
      promptSerialize,
    })
    // Scoped to the type this registration matched. Without it a view is
    // computed for every node in the document — ideogram4's onSerialize ran
    // against unrelated nodes, and contextmenu's `/.*/ ` selector (one
    // registration per matched def, ~1000 of them) turned 5 menu items into
    // 100k visibility entries per refresh. A registration only ever applies
    // to its own type, so the view should only cover its own nodes.
    const forType = typeof selector === 'string' ? selector : null
    if (serialize) serializeHooks.set(regId, { fn: serialize, forType })
    if (rec.menuWhen.size) menuWhenRegs.set(regId, { whens: rec.menuWhen, forType })
    if (rec.menuDynamic.size) {
      menuDynamicRegs.set(regId, {
        providers: rec.menuDynamic,
        runs: rec.menuRun,
        tokens: rec.dynamicMenuTokens,
        forType,
      })
    }
    return trackRegistration(rpc('extend', {
      regId, selector,
      hooks: Object.keys(hooks),
      hasSerialize: !!serialize,
      hasPromptSerialize: !!promptSerialize,
      declared: rec.declared,
      widgets: rec.widgets,
      menuItems: rec.menuItems,
    }))
  }

  function extend(selector, apply) {
    if (defCatalogue.length) {
      const sent = []
      for (const def of defCatalogue) {
        if (!matchesSelector(selector, def)) continue
        const { b, rec } = makeRecorder(def)
        apply(b) // the pack's own callback: per matched def, `b.def` in hand
        sent.push(ship(def.type, rec))
      }
      if (!sent.length &&
          (typeof selector === 'string' || Array.isArray(selector))) {
        pendingExtensions.push({ selector, apply })
      }
      return Promise.all(sent)
    }
    // No catalogue (the host's fetch failed): degrade to shipping the
    // selector itself, which preserves every builder that never reads
    // `b.def`. Predicate selectors cannot cross — they are functions.
    if (typeof selector === 'function') {
      throw new Error(
        'comfy.defs.extend: a predicate selector needs the def catalogue, ' +
        'which this sandbox failed to receive.')
    }
    const { b, rec } = makeRecorder(undefined)
    apply(b)
    return ship(selector, rec)
  }

  /**
   * `defs.define` — a pack-owned node type. The definition's data crosses;
   * its FUNCTIONS stay here: lifecycle hooks ride the existing hook channel,
   * and `resolve`/`supply` answer host requests against this worker's own
   * replica — the host refreshes the replica, asks "resolve node N", and this
   * side rebuilds the {self, nodesOfType} view from its snapshots. That is
   * what lets the prompt path await a worker's answer without any part of the
   * pack's logic leaving the worker.
   */
  const definitions = new Map() // type -> { resolve, supply }

  function define(def) {
    const regId = `r${regSeq++}`
    const data = {}
    const hooks = {}
    for (const [k, v] of Object.entries(def || {})) {
      if (k === 'resolve' || k === 'supply') continue
      if (typeof v === 'function') hooks[k] = v
      else data[k] = v
    }
    if (Array.isArray(data.widgets)) {
      data.widgets = data.widgets.map((w) => {
        const clean = {}
        for (const [k, v] of Object.entries(w)) {
          if (typeof v === 'function') {
            console.warn(
              `[sandbox] defs.define('${def.type}'): widget '${w.name}' ` +
              `member '${k}' is a function and cannot cross; dropped.`)
          } else clean[k] = v
        }
        return clean
      })
    }
    const serialize = hooks[SERIALIZE_HOOK]
    const promptSerialize = hooks[PROMPT_SERIALIZE_HOOK]
    delete hooks[SERIALIZE_HOOK]
    delete hooks[PROMPT_SERIALIZE_HOOK]
    registrations.set(regId, {
      hooks, menus: new Map(), serialize, promptSerialize,
    })
    definitions.set(def.type, { resolve: def.resolve, supply: def.supply })

    const catalogueDef = Object.freeze({
      type: data.type,
      title: data.title ?? data.type,
      category: data.category ?? 'custom',
      description: data.description ?? '',
      inputs: Object.freeze((data.inputs || []).map((input) =>
        Object.freeze({ ...input }))),
      outputs: Object.freeze((data.outputs || []).map((output) =>
        Object.freeze({ ...output }))),
      isOutputNode: false,
      hidden: Object.freeze({}),
      source: self.__pack,
    })
    defCatalogue = [...defCatalogue, catalogueDef]
    defsByType.set(def.type, catalogueDef)

    const matchedExtensions = pendingExtensions.filter((pending) =>
      matchesSelector(pending.selector, catalogueDef))
    for (const pending of matchedExtensions) {
      pendingExtensions.splice(pendingExtensions.indexOf(pending), 1)
      const { b, rec } = makeRecorder(catalogueDef)
      pending.apply(b)
      ship(def.type, rec)
    }

    if (serialize) {
      serializeHooks.set(regId, { fn: serialize, forType: def.type })
    }
    return trackRegistration(rpc('define', {
      regId,
      def: data,
      hooks: Object.keys(hooks),
      hasSerialize: !!serialize,
      hasPromptSerialize: !!promptSerialize,
      has: { resolve: typeof def.resolve === 'function',
             supply: typeof def.supply === 'function' },
    }))
  }

  /** ResolvedNodeView, rebuilt from this worker's replica snapshots. */
  function replicaView(nodeId) {
    const s = graphState.nodes.get(String(nodeId))
    if (!s) return undefined
    return {
      id: s.id,
      type: s.type,
      properties: Object.freeze({ ...(s.properties || {}) }),
      groups: Object.freeze([]),
      mode: s.mode ?? 0,
      color: s.color,
      inputs: Object.freeze((s.inputs || []).map((slot) => ({ ...slot }))),
      outputs: Object.freeze((s.outputs || []).map((slot) => ({ ...slot }))),
      widgetValue: (name) => {
        const w = (s.widgets || []).find((x) => x.name === name)
        return w ? w.value : undefined
      },
      input: (refArg) => {
        const inputs = s.inputs || []
        const index = typeof refArg === 'number'
          ? refArg
          : inputs.findIndex((i) => i.name === refArg)
        if (index < 0 || index >= inputs.length) return undefined
        return { nodeId: s.id, input: index }
      },
    }
  }

  const replicaNodesOfType = (wanted) =>
    [...graphState.nodes.values()]
      .filter((s) => s.type === wanted)
      .map((s) => replicaView(s.id))
      .filter(Boolean)

  const defsProxy = proxy(['comfy', 'defs'])
  const defs = new Proxy(Object.create(null), {
    get(_t, p) {
      if (p === 'extend') return extend
      if (p === 'define') return define
      // Synchronous reads a builder or hook body performs against the same
      // catalogue registration matched on. First slice of the replica: defs
      // are read-mostly and document-independent, so a boot snapshot serves.
      if (p === 'get') return (type) => defsByType.get(type)
      if (p === 'has') return (type) => defsByType.has(type)
      if (p === 'all') return () => defCatalogue.slice()
      if (typeof p !== 'string' || p === 'then') return undefined
      return defsProxy[p]
    },
  })

  // ---- node-body UI -------------------------------------------------------
  /**
   * A panel inside a node's body. The container is created lazily by the host
   * on first render (via the real `widgets.mount`), so a pack never holds — or
   * could hold — a DOM element.
   */
  const uiPanel = (nodeId, name = 'panel') => {
    const key = `${nodeId}:${name}`
    return {
      key,
      on(handler) { uiHandlers.set(key, handler) },
      render(markup) {
        return rpc('ui', { key, nodeId: String(nodeId), name, markup })
      },
    }
  }

  const uiProxy = proxy(['comfy', 'ui'])

  // Action-bar buttons carry a worker-owned `run` closure and return a live
  // update/remove handle. Neither can cross structured clone, so keep both
  // sides of that contract local and send the host only the closed visual
  // contribution plus lifecycle operations.
  const actionButtonRuns = new Map() // id -> run closure
  const topBarBadgeIds = new Set()

  function boundedActionString(value, name, { optional = false,
                                               max = 512 } = {}) {
    if (optional && value === undefined) return undefined
    if (typeof value !== 'string' || value.length < 1 || value.length > max ||
        /[\0-\x1f\x7f]/.test(value)) {
      throw new TypeError(`${name} must be a non-empty bounded string`)
    }
    return value
  }

  function actionButtonData(value, { partial = false } = {}) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError('action-bar button must be an object')
    }
    const allowed = partial
      ? new Set(['icon', 'label', 'tooltip', 'run'])
      : new Set(['id', 'icon', 'label', 'tooltip', 'run'])
    for (const key of Object.keys(value)) {
      if (!allowed.has(key)) {
        throw new TypeError(`unsupported action-bar button field '${key}'`)
      }
    }
    const data = {}
    if (!partial) {
      const id = boundedActionString(value.id, 'action-bar button id', {
        max: 128,
      })
      if (!id.includes('.') ||
          !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(id)) {
        throw new TypeError('action-bar button id must be namespaced')
      }
      data.id = id
    }
    if (!partial || Object.hasOwn(value, 'icon')) {
      data.icon = boundedActionString(value.icon, 'action-bar button icon', {
        max: 256,
      })
    }
    for (const key of ['label', 'tooltip']) {
      if (Object.hasOwn(value, key)) {
        data[key] = boundedActionString(
          value[key], `action-bar button ${key}`, { optional: true })
      }
    }
    return data
  }

  function topBarBadgeData(value, { partial = false } = {}) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError('top-bar badge must be an object')
    }
    const allowed = partial
      ? new Set(['text', 'label', 'variant', 'icon', 'tooltip'])
      : new Set(['id', 'text', 'label', 'variant', 'icon', 'tooltip'])
    for (const key of Object.keys(value)) {
      if (!allowed.has(key)) {
        throw new TypeError(`unsupported top-bar badge field '${key}'`)
      }
    }
    const data = {}
    if (!partial) {
      const id = boundedActionString(value.id, 'top-bar badge id', { max: 128 })
      if (!id.includes('.') || !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(id)) {
        throw new TypeError('top-bar badge id must be namespaced')
      }
      data.id = id
    }
    for (const key of ['text', 'label', 'icon', 'tooltip']) {
      if ((!partial && key === 'text') || Object.hasOwn(value, key)) {
        data[key] = boundedActionString(
          value[key], `top-bar badge ${key}`,
          { optional: key !== 'text', max: key === 'icon' ? 256 : 512 })
      }
    }
    if (Object.hasOwn(value, 'variant')) {
      if (value.variant !== undefined &&
          !['info', 'warning', 'error'].includes(value.variant)) {
        throw new TypeError('top-bar badge variant is invalid')
      }
      data.variant = value.variant
    }
    return data
  }

  function comboPreviewData(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        typeof value.id !== 'string' ||
        !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value.id) ||
        !value.id.includes('.')) {
      throw new TypeError('combo preview requires a namespaced id')
    }
    const closedList = (items, name, allowed) => {
      if (!Array.isArray(items) || !items.length || items.length > allowed.size ||
          items.some((item) => typeof item !== 'string' || !allowed.has(item)) ||
          new Set(items).size !== items.length) {
        throw new TypeError(`combo preview ${name} is invalid`)
      }
      return items.slice()
    }
    if (value.candidatePolicy !== 'adjacent-model-preview-v1') {
      throw new TypeError('unsupported combo preview candidate policy')
    }
    return {
      id: value.id,
      modelCategories: closedList(
        value.modelCategories, 'modelCategories',
        new Set(['loras', 'checkpoints', 'unet', 'diffusion_models'])),
      extensions: closedList(
        value.extensions, 'extensions',
        new Set(['safetensors', 'sft', 'pt', 'ckpt', 'gguf'])),
      candidatePolicy: value.candidatePolicy,
      media: closedList(
        value.media, 'media',
        new Set(['image/png', 'image/webp', 'image/jpeg',
                 'video/mp4', 'video/webm'])),
    }
  }

  function comboPreviewAssignmentData(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        new Set(Object.keys(value)).size !== 5 || ![
          'category', 'modelValue', 'sourceNodeId', 'imageIndex', 'policy',
        ].every((key) => Object.hasOwn(value, key)) ||
        !new Set(['loras', 'checkpoints', 'unet', 'diffusion_models'])
          .has(value.category) ||
        typeof value.modelValue !== 'string' ||
        value.modelValue.length < 1 || value.modelValue.length > 1024 ||
        /[\0-\x1f\x7f]/.test(value.modelValue) ||
        typeof value.sourceNodeId !== 'string' ||
        value.sourceNodeId.length < 1 || value.sourceNodeId.length > 256 ||
        /[\0-\x1f\x7f]/.test(value.sourceNodeId) ||
        !Number.isSafeInteger(value.imageIndex) || value.imageIndex < 0 ||
        value.imageIndex > 4095 ||
        value.policy !== 'adjacent-model-preview-v1') {
      throw new TypeError('combo preview assignment is invalid')
    }
    return {
      category: value.category,
      modelValue: value.modelValue,
      sourceNodeId: value.sourceNodeId,
      imageIndex: value.imageIndex,
      policy: value.policy,
    }
  }

  function localizationCatalogData(locale, value) {
    if (typeof locale !== 'string' || locale.length > 32 ||
        !/^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$/.test(locale) ||
        !value || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError('localization catalog declaration is invalid')
    }
    const keys = Object.keys(value)
    if (!keys.includes('messages') ||
        keys.some((key) => key !== 'messages' && key !== 'phrases') ||
        !value.messages || typeof value.messages !== 'object' ||
        Array.isArray(value.messages)) {
      throw new TypeError('localization catalog requires messages')
    }
    let entries = 0
    let bytes = 0
    const forbidden = new Set(['__proto__', 'prototype', 'constructor'])
    const seen = new WeakSet()
    const addString = (text, maximum) => {
      if (typeof text !== 'string' || text.includes('\0')) {
        throw new TypeError('localization catalog contains an invalid string')
      }
      const size = new TextEncoder().encode(text).byteLength
      if (size > maximum || (bytes += size) > 4 * 1024 * 1024) {
        throw new TypeError('localization catalog exceeds its bounds')
      }
    }
    const walk = (input, depth) => {
      if (typeof input === 'string') {
        addString(input, 4096)
        return input
      }
      if (input === null) return null
      if (!input || typeof input !== 'object' || Array.isArray(input) ||
          depth > 16 || seen.has(input)) {
        throw new TypeError('localization message tree is invalid')
      }
      seen.add(input)
      const output = {}
      for (const [key, child] of Object.entries(input)) {
        if (forbidden.has(key) || ++entries > 20_000) {
          throw new TypeError('localization catalog has invalid keys or size')
        }
        addString(key, 512)
        output[key] = walk(child, depth + 1)
      }
      seen.delete(input)
      return output
    }
    const messages = walk(value.messages, 0)
    let phrases
    if (value.phrases !== undefined) {
      if (!value.phrases || typeof value.phrases !== 'object' ||
          Array.isArray(value.phrases)) {
        throw new TypeError('localization phrases must be an object')
      }
      phrases = {}
      for (const [source, translated] of Object.entries(value.phrases)) {
        if (forbidden.has(source) || typeof translated !== 'string' ||
            ++entries > 20_000) {
          throw new TypeError('localization phrase is invalid')
        }
        addString(source, 4096)
        addString(translated, 4096)
        phrases[source] = translated
      }
    }
    return { locale, catalog: { messages, ...(phrases ? { phrases } : {}) } }
  }

  function reportActionFailure(id, phase, err) {
    self.postMessage({
      t: 'packerror',
      hook: `actionBar:${id}:${phase}`,
      error: String((err && err.stack) || err),
    })
  }

  function addActionBarButton(def) {
    const data = actionButtonData(def)
    if (typeof def.run !== 'function') {
      throw new TypeError('action-bar button run must be a function')
    }
    if (actionButtonRuns.has(data.id)) {
      throw new TypeError(`action-bar button '${data.id}' is already registered`)
    }
    actionButtonRuns.set(data.id, def.run)
    let removed = false
    const ready = rpc('uiactionreg', { def: data })
    ready.catch((err) => reportActionFailure(data.id, 'register', err))

    return Object.freeze({
      update(changes) {
        if (removed) {
          throw new TypeError(
            `action-bar button '${data.id}' has been removed and cannot be updated`)
        }
        const next = actionButtonData(changes, { partial: true })
        if (Object.hasOwn(changes, 'run')) {
          if (typeof changes.run !== 'function') {
            throw new TypeError('action-bar button run must be a function')
          }
          actionButtonRuns.set(data.id, changes.run)
        }
        ready.then(() => rpc('uiactionupdate', { id: data.id, changes: next }))
          .catch((err) => reportActionFailure(data.id, 'update', err))
      },
      remove() {
        if (removed) return
        removed = true
        actionButtonRuns.delete(data.id)
        ready.then(() => rpc('uiactionremove', { id: data.id }))
          .catch((err) => reportActionFailure(data.id, 'remove', err))
      },
    })
  }

  function addTopBarBadge(def) {
    const data = topBarBadgeData(def)
    if (topBarBadgeIds.has(data.id)) {
      throw new TypeError(`top-bar badge '${data.id}' is already registered`)
    }
    topBarBadgeIds.add(data.id)
    let removed = false
    const ready = rpc('uitopbarreg', { def: data })
    ready.catch((err) => reportActionFailure(data.id, 'register', err))
    return Object.freeze({
      update(changes) {
        if (removed) {
          throw new TypeError(
            `top-bar badge '${data.id}' has been removed and cannot be updated`)
        }
        const next = topBarBadgeData(changes, { partial: true })
        ready.then(() => rpc('uitopbarupdate', { id: data.id, changes: next }))
          .catch((err) => reportActionFailure(data.id, 'update', err))
      },
      remove() {
        if (removed) return
        removed = true
        topBarBadgeIds.delete(data.id)
        ready.then(() => rpc('uitopbarremove', { id: data.id }))
          .catch((err) => reportActionFailure(data.id, 'remove', err))
      },
    })
  }

  function finishDialog(rec) {
    if (rec.destroyed) return
    rec.destroyed = true
    mountedUIs.delete(rec.mountKey)
    uiHandlers.delete(rec.mountKey)
    if (openDialogs.get(rec.key) === rec) openDialogs.delete(rec.key)
    try {
      rec.def.destroy?.()
    } catch (err) {
      self.postMessage({
        t: 'packerror', hook: `dialog:${rec.key}:destroy`,
        error: String((err && err.stack) || err),
      })
    }
  }

  function showDialog(def) {
    if (!def || typeof def !== 'object' || Array.isArray(def) ||
        Object.keys(def).some((key) =>
          !['key', 'title', 'render', 'destroy', 'onKeyDown'].includes(key)) ||
        typeof def.key !== 'string' || !def.key.includes('.') ||
        !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(def.key) ||
        typeof def.render !== 'function' ||
        (def.destroy !== undefined && typeof def.destroy !== 'function') ||
        (def.onKeyDown !== undefined && typeof def.onKeyDown !== 'function')) {
      throw new TypeError('sandbox dialog requires a mounted dialog definition')
    }
    const title = def.title === undefined
      ? undefined
      : boundedActionString(def.title, 'dialog title', { max: 512 })
    openDialogs.get(def.key)?.close()
    const dialogId = `d${dialogSeq++}`
    const mountKey = `dialog:${dialogId}`
    const container = makeStubElement('div')
    const rec = {
      kind: 'dialog', key: def.key, dialogId, mountKey, title, def, container,
      nodeId: null, name: null, stubIndex: new Map(), canvases: new Set(),
      registered: false, closeRequested: false, destroyed: false, ready: null,
    }
    const close = () => {
      if (rec.closeRequested || rec.destroyed) return
      rec.closeRequested = true
      if (!rec.ready) return
      rec.ready.then(() => rpc('dialogclose', { dialogId }))
        .catch((err) => {
          finishDialog(rec)
          self.postMessage({
            t: 'packerror', hook: `dialog:${rec.key}:close`,
            error: String((err && err.stack) || err),
          })
        })
    }
    rec.close = close
    mountedUIs.set(mountKey, rec)
    uiHandlers.set(mountKey, (action, detail) =>
      dispatchStubEvent(rec, action, detail))
    openDialogs.set(def.key, rec)
    try {
      def.render(container)
    } catch (err) {
      finishDialog(rec)
      throw err
    }
    rec.ready = rpc('dialogreg', {
      dialogId, key: def.key, title,
      hasKeyDown: typeof def.onKeyDown === 'function',
    })
    rec.ready.then(() => {
      rec.registered = true
      if (rec.closeRequested) {
        void rpc('dialogclose', { dialogId }).catch((err) => {
          finishDialog(rec)
          self.postMessage({
            t: 'packerror', hook: `dialog:${rec.key}:close`,
            error: String((err && err.stack) || err),
          })
        })
      } else if (!rec.destroyed) {
        flushMount(rec)
      }
    }).catch((err) => {
      finishDialog(rec)
      self.postMessage({
        t: 'packerror', hook: `dialog:${rec.key}:register`,
        error: String((err && err.stack) || err),
      })
    })
    return Object.freeze({ close })
  }

  const ui = new Proxy(Object.create(null), {
    get(_t, p) {
      if (p === 'panel') return uiPanel
      if (p === 'addTopBarBadge') return addTopBarBadge
      if (p === 'addActionBarButton') return addActionBarButton
      if (p === 'showDialog') return showDialog
      if (typeof p !== 'string' || p === 'then') return undefined
      return uiProxy[p]   // sidebar tabs, dialogs, … still go to the real API
    },
  })

  // ---- element handles ----------------------------------------------------
  const element = (name) => ({
    invoke: (method, ...args) => rpc('elem', { op: 'invoke', name, method, args }),
    get: (prop) => rpc('elem', { op: 'get', name, prop }),
    set: (prop, value) => rpc('elem', { op: 'set', name, prop, value }),
    listen: (event, fn) => {
      const k = `${name}:${event}`
      const list = elemHandlers.get(k) || []
      list.push(fn)
      elemHandlers.set(k, list)
      return rpc('elem', { op: 'listen', name, event })
    },
  })

  // ---- graph replica + node handles ---------------------------------------
  //
  // The guest's copy of graph state, as data. Three feeds keep it honest:
  // the epoch push (all node snapshots, stamped with the document id — an
  // unrecognized epoch DISCARDS the cache rather than patching it), the
  // incremental nodeAdded/nodeRemoved feed between epochs, and the snapshot
  // carried by every hook/menu dispatch, which is state as of the gesture the
  // closure is answering. Reads answer from here synchronously; mutations go
  // out as explicit nodeop messages and apply here optimistically.
  // ---- Remote-DOM mounts + canvas surfaces --------------------------------
  //
  // `widgets.mount({render(container)})` hands the pack a STUB container from
  // the DOM facade above. The pack builds its tree against it exactly as
  // written; this side serializes that tree to markup — stable per-stub keys,
  // listener types declared as `data-on` — and ships it through the existing
  // sanitize-and-shadow-root channel. Mutations mark dirty and reflush on a
  // microtask. Events come back with the stub key and pointer detail, and
  // dispatch into the stub's own listeners.
  //
  // A stub <canvas> is real pixels: it is backed by an OffscreenCanvas here,
  // and each flush ships a BITMAP COPY (createImageBitmap, never
  // transferToImageBitmap — that would clear the pack's drawing behind its
  // back) that the host paints into the rendered canvas. Same pipeline for a
  // standalone `widgets.canvas` surface: host reports the size, guest draws
  // and ships, host caches the last bitmap and paints it every frame — so
  // pan/zoom stays host-instant and only content lags a frame.
  const badgeClicks = new Map()   // badgeId -> onClick closure
  const badgeProviders = new Map() // badgeId -> materialized provider state

  // BadgeDef is deliberately a tiny, closed data contract. A provider closure
  // stays in this worker; only its current text/colours cross the boundary.
  // That both preserves dynamic badges and prevents arbitrary objects (or a
  // second callback hidden below `onClick`) from reaching the host realm.
  function materializeBadge(badgeId, source) {
    const value = typeof source === 'function' ? source() : source
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError('badge provider must return a BadgeDef object')
    }
    if (typeof value.text !== 'string') {
      throw new TypeError('badge text must be a string')
    }
    const data = { text: value.text }
    for (const key of ['color', 'bgColor']) {
      if (value[key] !== undefined) {
        if (typeof value[key] !== 'string') {
          throw new TypeError(`badge ${key} must be a string`)
        }
        data[key] = value[key]
      }
    }
    if (value.onClick !== undefined && typeof value.onClick !== 'function') {
      throw new TypeError('badge onClick must be a function')
    }
    if (typeof value.onClick === 'function') badgeClicks.set(badgeId, value.onClick)
    else badgeClicks.delete(badgeId)
    return { data, hasClick: typeof value.onClick === 'function' }
  }

  // ---- materialized views of pack-computed answers ------------------------
  //
  // Three host-synchronous reads whose VALUES are pure functions of state this
  // worker already holds. Neither can be a call across the boundary, and
  // neither needs to be: compute the answer whenever the state that feeds it
  // could have changed, and let the host read the last answer synchronously.
  // Same contract as element rects and SVG path geometry — stale by at most
  // one dispatch, which is what the reader actually needs.
  //
  //   serializeHooks — `onSerialize` returns the pack's blob for the saved
  //     workflow. State can only change in response to something this worker
  //     RECEIVED (a hook, an event, a UI interaction, a menu or command run),
  //     so recomputing after every dispatch is precise rather than a poll.
  //   menuWhenRegs   — `when` decides whether a node menu shows an item. A
  //     pure predicate over the node, evaluated per node when its snapshot
  //     lands, so the answer is ready before any right-click.
  //   badgeProviders — a dynamic BadgeDef provider. The host renderer cannot
  //     call a closure across the sandbox boundary, so it reads the latest
  //     closed data view materialized after each worker dispatch.
  const serializeHooks = new Map() // regId -> onSerialize closure
  const menuWhenRegs = new Map()   // regId -> Map<menuId, predicate>
  const menuDynamicRegs = new Map() // regId -> materialized submenu providers

  let viewsDirty = false
  function refreshMaterializedViews() {
    if (viewsDirty) return
    viewsDirty = true
    queueMicrotask(() => {
      viewsDirty = false
      if (serializeHooks.size) {
        const payloads = []
        for (const [regId, { fn, forType }] of serializeHooks) {
          for (const [id, snap] of graphState.nodes) {
            if (forType && snap.type !== forType) continue
            const view = nodeViews.get(id) ?? viewFor(id)
            if (!view) continue
            try {
              const value = fn(view)
              if (value !== undefined) {
                payloads.push([`${regId}:${id}`, value])
              }
            } catch (err) {
              // A pack that cannot serialize must say so, not silently save
              // a stale blob under a new workflow.
              self.postMessage({ t: 'packerror', hook: `onSerialize:${id}`,
                                 error: String((err && err.stack) || err) })
            }
          }
        }
        if (payloads.length) self.postMessage({ t: 'serializeview', payloads })
      }
      if (menuWhenRegs.size) {
        const vis = []
        for (const [regId, { whens, forType }] of menuWhenRegs) {
          for (const [id, snap] of graphState.nodes) {
            if (forType && snap.type !== forType) continue
            const view = nodeViews.get(id) ?? viewFor(id)
            if (!view) continue
            for (const [menuId, predicate] of whens) {
              let shown = true
              try {
                shown = !!predicate(view)
              } catch (err) {
                self.postMessage({ t: 'packerror', hook: `menuWhen:${menuId}`,
                                   error: String((err && err.stack) || err) })
              }
              vis.push([`${regId}:${menuId}:${id}`, shown])
            }
          }
        }
        if (vis.length) self.postMessage({ t: 'menuview', vis })
      }
      if (menuDynamicRegs.size) {
        const views = []
        for (const [regId, rec] of menuDynamicRegs) {
          for (const token of rec.tokens) rec.runs.delete(token)
          rec.tokens.clear()
          for (const [id, snap] of graphState.nodes) {
            if (rec.forType && snap.type !== rec.forType) continue
            const view = nodeViews.get(id) ?? viewFor(id)
            if (!view) continue
            for (const [menuId, provider] of rec.providers) {
              let items = []
              try {
                const provided = provider(view)
                if (!Array.isArray(provided) || provided.length > 128) {
                  throw new TypeError(
                    'dynamic node submenu must return at most 128 items')
                }
                items = provided.map((item, index) => {
                  if (!item || typeof item !== 'object' ||
                      typeof item.label !== 'string' || !item.label ||
                      item.label.length > 512 ||
                      typeof item.run !== 'function') {
                    throw new TypeError(
                      'dynamic node submenu items require label and run')
                  }
                  const token = `d${regId}:${menuId}:${id}:${index}`
                  rec.runs.set(token, item.run)
                  rec.tokens.add(token)
                  return { menuId: token, label: item.label }
                })
              } catch (err) {
                self.postMessage({
                  t: 'packerror', hook: `menuItems:${menuId}`,
                  error: String((err && err.stack) || err),
                })
              }
              views.push([`${regId}:${menuId}:${id}`, items])
            }
          }
        }
        self.postMessage({ t: 'menudynamicview', views })
      }
      if (badgeProviders.size) {
        const updates = []
        for (const [badgeId, rec] of badgeProviders) {
          try {
            const next = materializeBadge(badgeId, rec.source)
            const signature = JSON.stringify([next.data, next.hasClick])
            if (signature !== rec.signature) {
              rec.signature = signature
              updates.push({ badgeId, def: next.data,
                             hasClick: next.hasClick })
            }
          } catch (err) {
            self.postMessage({ t: 'packerror', hook: `badge:${badgeId}`,
                               error: String((err && err.stack) || err) })
          }
        }
        if (updates.length) void rpc('badgeview', { updates })
      }
    })
  }
  const mountedUIs = new Map()    // key -> mount record
  const canvasSurfaces = new Map() // `${nodeId}:${name}` -> surface record
  const nodeCanvasSurfaces = new Map() // graph-scoped whole-node content

  function checkedNodeCanvasBounds(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
        Object.keys(value).some((key) => !['x', 'y', 'width', 'height'].includes(key))) {
      throw new TypeError('invalid node canvas bounds')
    }
    const { x, y, width, height } = value
    if (![x, y, width, height].every((n) => typeof n === 'number' && Number.isFinite(n)) ||
        Math.abs(x) > 8192 || Math.abs(y) > 8192 || width < 1 || height < 1 ||
        width > 8192 || height > 8192 || Math.ceil(width) * Math.ceil(height) > 16_777_216) {
      throw new RangeError('node canvas bounds exceed finite coordinate or pixel limits')
    }
    return Object.freeze({ x, y, width, height })
  }

  function makeNodeCanvas(ref, def) {
    if (typeof def?.draw !== 'function') throw new TypeError('node canvas draw is required')
    if (def.layer !== undefined && def.layer !== 'foreground') throw new TypeError('invalid node canvas layer')
    let bounds = checkedNodeCanvasBounds(def.bounds)
    const surfaceId = `nc-${seq++}`
    let mounted = false, removed = false, revision = 0, offscreen, key, graphId
    let painting = false, redrawQueued = false
    const identity = () => ({ nodeId: ref.id, graphId, surfaceId })
    const surface = {
      redraw() {
        if (removed || !mounted) return
        if (painting) { revision++; redrawQueued = true; return }
        const frameBounds = bounds
        const frameRevision = ++revision
        offscreen ??= new OffscreenCanvas(1, 1)
        offscreen.width = Math.ceil(frameBounds.width)
        offscreen.height = Math.ceil(frameBounds.height)
        const ctx = wrapContext(offscreen.getContext('2d'))
        ctx.setTransform(1, 0, 0, 1, -frameBounds.x, -frameBounds.y)
        try { def.draw(ctx) } catch (error) {
          self.postMessage({ t: 'packerror', hook: 'node.canvas', error: String(error) })
          return
        }
        painting = true
        let snapshot
        try { snapshot = createImageBitmap(offscreen) } catch (error) {
          painting = false
          self.postMessage({ t: 'packerror', hook: 'node.canvas', error: String(error) })
          return
        }
        Promise.resolve(snapshot).then((bitmap) => {
          if (removed || revision !== frameRevision) { bitmap.close(); return }
          try {
            self.postMessage({ t: 'nodecanvasframe', ...identity(),
              revision: frameRevision, bounds: frameBounds, bitmap }, [bitmap])
          } catch (error) { bitmap.close(); throw error }
        }).catch((error) => {
          self.postMessage({ t: 'packerror', hook: 'node.canvas', error: String(error) })
        }).finally(() => {
          painting = false
          if (redrawQueued && !removed) { redrawQueued = false; surface.redraw() }
        })
      },
      setBounds(value) {
        if (removed) throw new Error('node canvas was removed')
        bounds = checkedNodeCanvasBounds(value)
        surface.redraw()
      },
      remove() {
        if (removed) return
        removed = true
        revision++
        if (offscreen) offscreen.width = offscreen.height = 0
        if (nodeCanvasSurfaces.get(key)?.surfaceId === surfaceId) nodeCanvasSurfaces.delete(key)
        if (mounted) void rpc('nodecanvasremove', identity())
      },
    }
    ref.whenReal(() => {
      if (removed) return
      graphId = ref.snap?.graphId
      key = JSON.stringify([String(graphId), ref.id])
      nodeCanvasSurfaces.get(key)?.surface.remove()
      nodeCanvasSurfaces.set(key, { surfaceId, surface })
      void rpc('nodecanvasmount', { ...identity(), bounds, layer: def.layer }).then(() => {
        mounted = true
        if (removed) { void rpc('nodecanvasremove', identity()); return }
        surface.redraw()
      }, (error) => {
        surface.remove()
        self.postMessage({ t: 'packerror', hook: 'node.canvas', error: String(error) })
      })
    })
    return Object.freeze(surface)
  }

  const escText = (s) => String(s)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  const escAttr = (s) => escText(s).replaceAll('"', '&quot;')

  function serializeStub(child, rec) {
    if (child == null) return ''
    if (typeof child === 'string' || typeof child === 'number') {
      return escText(child)
    }
    if (child.nodeType === 3) return escText(child.textContent ?? '')
    const stub = child.__stub
    if (!stub) return ''
    rec.stubIndex.set(stub.stubId, child)
    if (stub.tagName === 'CANVAS') rec.canvases.add(stub)

    const tag = stub.tagName.toLowerCase()
    const attrs = []
    for (const [k, v] of stub.attributes) {
      if (k.toLowerCase().startsWith('on')) continue
      attrs.push(`${k}="${escAttr(v)}"`)
    }
    if (stub.classes.size) attrs.push(`class="${escAttr([...stub.classes].join(' '))}"`)
    for (const k of ['id', 'value', 'placeholder', 'type', 'width', 'height',
                     'min', 'max', 'step', 'title', 'alt', 'src']) {
      const v = stub.props.get(k)
      if (v !== undefined && v !== null) attrs.push(`${k}="${escAttr(v)}"`)
    }
    if (stub.props.get('checked')) attrs.push('checked')
    if (stub.props.get('disabled')) attrs.push('disabled')
    const styleEntries = Object.entries(stub.style).filter(
      ([k, v]) => typeof v === 'string' && v !== '' &&
        !['setProperty', 'removeProperty', 'getPropertyValue'].includes(k))
    if (styleEntries.length) {
      // `cssText` is a whole declaration block, not a property — hyphenating
      // it produced a literal `css-text:` rule and dropped every style in it.
      const css = styleEntries
        .map(([k, v]) => k === 'cssText'
          ? String(v)
          : `${k.replaceAll(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}:${v}`)
        .join(';')
      attrs.push(`style="${escAttr(css)}"`)
    }
    attrs.push(`data-key="${stub.stubId}"`)
    const events = [...stub.listeners.keys()]
    if (events.length) {
      attrs.push(`data-on="${events.map((e) => `${e}:${stub.stubId}`).join(' ')}"`)
    }

    const open = `<${tag} ${attrs.join(' ')}>`
    if (tag === 'br' || tag === 'hr' || tag === 'img') return open
    // innerHTML/textContent CLEAR the children when written (the setter does
    // that), so children appended afterwards must win — `el.innerHTML = '';
    // el.appendChild(canvas)` is the corpus idiom for "reset then rebuild",
    // and preferring the stored string made that canvas invisible.
    const inner = stub.childNodes.length
      ? stub.childNodes.map((c) => serializeStub(c, rec)).join('')
      : stub.props.has('innerHTML')
        ? String(stub.props.get('innerHTML')) // host sanitizes; nothing runs here
        : stub.props.has('textContent')
          ? escText(stub.props.get('textContent'))
          : ''
    return `${open}${inner}</${tag}>`
  }

  function flushMount(rec) {
    rec.stubIndex = new Map()
    rec.canvases = new Set()
    const markup = rec.container.childNodes
      .map((c) => serializeStub(c, rec))
      .join('')
    if (rec.kind === 'dialog') {
      if (!rec.registered || rec.destroyed) return
      void rpc('dialogupdate', { dialogId: rec.dialogId, markup })
    } else {
      void rpc('ui', {
        key: rec.key, nodeId: rec.nodeId, name: rec.name, markup,
      })
    }
    for (const stub of rec.canvases) {
      if (!stub.offscreen) continue
      createImageBitmap(stub.offscreen).then((bitmap) => {
        self.postMessage({ t: 'uibitmap', key: rec.key, stubId: stub.stubId,
                           bitmap }, [bitmap])
      }, () => {})
    }
  }

  let uiFlushQueued = false
  flushDirtyUI = () => {
    if (uiFlushQueued || !mountedUIs.size) return
    uiFlushQueued = true
    // A microtask coalesces a burst of DOM writes, but it is NOT enough on
    // its own: editors construct themselves in a `setTimeout` (deferred so a
    // saved workflow finishes restoring first), so the canvas they append
    // lands in a later macrotask. A microtask-only flush shipped the tree
    // without it and nothing re-armed — the editor rendered as an empty box.
    // The macrotask hop is what catches deferred construction.
    queueMicrotask(() => {
      uiFlushQueued = false
      for (const rec of mountedUIs.values()) flushMount(rec)
      dirtySince = Date.now()
    })
  }

  // A short settling pass after the last write: deferred constructors, image
  // decodes and layout-dependent sizing all land after the microtask that
  // flushed their parent. Cheap because a flush with no change is a no-op
  // markup diff on the host, and it stops once things go quiet.
  let dirtySince = 0
  setInterval(() => {
    if (!mountedUIs.size || !dirtySince) return
    if (Date.now() - dirtySince > 3000) { dirtySince = 0; return }
    for (const rec of mountedUIs.values()) flushMount(rec)
  }, 250)

  function dispatchStubEvent(rec, stubId, detail) {
    const el = rec.stubIndex.get(stubId)
    const stub = el && el.__stub
    if (!stub) return
    const type = detail?.type
    if (detail && 'value' in detail && detail.value !== undefined) {
      stub.props.set('value', detail.value)
    }
    if (detail && 'checked' in detail && detail.checked !== undefined) {
      stub.props.set('checked', detail.checked)
    }
    const event = {
      ...detail,
      type,
      target: el,
      currentTarget: el,
      preventDefault() {},
      stopPropagation() {},
    }
    for (const fn of stub.listeners.get(type) || []) {
      try {
        fn(event)
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `ui:${type}`,
                           error: String((err && err.stack) || err) })
      }
    }
  }

  const graphState = { epoch: undefined, nodes: new Map() }
  let lastCtx = { pointer: undefined, selection: [] }
  let executingNodeId
  const executingListeners = new Set()
  let backendBase = ''
  let backendAssetBase = ''
  let routeBase = ''
  const nodeViews = new Map() // real id -> view (stable identity for a pack)
  let subSeq = 1
  const subHandlers = new Map() // subId -> fn

  const mergeSnapshot = (snap) => {
    if (snap && snap.id) graphState.nodes.set(String(snap.id), snap)
  }

  const subscribe = (path, args, fn) => {
    const subId = `s${subSeq++}`
    subHandlers.set(subId, fn)
    rpc('sub', { subId, path, args }).catch((err) => {
      subHandlers.delete(subId)
      console.error(`[sandbox] subscription ${path} refused:`, err)
    })
    return () => { subHandlers.delete(subId); void rpc('unsub', { subId }) }
  }

  const miss = (what) => {
    throw new Error(
      `[sandbox] ${what} is not yet available to a sandboxed pack.`)
  }

  function widgetView(ref, name) {
    const find = () => {
      if (ref.id) {
        const current = graphState.nodes.get(ref.id)
        if (current && (!ref.snap || current.graphId === ref.snap.graphId)) ref.snap = current
      }
      const snap = ref.snap
      const w = snap && snap.widgets && snap.widgets.find((x) => x.name === name)
      if (!w) throw new Error(`[sandbox] widget '${name}' is gone from node ${ref.id}`)
      return w
    }
    return {
      get name() { return name },
      get widgetType() { return find().widgetType },
      getLabel() { return find().label },
      getValue() { return find().value },
      getOptions() {
        const options = find().options
        return options === undefined ? undefined : structuredClone(options)
      },
      setOption(key, value) {
        if (typeof key !== 'string' || key.length < 1 || key.length > 128 ||
            /[\0-\x1f\x7f]/.test(key) ||
            new Set(['__proto__', 'prototype', 'constructor']).has(key)) {
          throw new TypeError('widget option key is invalid')
        }
        ;(find().options ??= {})[key] = value
        ref.op('widgets.setOption', [name, key, value])
      },
      setLabel(label) {
        if (typeof label !== 'string' || label.length > 1024 || /\0/.test(label)) {
          throw new TypeError('widget label must be bounded text')
        }
        find().label = label
        ref.op('widgets.setLabel', [name, label])
      },
      setValue(v) {
        find().value = v // optimistic; the nodeop reply re-syncs the snapshot
        ref.op('widgets.setValue', [name, v])
      },
      setHidden(hidden) {
        find().hidden = !!hidden
        ref.op('widgets.setHidden', [name, !!hidden])
      },
      isHidden() { return !!find().hidden },
      setDisabled(disabled) {
        find().disabled = !!disabled
        ref.op('widgets.setDisabled', [name, !!disabled])
      },
      isDisabled() { return !!find().disabled },
      isSerialized() { return find().serialized !== false },
      getHeight() { return find().height },
      on(event, fn) {
        const subId = `s${subSeq++}`
        subHandlers.set(subId, fn)
        ref.whenReal(() =>
          rpc('subwidget', { subId, nodeId: ref.id, name, event }).catch((err) =>
            console.error(`[sandbox] widget '${name}' on('${event}'):`, err)))
        return () => { subHandlers.delete(subId); void rpc('unsub', { subId }) }
      },
      mount() { miss(`widgets.get('${name}').mount (Remote-DOM lane)`) },
    }
  }

  function slotCollection(ref, side) {
    const list = () => {
      if (ref.id) ref.snap = graphState.nodes.get(ref.id) || ref.snap
      return (ref.snap && ref.snap[side]) || []
    }
    const slotFor = (slotId) => list().find((slot) => slot.id === slotId)
    const indexOf = (slotId) => list().findIndex((slot) => slot.id === slotId)
    const find = (slotRef) => {
      if (typeof slotRef === 'string') {
        return list().find((slot) => slot.id === slotRef) ||
          list().find((slot) => slot.name === slotRef)
      }
      return list()[slotRef && slotRef.index]
    }
    const view = (initial) => {
      const slotId = initial.id
      const current = () => slotFor(slotId) || initial
      const handle = {
        get id() { return slotId },
        get index() { return indexOf(slotId) },
        get name() { return current().name },
        get type() { return current().type },
        get label() { return current().label },
        get isConnected() { return !!current().connected },
        get connectedType() { return current().connectedType },
        get isWidgetInput() { return !!current().isWidgetInput },
        widgetConfig: side === 'inputs'
          ? () => structuredClone(current().widgetConfig)
          : undefined,
        link: side === 'inputs'
          ? () => current().link ? { ...current().link } : undefined
          : undefined,
        source: side === 'inputs'
          ? () => (current().sourceNodeId != null
              ? { nodeId: current().sourceNodeId,
                  outputIndex: current().sourceOutput }
              : undefined)
          : undefined,
        resolvedSource: side === 'inputs'
          ? () => current().resolvedSource
              ? structuredClone(current().resolvedSource) : undefined
          : undefined,
        links: side === 'outputs'
          ? () => (current().links || []).map((link) => ({ ...link }))
          : undefined,
        targets: side === 'outputs'
          ? () => (current().targets || []).map((target) => ({ ...target }))
          : undefined,
        modify(patch) {
          const slot = current()
          if (patch && typeof patch === 'object') Object.assign(slot, patch)
          ref.op(`${side}.modify`, [slotId, patch])
        },
        connectTo: side === 'outputs'
          ? (targetId, inputRef) => {
              ref.op('outputs.connectTo', [slotId, String(targetId), inputRef])
              return undefined
            }
          : undefined,
        disconnect: side === 'inputs'
          ? () => {
              const slot = current()
              if (!slot.connected) return false
              slot.connected = false
              delete slot.sourceNodeId
              delete slot.sourceOutput
              ref.op('inputs.disconnect', [slotId])
              return true
            }
          : (targetId) => {
              const slot = current()
              const before = (slot.targets || []).length
              slot.targets = targetId === undefined ? [] :
                (slot.targets || []).filter((target) =>
                  String(target.nodeId) !== String(targetId))
              slot.connected = slot.targets.length > 0
              ref.op('outputs.disconnect', [slotId, targetId])
              return slot.targets.length !== before
            },
        moveLinksTo: side === 'outputs'
          ? (target) => {
              const links = handle.links()
              ref.op('outputs.moveLinksTo', [slotId, target])
              return links
            }
          : undefined,
        snapshot() {
          const slot = current()
          return Object.freeze({
            id: slotId,
            index: indexOf(slotId),
            name: slot.name,
            type: slot.type,
            label: slot.label,
            localizedName: slot.localizedName,
            position: slot.position ? { ...slot.position } : undefined,
            direction: slot.direction,
            shape: slot.shape || 'default',
            isConnected: !!slot.connected,
          })
        },
      }
      return handle
    }
    const collection = {
      all: () => list().map(view),
      ids: () => list().map((slot) => slot.id),
      names: () => list().map((slot) => slot.name),
      at: (index) => {
        const slot = list()[index]
        return slot ? view(slot) : undefined
      },
      get(slotRef) {
        const slot = find(slotRef)
        return slot ? view(slot) : undefined
      },
      byId(id) {
        const slot = list().find((item) => item.id === id)
        return slot ? view(slot) : undefined
      },
      byName(name) {
        const matches = list().filter((slot) => slot.name === name)
        return matches.length === 1 ? view(matches[0]) : undefined
      },
      add(name, type, options) {
        const slots = list()
        const slot = {
          id: `guest:${side}:${regSeq++}`,
          index: slots.length,
          name,
          type: Array.isArray(type) ? type.join(',') : String(type),
          label: undefined,
          connected: false,
          shape: options?.shape || 'default',
          localizedName: options?.localizedName,
          position: options?.position,
          direction: options?.direction,
          isWidgetInput: !!options?.widget,
          widgetConfig: options?.widgetConfig,
        }
        slots.push(slot)
        ref.op(`${side}.add`, [name, type, options])
        return view(slot)
      },
      remove(slotRef) {
        const slots = list()
        const slot = find(slotRef)
        if (!slot) return false
        slots.splice(slots.indexOf(slot), 1)
        slots.forEach((item, index) => { item.index = index })
        ref.op(`${side}.remove`, [slot.id])
        return true
      },
      reorder(names) {
        const slots = list()
        const currentNames = slots.map((slot) => slot.name)
        if (names.length !== currentNames.length ||
            [...names].sort().join('\0') !==
              [...currentNames].sort().join('\0')) {
          throw new Error(`${side}.reorder needs a permutation of current slots`)
        }
        const byName = new Map(slots.map((slot) => [slot.name, slot]))
        ref.snap[side] = names.map((name, index) => {
          const slot = byName.get(name)
          slot.index = index
          return slot
        })
        ref.op(`${side}.reorder`, [[...names]])
      },
      get length() { return list().length },
      *[Symbol.iterator]() { yield* collection.all() },
    }
    return collection
  }

  function makeNodeRef(id, snap) {
    const ref = {
      id: id ? String(id) : null,
      snap: snap || (id ? graphState.nodes.get(String(id)) : null),
      queue: [],
      op(op, args) {
        if (!ref.id) { ref.queue.push([op, args]); return }
        rpc('nodeop', { nodeId: ref.id, graphId: ref.snap?.graphId, op, args }).then((snapshot) => {
          ref.snap = snapshot
          mergeSnapshot(snapshot)
        },
          (err) => console.error(`[sandbox] ${op} on ${ref.id}:`, err))
      },
      whenReal(fn) {
        if (ref.id) fn()
        else ref.queue.push(fn)
      },
      resolve(realSnap) {
        ref.id = String(realSnap.id)
        ref.snap = realSnap
        mergeSnapshot(realSnap)
        nodeViews.set(ref.id, ref.view)
        for (const item of ref.queue.splice(0)) {
          typeof item === 'function' ? item() : ref.op(item[0], item[1])
        }
      },
    }
    const read = (what, fn) => {
      // Between dispatches the cache may be fresher than the ref's own copy.
      if (ref.id) {
        const current = graphState.nodes.get(ref.id)
        if (current && (!ref.snap || current.graphId === ref.snap.graphId)) ref.snap = current
      }
      if (!ref.snap) {
        throw new Error(
          `[sandbox] ${what} read before the host confirmed this node — ` +
          `a just-added node's state arrives asynchronously.`)
      }
      return fn(ref.snap)
    }
    const optimistic = (patch, op, args) => {
      if (ref.snap) Object.assign(ref.snap, patch)
      ref.op(op, args)
    }
    ref.view = {
      get id() { return ref.id ?? read('id', (s) => s.id) },
      get type() { return read('type', (s) => s.type) },
      get comfyClass() { return read('comfyClass', (s) => s.type) },
      get graphId() { return read('graphId', (s) => s.graphId) },
      getTitle: () => read('getTitle', (s) => s.title),
      getMode: () => read('getMode', (s) => s.mode),
      isCollapsed: () => read('isCollapsed', (s) => !!s.collapsed),
      isPinned: () => read('isPinned', (s) => !!s.pinned),
      getColor: () => read('getColor', (s) => s.color),
      getBgColor: () => read('getBgColor', (s) => s.bgColor),
      getShape: () => read('getShape', (s) => s.shape),
      getPosition: () => read('getPosition', (s) => ({ ...s.position })),
      getSize: () => read('getSize', (s) => ({ ...s.size })),
      getProperties: () => read('getProperties', (s) => ({ ...(s.properties || {}) })),
      getProperty: (k) => read('getProperty', (s) => (s.properties || {})[k]),
      getOutputImages: () => read(
        'getOutputImages', (s) => (s.outputImages || []).slice()),
      getDisplayedImageIndex: () => read(
        'getDisplayedImageIndex', (s) => s.displayedImageIndex),
      setTitle: (v) => optimistic({ title: v }, 'setTitle', [v]),
      setPosition: (v) => optimistic({ position: v }, 'setPosition', [v]),
      setSize: (v) => optimistic({ size: v }, 'setSize', [v]),
      setColor: (v) => optimistic({ color: v }, 'setColor', [v]),
      setBgColor: (v) => optimistic({ bgColor: v }, 'setBgColor', [v]),
      setMode: (v) => optimistic({ mode: v }, 'setMode', [v]),
      setCollapsed: (v) => optimistic({ collapsed: v }, 'setCollapsed', [v]),
      setPinned: (v) => optimistic({ pinned: v }, 'setPinned', [v]),
      setResizable: (v) => {
        if (typeof v !== 'boolean') throw new TypeError('resizable must be boolean')
        ref.op('setResizable', [v])
      },
      setProperty: (k, v) => {
        if (ref.snap) (ref.snap.properties ??= {})[k] = v
        ref.op('setProperty', [k, v])
      },
      setSizeConstraints: (c) => ref.op('setSizeConstraints', [c]),
      isSerializingWidgets: () =>
        read('isSerializingWidgets', (s) => !!s.serializingWidgets),
      setSerializeWidgets: (v) =>
        optimistic({ serializingWidgets: !!v }, 'setSerializeWidgets', [!!v]),
      addBadge: (def) => {
        // Closures stay here. Dynamic providers are materialized after each
        // dispatch; the host sees only the current closed BadgeDef data.
        const badgeId = `b${regSeq++}`
        let removed = false
        ref.whenReal(() => {
          if (removed) return
          try {
            const current = materializeBadge(badgeId, def)
            if (typeof def === 'function') {
              badgeProviders.set(badgeId, {
                source: def,
                signature: JSON.stringify([current.data, current.hasClick]),
              })
            }
            void rpc('badge', { nodeId: ref.id, badgeId, def: current.data,
                                hasClick: current.hasClick })
          } catch (err) {
            self.postMessage({ t: 'packerror', hook: `badge:${badgeId}`,
                               error: String((err && err.stack) || err) })
          }
        })
        return () => {
          removed = true
          badgeProviders.delete(badgeId)
          badgeClicks.delete(badgeId)
          void rpc('badgeremove', { badgeId })
        }
      },
      remove: () => ref.op('remove', []),
      canvas: (def) => makeNodeCanvas(ref, def),
      widgets: (() => {
        const collection = {
        get: (name) => {
          const has = ref.snap && ref.snap.widgets &&
            ref.snap.widgets.some((w) => w.name === name)
          return has ? widgetView(ref, name) : undefined
        },
        all: () => read('widgets.all', (s) =>
          (s.widgets || []).map((w) => widgetView(ref, w.name))),
        names: () => read('widgets.names', (s) =>
          (s.widgets || []).map((w) => w.name)),
        at: (index) => read('widgets.at', (s) => {
          const widget = (s.widgets || [])[index]
          return widget ? widgetView(ref, widget.name) : undefined
        }),
        remove: (name) => {
          const widgets = ref.snap && ref.snap.widgets
          const index = widgets?.findIndex((widget) => widget.name === name) ?? -1
          if (index < 0) return false
          widgets.splice(index, 1)
          ref.op('widgets.remove', [name])
          return true
        },
        reorder: (names) => {
          const widgets = ref.snap && ref.snap.widgets
          if (!widgets) return
          const current = widgets.map((widget) => widget.name)
          if (names.length !== current.length ||
              [...names].sort().join('\0') !== [...current].sort().join('\0')) {
            throw new Error('widgets.reorder needs every current widget name exactly once')
          }
          const byName = new Map(widgets.map((widget) => [widget.name, widget]))
          ref.snap.widgets = names.map((name) => byName.get(name))
          ref.op('widgets.reorder', [[...names]])
        },
        move: (name, toIndex) => {
          const names = collection.names()
          const from = names.indexOf(name)
          if (from < 0) throw new Error(`no widget '${name}' on node ${ref.id}`)
          const target = Math.max(0, Math.min(names.length - 1, Number(toIndex)))
          names.splice(target, 0, names.splice(from, 1)[0])
          collection.reorder(names)
        },
        add: (def) => {
          // Optimistic, and it RETURNS the view: the measured idiom is
          // `.add({...}).on('change', …)`, and GetNode `get`s it right back.
          // Known loss, recorded: an options object whose `values` is a
          // non-enumerable accessor (GetNode's live combo list) does not
          // survive structured clone — dynamic option feeds are a
          // declared-intent-lane row, not something to fake here.
          if (ref.snap) {
            (ref.snap.widgets ??= []).push({
              name: def?.name, widgetType: def?.type, value: def?.value,
            })
          }
          ref.op('widgets.add', [def])
          return widgetView(ref, def?.name)
        },
        mount: (def) => {
          const name = def?.name || 'panel'
          ref.whenReal(() => {
            const key = `${ref.id}:${name}`
            const container = makeStubElement('div')
            const rec = { key, nodeId: ref.id, name, container,
                          stubIndex: new Map(), canvases: new Set() }
            mountedUIs.set(key, rec)
            uiHandlers.set(key, (action, detail) =>
              dispatchStubEvent(rec, action, detail))
            try {
              def?.render?.(container)
            } catch (err) {
              self.postMessage({ t: 'packerror', hook: `mount:${name}`,
                                 error: String((err && err.stack) || err) })
            }
            flushMount(rec)
          })
          // The real widget exists host-side after the flush; until the next
          // snapshot refresh, reads through this view answer from optimism.
          if (ref.snap) {
            (ref.snap.widgets ??= []).push({ name, widgetType: 'mounted' })
          }
          return widgetView(ref, name)
        },
        canvas: (def) => {
          const name = def?.name || 'canvas'
          const rec = { def, size: null, offscreen: null, nodeId: null }
          const surf = {
            redraw() {
              // A zero dimension is pre-layout: the host's draw pass reports
              // again when the widget gets real height, and that resend
              // re-triggers this.
              if (!rec.size || !rec.nodeId) return
              if (!(rec.size[0] > 0) || !(rec.size[1] > 0)) return
              rec.offscreen ??= new OffscreenCanvas(rec.size[0], rec.size[1])
              if (rec.offscreen.width !== rec.size[0]) rec.offscreen.width = rec.size[0]
              if (rec.offscreen.height !== rec.size[1]) rec.offscreen.height = rec.size[1]
              try {
                const ctx = wrapContext(rec.offscreen.getContext('2d'))
                ctx.clearRect(0, 0, rec.size[0], rec.size[1])
                def?.draw?.(ctx, [...rec.size])
              } catch (err) {
                self.postMessage({ t: 'packerror', hook: `canvas:${name}`,
                                   error: String((err && err.stack) || err) })
                return
              }
              createImageBitmap(rec.offscreen).then((bitmap) => {
                self.postMessage({ t: 'canvasbitmap', nodeId: rec.nodeId,
                                   name, bitmap }, [bitmap])
              }, (err) => {
                self.postMessage({ t: 'packerror', hook: `canvas:${name}:bitmap`,
                                   error: String(err) })
              })
            },
          }
          ref.whenReal(() => {
            rec.nodeId = ref.id
            canvasSurfaces.set(`${ref.id}:${name}`, rec)
            const handlers = [
              'onPointerDown', 'onPointerMove', 'onPointerUp', 'onContextMenu',
            ].filter((key) => typeof def?.[key] === 'function')
            const opts = {}
            for (const [key, value] of Object.entries(def || {})) {
              if (key !== 'draw' && !handlers.includes(key)) opts[key] = value
            }
            void rpc('canvasmount', { nodeId: ref.id, name, opts, handlers })
          })
          rec.surf = surf
          return surf
        },
        get length() {
          return (ref.snap && ref.snap.widgets || []).length
        },
        *[Symbol.iterator]() {
          yield* collection.all()
        },
      }
      return collection
      })(),
      inputs: slotCollection(ref, 'inputs'),
      outputs: slotCollection(ref, 'outputs'),
      snapshot: () => read('snapshot', (s) => ({ ...s })),
    }
    if (ref.id) nodeViews.set(ref.id, ref.view)
    return ref
  }

  function viewFor(id, snap) {
    const key = String(id)
    if (snap) mergeSnapshot(snap)
    const existing = nodeViews.get(key)
    if (existing && (!snap || existing.graphId === snap.graphId)) return existing
    if (!graphState.nodes.has(key)) return undefined
    return makeNodeRef(key).view
  }

  const updateExecutingNode = (snap) => {
    if (snap && snap.id != null) {
      mergeSnapshot(snap)
      executingNodeId = String(snap.id)
    } else {
      executingNodeId = undefined
    }
    const view = executingNodeId === undefined
      ? undefined : viewFor(executingNodeId)
    for (const listener of executingListeners) listener(view)
  }

  const graphApi = {
    node: (id) => viewFor(id),
    nodes: () => [...graphState.nodes.keys()].map((id) => viewFor(id)),
    nodesOfType: (type) => [...graphState.nodes.values()]
      .filter((s) => s.type === type)
      .map((s) => viewFor(s.id)),
    selection: () => (lastCtx.selection || [])
      .map((id) => viewFor(id))
      .filter(Boolean),
    select: (nodes, options) => {
      const ids = (nodes || []).map((n) => String(n && n.id ? n.id : n))
      void rpc('graphop', { op: 'select', args: [ids, options] })
    },
    add: (type, init) => {
      const ref = makeNodeRef(null)
      rpc('graphop', { op: 'add', args: [type, init] }).then(
        (snapArg) => ref.resolve(snapArg),
        (err) => console.error(`[sandbox] graph.add('${type}'):`, err))
      return ref.view
    },
    remove: (id) => { void rpc('graphop', { op: 'remove', args: [String(id)] }) },
    centerOn: (node) => {
      void rpc('graphop', { op: 'centerOn', args: [String(node && node.id ? node.id : node)] })
    },
    pointerPosition: () => lastCtx.pointer,
    root: () => graphApi,
    subgraphs: () => miss('graph.subgraphs'),
    links: () => miss('graph.links'),
    groups: () => miss('graph.groups'),
    nodeAt: () => miss('graph.nodeAt'),
  }

  const backendApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'url') {
        return (path) =>
          backendBase.replace(/\/$/, '') + '/' + String(path).replace(/^\//, '')
      }
      if (p === 'ownUrl') {
        return (path) => {
          if (!routeBase) throw new Error('this pack declares no routes')
          const tail = String(path).replace(/^\//, '')
          return backendBase.replace(/\/$/, '') + '/ext/' + routeBase + '/' + tail
        }
      }
      if (p === 'ownFetch') {
        return (path, init) => {
          if (!routeBase) throw new Error('this pack declares no routes')
          const tail = String(path).replace(/^\//, '')
          return backendApi.fetch('/ext/' + routeBase + '/' + tail, init)
        }
      }
      if (p === 'assetUrl') {
        return (path) => backendAssetBase.replace(/\/$/, '') + '/' +
          String(path).replace(/^\//, '')
      }
      if (p === 'on') return (event, fn) => subscribe('backend.on', [event], fn)
      if (p === 'fetch') {
        return async (path, init) => {
          const r = await rpc('backendfetch', { path, init })
          return {
            ok: r.ok, status: r.status,
            json: async () => JSON.parse(r.body),
            text: async () => r.body,
          }
        }
      }
      return proxy(['comfy', 'backend', p])
    },
  })

  const systemApi = Object.freeze({
    monitor: () => rpc('systemmonitor', {}),
  })

  const workflowApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'documentId') return () => graphState.epoch
      if (p === 'registerImporter') {
        return (def) => {
          if (!def || typeof def !== 'object' || Array.isArray(def) ||
              typeof def.id !== 'string' ||
              !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(def.id)) {
            throw new TypeError('workflow importer requires a valid id')
          }
          if (typeof def.parse !== 'function') {
            throw new TypeError('workflow importer requires a parse function')
          }
          if (def.enabled !== undefined && typeof def.enabled !== 'function') {
            throw new TypeError('workflow importer enabled must be a function')
          }
          if (workflowImporters.has(def.id)) {
            throw new Error(`duplicate workflow importer '${def.id}'`)
          }
          const data = {
            id: def.id,
            mimeTypes: def.mimeTypes,
            extensions: def.extensions,
            maxBytes: def.maxBytes,
          }
          const rec = { parse: def.parse, enabled: def.enabled }
          workflowImporters.set(def.id, rec)
          void rpc('importerreg', { def: data }).catch((err) => {
            if (workflowImporters.get(def.id) === rec) {
              workflowImporters.delete(def.id)
            }
            console.error(`[sandbox] workflow importer '${def.id}':`, err)
          })
          let active = true
          return () => {
            if (!active) return
            active = false
            if (workflowImporters.get(def.id) === rec) {
              workflowImporters.delete(def.id)
            }
            void rpc('importerremove', { importerId: def.id }).catch(
              (err) => console.error(
                `[sandbox] remove workflow importer '${def.id}':`, err))
          }
        }
      }
      return proxy(['comfy', 'workflow', p])
    },
  })

  const widgetsApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'registerComboPreview') {
        return (definition) => {
          const data = comboPreviewData(definition)
          if (comboPreviewRegistrations.has(data.id)) {
            throw new Error(`duplicate combo preview '${data.id}'`)
          }
          comboPreviewRegistrations.add(data.id)
          void rpc('combopreviewreg', { def: data }).catch((err) => {
            comboPreviewRegistrations.delete(data.id)
            console.error(`[sandbox] combo preview '${data.id}':`, err)
          })
          let active = true
          return () => {
            if (!active) return
            active = false
            comboPreviewRegistrations.delete(data.id)
            void rpc('combopreviewremove', { previewId: data.id }).catch(
              (err) => console.error(
                `[sandbox] remove combo preview '${data.id}':`, err))
          }
        }
      }
      if (p === 'assignComboPreview') {
        return async (assignment) => {
          const data = comboPreviewAssignmentData(assignment)
          await rpc('combopreviewassign', { assignment: data })
        }
      }
      return proxy(['comfy', 'widgets', p])
    },
  })

  // ---- settings: the sync slice -------------------------------------------
  //
  // `settings.get()` is synchronous in the published API, and packs gate
  // whole features on it — `if (!settings.get('X.enabled')) return`. Through
  // the generic RPC that read returned a PROMISE, which is truthy, so every
  // such gate silently passed regardless of the stored value. And a declare
  // carrying an `onChange` function died in postMessage (DataCloneError on an
  // unawaited promise), so the setting was never declared at all.
  //
  // Here: declares seed a local cache with the default and cross as data;
  // the host answers back the STORED value (a user's saved choice beats the
  // default) and later changes arrive on the subscription channel — both
  // update the cache and invoke the pack's own onChange, kept local. Reads
  // answer from the cache synchronously. A read of an id this pack never
  // declared (a core preference) has no cache entry: it answers undefined
  // once, loudly, and backfills for the next read.
  const settingsCache = new Map()
  const settingsWarned = new Set()

  const settingsApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'declare') {
        return (def) => {
          const { onChange, ...data } = def || {}
          if (!settingsCache.has(data.id)) {
            settingsCache.set(data.id, data.defaultValue)
          }
          const applyValue = (value) => {
            if (value === settingsCache.get(data.id)) return
            settingsCache.set(data.id, value)
            try {
              onChange?.(value)
            } catch (err) {
              self.postMessage({ t: 'packerror', hook: `settings:${data.id}`,
                                 error: String((err && err.stack) || err) })
            }
          }
          subscribe('settings.onChange', [data.id], applyValue)
          rpc('settingsdeclare', { def: data }).then(
            (stored) => { if (stored !== undefined) applyValue(stored) },
            (err) => console.error(`[sandbox] settings.declare '${data.id}':`, err))
        }
      }
      if (p === 'get') {
        return (id) => {
          if (settingsCache.has(id)) return settingsCache.get(id)
          if (!settingsWarned.has(id)) {
            settingsWarned.add(id)
            console.warn(
              `[sandbox] settings.get('${id}'): not declared by this pack — ` +
              'answering undefined once and backfilling asynchronously.')
            rpc('call', { path: 'comfy.settings.get', args: [id] }).then(
              (v) => settingsCache.set(id, v), () => {})
          }
          return undefined
        }
      }
      if (p === 'set') {
        return (id, value) => {
          settingsCache.set(id, value)
          return rpc('call', { path: 'comfy.settings.set', args: [id, value] })
        }
      }
      if (p === 'onChange') {
        return (id, fn) =>
          subscribe('settings.onChange', [id], (value, ...rest) => {
            settingsCache.set(id, value)
            return fn(value, ...rest)
          })
      }
      return proxy(['comfy', 'settings', p])
    },
  })

  const localizationApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'registerCatalog') {
        return (locale, catalog) => {
          const data = localizationCatalogData(locale, catalog)
          if (localizationRegistrations.has(data.locale)) {
            throw new Error(
              `duplicate localization catalog '${data.locale}'`)
          }
          localizationRegistrations.add(data.locale)
          void rpc('localereg', data).catch((err) => {
            localizationRegistrations.delete(data.locale)
            console.error(
              `[sandbox] localization catalog '${data.locale}':`, err)
          })
          let active = true
          return () => {
            if (!active) return
            active = false
            localizationRegistrations.delete(data.locale)
            void rpc('localeremove', { locale: data.locale }).catch(
              (err) => console.error(
                `[sandbox] remove localization '${data.locale}':`, err))
          }
        }
      }
      return proxy(['comfy', 'localization', p])
    },
  })

  /**
   * The root `comfy`. Members implemented locally must win over the generic
   * path proxy, which would otherwise shadow them: its `get` trap answers every
   * key, so a plain `comfy.ui = ui` assignment is silently ignored.
   */
  // ---- commands -----------------------------------------------------------
  //
  // `register` carries functions — `run` always, `label` sometimes (a toggle
  // whose caption reads current state). The closure stays here and the host
  // gets a trampoline. A label FUNCTION is read synchronously by the host
  // each time it is shown, so it cannot stay live across the boundary: it is
  // evaluated once at registration and crosses as that string, and the
  // dynamic re-read is a recorded declared-intent-lane row alongside menu
  // `when`. Better a stable caption than a registration that dies in
  // postMessage with the command silently missing — which is what happened.
  const commandRuns = new Map() // id -> run closure

  const commandsApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'register') {
        return (def) => {
          const { run, label, ...data } = def || {}
          commandRuns.set(data.id, run)
          let staticLabel = label
          if (typeof label === 'function') {
            try {
              staticLabel = String(label())
            } catch {
              staticLabel = data.id
            }
          }
          rpc('commandreg', { def: { ...data, label: staticLabel } }).catch(
            (err) => console.error(`[sandbox] commands.register '${data.id}':`, err))
        }
      }
      return proxy(['comfy', 'commands', p])
    },
  })

  // Listener-taking queue methods need the subscription channel. Sending a
  // callback through the ordinary RPC proxy would ask structuredClone to copy
  // a function and fail before the host sees the registration. The host keeps
  // the real listener and this worker keeps the pack closure, exactly like the
  // other documented event methods below.
  const queueRoot = proxy(['comfy', 'queue'])
  const queueApi = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'onBeforeRun') {
        return (fn) => subscribe('queue.onBeforeRun', [], fn)
      }
      if (p === 'onAfterRun') {
        return (fn) => subscribe('queue.onAfterRun', [], fn)
      }
      if (p === 'onRejected') {
        return (fn) => subscribe('queue.onRejected', [], fn)
      }
      return queueRoot[p]
    },
  })

  const overrides = new Map([
    ['defs', defs], ['ui', ui], ['element', element],
    ['graph', graphApi], ['backend', backendApi], ['workflow', workflowApi],
    ['system', systemApi],
    ['widgets', widgetsApi],
    ['localization', localizationApi],
    ['settings', settingsApi], ['commands', commandsApi], ['queue', queueApi],
    ['on', (event, fn) => subscribe('on', [event], fn)],
    ['onWorkflowLoaded', (fn) => subscribe('onWorkflowLoaded', [], fn)],
    ['onReady', (fn) => subscribe('onReady', [], fn)],
    ['onAppReady', (fn) => subscribe('onReady', [], fn)],
    ['onNodeChanged', (fn, opts) =>
      subscribe('onNodeChanged', opts ? [opts] : [], fn)],
    ['onNodeDragEnd', (fn) => subscribe('onNodeDragEnd', [], fn)],
    ['onNodeMoved', (fn) => subscribe('onNodeMoved', [], fn)],
    ['onViewportChanged', (fn) => subscribe('onViewportChanged', [], fn)],
    ['onPreview', (fn) => subscribe('onPreview', [], fn)],
    ['executingNode', () => executingNodeId === undefined
      ? undefined : viewFor(executingNodeId)],
    ['executionNode', (id) => viewFor(String(id))],
    ['onExecutingNodeChanged', (fn) => {
      if (typeof fn !== 'function') {
        throw new TypeError('onExecutingNodeChanged requires a listener')
      }
      executingListeners.add(fn)
      return () => executingListeners.delete(fn)
    }],
  ])
  const rootProxy = proxy(['comfy'])
  const comfy = new Proxy(Object.create(null), {
    get(_t, p) {
      if (typeof p !== 'string' || p === 'then') return undefined
      if (p === 'capabilities') return () => capabilities.slice()
      if (overrides.has(p)) return overrides.get(p)
      return rootProxy[p]
    },
    has(_t, p) { return overrides.has(p) || typeof p === 'string' },
  })

  self.addEventListener('message', async (e) => {
    const m = e.data
    if (!m || !m.t) return

    // URL first: a URL-imported module has a base URL, so a multi-file pack
    // resolves its `./helper.js` imports. That fetch is cross-origin from
    // this opaque origin and only succeeds when the asset server answers
    // CORS. The probe distinguishes "origin refuses CORS" (fall back to a
    // blob of the entry source, single-file semantics) from "the pack threw
    // while evaluating" (a real load error the author must see, never masked
    // by a second evaluation attempt).
    async function importEntry(packUrl, blobUrl) {
      let mode = 'url'
      let probe = ''
      if (blobUrl) {
        if (!/^https?:/.test(packUrl || '')) mode = 'source'
        else {
          try {
            const res = await fetch(packUrl, { method: 'GET' })
            if (!res.ok) { mode = 'source'; probe = `HTTP ${res.status}` }
          } catch (err) {
            mode = 'source'
            probe = String(err)
          }
        }
      }
      try {
        await import(mode === 'url' ? packUrl : blobUrl)
      } catch (err) {
        // Name which path failed and why the fallback was taken, or the
        // failure reads as the wrong lane's bug.
        err.message = `[${mode} mode${probe ? `; url probe: ${probe}` : ''}] ${err.message}`
        throw err
      }
      return mode
    }
    const reportLoad = async (packUrl, blobUrl) => {
      try {
        const mode = await importEntry(packUrl, blobUrl)
        while (registrationPromises.size) {
          await Promise.all([...registrationPromises])
        }
        self.postMessage({ t: 'loaded', pack: self.__pack, url: packUrl, mode })
      } catch (err) {
        // `message` first: the stack string is a snapshot taken at throw time,
        // so the mode/probe prefix importEntry adds never appears in it.
        self.postMessage({ t: 'loaderror', pack: self.__pack, url: packUrl,
                           error: String((err && err.message) || err),
                           stack: String((err && err.stack) || '') })
      }
    }

    if (m.t === 'init') {
      capabilities = m.capabilities || []
      defCatalogue = (m.boot && m.boot.defs) || []
      defsByType = new Map(defCatalogue.map((d) => [d.type, d]))
      backendBase = (m.boot && m.boot.backendBase) || ''
      backendAssetBase = (m.boot && m.boot.backendAssetBase) || backendBase
      routeBase = (m.boot && m.boot.routeBase) || ''
      updateExecutingNode(m.boot && m.boot.executingNode)
      self.comfy = comfy
      self.__pack = m.name
      if (m.boot && m.boot.executionLifecycle) {
        subscribe('onExecutingNodeChanged', [], updateExecutingNode)
      }
      await reportLoad(m.packUrl, m.packBlobUrl)
      return
    }

    if (m.t === 'epoch') {
      // A document swap: DISCARD, never patch. Views survive by identity but
      // re-read through the fresh cache; a view whose node did not come back
      // reads as gone, which is the truth.
      graphState.epoch = m.documentId
      graphState.nodes = new Map()
      for (const snap of m.nodes || []) mergeSnapshot(snap)
      refreshMaterializedViews()
      return
    }

    if (m.t === 'nodeAdded') {
      mergeSnapshot(m.node)
      refreshMaterializedViews()
      return
    }
    if (m.t === 'nodeRemoved') {
      graphState.nodes.delete(String(m.nodeId))
      nodeViews.delete(String(m.nodeId))
      return
    }

    if (m.t === 'event') {
      const fn = subHandlers.get(m.subId)
      if (!fn) return
      try {
        await fn(...(m.args || []))
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `event:${m.subId}`,
                           error: String((err && err.stack) || err) })
      }
      return
    }

    if (m.t === 'uirects') {
      for (const [stubId, rect] of m.rects) stubRects.set(stubId, rect)
      return
    }

    if (m.t === 'nodecanvasremoved') {
      const key = JSON.stringify([String(m.graphId), String(m.nodeId)])
      const rec = nodeCanvasSurfaces.get(key)
      if (rec?.surfaceId === m.surfaceId) rec.surface.remove()
      return
    }

    if (m.t === 'canvassize') {
      // The host owns layout; the surface learns its pixels from the host's
      // own draw pass and re-renders at the real size.
      const rec = canvasSurfaces.get(`${m.nodeId}:${m.name}`)
      if (rec) {
        rec.size = m.size
        rec.surf.redraw()
      }
      return
    }

    if (m.t === 'canvasevent') {
      const rec = canvasSurfaces.get(`${m.nodeId}:${m.name}`)
      const handler = rec?.def?.[m.handler]
      if (typeof handler !== 'function') return
      try {
        const event = Object.freeze({
          type: String(m.event?.type || ''),
          detail: Number.isInteger(m.event?.detail) ? m.event.detail : 0,
          altKey: m.event?.altKey === true,
          ctrlKey: m.event?.ctrlKey === true,
          metaKey: m.event?.metaKey === true,
          shiftKey: m.event?.shiftKey === true,
          button: Number.isInteger(m.event?.button) ? m.event.button : 0,
          buttons: Number.isInteger(m.event?.buttons) ? m.event.buttons : 0,
          clientX: Number.isFinite(m.event?.clientX) ? m.event.clientX : 0,
          clientY: Number.isFinite(m.event?.clientY) ? m.event.clientY : 0,
          preventDefault() {},
          stopPropagation() {},
        })
        await handler({
          x: Number.isFinite(m.x) ? m.x : 0,
          y: Number.isFinite(m.y) ? m.y : 0,
          event,
        })
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `canvas:${m.name}:${m.handler}`,
                           error: String((err && err.stack) || err) })
      }
      return
    }

    if (m.t === 'badgeclick') {
      const onClick = badgeClicks.get(m.badgeId)
      if (!onClick) return
      try {
        await onClick()
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `badge:${m.badgeId}`,
                           error: String((err && err.stack) || err) })
      }
      return
    }

    if (m.t === 'command') {
      const run = commandRuns.get(m.id)
      if (!run) return
      try {
        await run()
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `command:${m.id}`,
                           error: String((err && err.stack) || err) })
      }
      return
    }

    if (m.t === 'uiaction') {
      const run = actionButtonRuns.get(m.id)
      if (!run) return
      try {
        const event = Object.freeze({
          type: 'click',
          altKey: m.event?.altKey === true,
          ctrlKey: m.event?.ctrlKey === true,
          metaKey: m.event?.metaKey === true,
          shiftKey: m.event?.shiftKey === true,
          button: Number.isInteger(m.event?.button) ? m.event.button : 0,
          buttons: Number.isInteger(m.event?.buttons) ? m.event.buttons : 0,
          clientX: Number.isFinite(m.event?.clientX) ? m.event.clientX : 0,
          clientY: Number.isFinite(m.event?.clientY) ? m.event.clientY : 0,
          preventDefault() {},
          stopPropagation() {},
        })
        await run(event)
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({ t: 'packerror', hook: `actionBar:${m.id}:run`,
                           error: String((err && err.stack) || err) })
      }
      return
    }

    // Host-initiated requests: the prompt path asking a pack-defined node's
    // resolver or supplier for its answer. The view is rebuilt entirely from
    // this worker's replica — the host refreshed it just before asking.
    if (m.t === 'importFile') {
      const answer = (ok, value, error) =>
        self.postMessage({ t: 'answer', reqId: m.reqId, ok, value, error })
      const importer = workflowImporters.get(m.importerId)
      if (!importer) {
        return answer(false, null, `no workflow importer '${m.importerId}'`)
      }
      try {
        if (importer.enabled && !(await importer.enabled())) {
          return answer(true, null)
        }
        const bytes = new Uint8Array(m.bytes)
        const context = Object.freeze({ name: m.name, type: m.type })
        return answer(true, await importer.parse(bytes, context))
      } catch (err) {
        return answer(false, null, String((err && err.stack) || err))
      }
    }

    if (m.t === 'resolve' || m.t === 'supply') {
      const definition = definitions.get(m.defType)
      const fn = definition && definition[m.t]
      const answer = (ok, value, error) =>
        self.postMessage({ t: 'answer', reqId: m.reqId, ok, value, error })
      if (!fn) return answer(false, null, `no ${m.t} for '${m.defType}'`)
      try {
        const self_ = replicaView(m.nodeId)
        if (!self_) {
          return answer(false, null,
            `node ${m.nodeId} is not in this worker's replica`)
        }
        const view = m.t === 'resolve'
          ? { self: self_, nodesOfType: replicaNodesOfType }
          : { self: self_, nodesOfType: replicaNodesOfType,
              unconnectedInputs: () => m.unconnected || [] }
        return answer(true, await fn(view))
      } catch (err) {
        return answer(false, null, String((err && err.stack) || err))
      }
    }

    if (m.t === 'promptSerialize') {
      const answer = (ok, value, error) =>
        self.postMessage({ t: 'answer', reqId: m.reqId, ok, value, error })
      const fn = registrations.get(m.regId)?.promptSerialize
      if (!fn) {
        return answer(false, null,
          `no onPromptSerialize callback for registration '${m.regId}'`)
      }
      try {
        const view = viewFor(m.nodeId)
        if (!view) {
          return answer(false, null,
            `node ${m.nodeId} is not in this worker's replica`)
        }
        return answer(true, await fn(view))
      } catch (err) {
        return answer(false, null, String((err && err.stack) || err))
      }
    }

    if (m.t === 'load') {
      // A later entry module of the same pack, imported into this same worker
      // so the pack's modules share one realm and can import each other.
      const blobUrl = m.packSource != null
        ? URL.createObjectURL(new Blob([m.packSource], { type: 'text/javascript' }))
        : null
      await reportLoad(m.packUrl, blobUrl)
      return
    }

    if (m.t === 'ret') {
      const p = pending.get(m.id)
      if (!p) return
      pending.delete(m.id)
      m.ok ? p.resolve(m.value) : p.reject(new Error(m.error))
      return
    }

    // Hook and menu dispatches carry a fresh snapshot of the node plus the
    // gesture context (pointer, selection). The closure receives a real
    // handle over that state — not identity — so its synchronous reads
    // answer from what was true at dispatch.
    if (m.t === 'hook' || m.t === 'menu') {
      const reg = registrations.get(m.regId)
      const fn = m.t === 'hook'
        ? reg && reg.hooks[m.hook]
        : reg && reg.menus && reg.menus.get(m.menuId)
      // `menus` is keyed by the flattened menuId, so a submenu child's run
      // resolves the same way its parent's does.
      if (!fn) return
      if (m.ctx) lastCtx = m.ctx
      const view = m.snapshot
        ? viewFor(m.snapshot.id, m.snapshot)
        : (m.node && viewFor(m.node.id)) || m.node
      try {
        await (m.t === 'hook' ? fn(view, m.arg) : fn(view))
        refreshMaterializedViews()
      } catch (err) {
        // A pack's closure throwing must not kill the worker or the host.
        self.postMessage({
          t: 'packerror',
          hook: m.t === 'hook' ? m.hook : `menu:${m.menuId}`,
          error: String((err && err.stack) || err),
        })
      }
      return
    }

    if (m.t === 'dialogclosed') {
      const rec = mountedUIs.get(`dialog:${m.dialogId}`)
      if (rec?.kind === 'dialog') finishDialog(rec)
      return
    }

    if (m.t === 'dialogkey') {
      const rec = mountedUIs.get(`dialog:${m.dialogId}`)
      if (rec?.kind !== 'dialog' || rec.destroyed ||
          typeof rec.def.onKeyDown !== 'function') return
      try {
        await rec.def.onKeyDown(Object.freeze({ ...m.detail }))
        refreshMaterializedViews()
      } catch (err) {
        self.postMessage({
          t: 'packerror', hook: `dialog:${rec.key}:keydown`,
          error: String((err && err.stack) || err),
        })
      }
      return
    }

    if (m.t === 'uiEvent') {
      const h = uiHandlers.get(m.key)
      if (h) h(m.action, m.detail)
      refreshMaterializedViews()
      return
    }

    if (m.t === 'elemEvent') {
      for (const fn of elemHandlers.get(`${m.name}:${m.event}`) || []) {
        fn(m.detail)
      }
      refreshMaterializedViews()
    }
  })
})()
