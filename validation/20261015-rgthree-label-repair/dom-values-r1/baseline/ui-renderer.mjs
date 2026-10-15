/**
 * Lane-2 UI renderer (host side): render pack-DESCRIBED UI into a node body.
 *
 * The pack lives in a worker and has no DOM, so it cannot draw. It sends
 * markup; the host sanitises it and mounts it into a **closed shadow root**.
 * That gives the pack ordinary HTML/CSS authoring (the thing that makes custom
 * UI actually easy) while keeping three properties:
 *
 *   1. NO SCRIPT crosses. Elements/attributes are allowlisted; <script>,
 *      event-handler attributes (on*), javascript: URLs and friends are dropped
 *      on the floor. The pack cannot obtain main-realm execution.
 *   2. STYLE IS CONTAINED. A closed shadow root means the pack's CSS cannot
 *      touch the app, and the app's CSS cannot break the pack's UI. `:host`
 *      works, so packs can still style their own container.
 *   3. INTERACTION IS DECLARED. Instead of handlers, the pack marks elements
 *      with `data-on="click:actionName"`. The host attaches the listener and
 *      RPCs the action back to the worker. The pack replies with new markup or
 *      a patch.
 *
 * Cost: ~15KB per shadow root (measured); 200 node widgets ≈ 28MB total.
 */

const ALLOWED_TAGS = new Set([
  'div', 'span', 'p', 'section', 'header', 'footer', 'small', 'strong', 'em',
  'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'hr', 'pre', 'code', 'label',
  'button', 'input', 'select', 'option', 'textarea', 'progress', 'meter',
  'img', 'canvas', 'svg', 'path', 'circle', 'rect', 'line', 'g', 'style',
])

const ALLOWED_ATTRS = new Set([
  'class', 'id', 'title', 'alt', 'width', 'height', 'style',
  'type', 'value', 'placeholder', 'min', 'max', 'step', 'checked', 'disabled',
  'selected', 'readonly', 'rows', 'cols', 'name', 'for', 'colspan', 'rowspan',
  'd', 'cx', 'cy', 'r', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'fill', 'stroke',
  'viewBox', 'stroke-width', 'points', 'transform',
  'data-on', 'data-key', 'data-testid',
])

/** URL attributes get extra scrutiny; only these schemes may appear. */
const URL_ATTRS = new Set(['src', 'href'])
const SAFE_SCHEME = /^(https?:|data:image\/(png|jpe?g|gif|webp|svg\+xml);|blob:)/i

/**
 * Parse untrusted markup into a DocumentFragment containing only allowlisted
 * nodes. Parsing happens in an inert document (DOMParser), so nothing runs and
 * no resource loads during parse.
 */
export function sanitizeMarkup(markup) {
  const doc = new DOMParser().parseFromString(
    `<body>${String(markup)}</body>`, 'text/html')
  const frag = document.createDocumentFragment()

  const clean = (src) => {
    if (src.nodeType === Node.TEXT_NODE) {
      return document.createTextNode(src.nodeValue)
    }
    if (src.nodeType !== Node.ELEMENT_NODE) return null
    const tag = src.tagName.toLowerCase()
    if (!ALLOWED_TAGS.has(tag)) return null            // drop element + subtree

    const el = tag === 'svg' || ['path', 'circle', 'rect', 'line', 'g'].includes(tag)
      ? document.createElementNS('http://www.w3.org/2000/svg', tag)
      : document.createElement(tag)

    for (const { name, value } of Array.from(src.attributes)) {
      const n = name.toLowerCase()
      if (n.startsWith('on')) continue                  // no inline handlers
      if (URL_ATTRS.has(n)) {
        if (!SAFE_SCHEME.test(value.trim())) continue   // no javascript:, etc.
        el.setAttribute(n, value)
        continue
      }
      if (!ALLOWED_ATTRS.has(n)) continue
      el.setAttribute(n, value)
    }
    for (const child of Array.from(src.childNodes)) {
      const c = clean(child)
      if (c) el.appendChild(c)
    }
    return el
  }

  for (const child of Array.from(doc.body.childNodes)) {
    const c = clean(child)
    if (c) frag.appendChild(c)
  }
  return frag
}

/**
 * Mount a pack's UI into `container` (the element `widgets.mount` gave us).
 *
 * @param {HTMLElement} container
 * @param {(action:string, detail:object)=>void} dispatch  called on declared events
 * @returns {{update(markup:string):void, destroy():void}}
 */
export function mountPackUI(container, dispatch, onMeasured) {
  // closed: outside code (including other packs' host-side glue) cannot reach in
  const shadow = container.attachShadow({ mode: 'closed' })
  const listeners = []

  // Everything the pack sends goes inside this wrapper rather than straight
  // into the shadow root, so there is one element whose height IS the content
  // height. The pack cannot measure its own DOM — it has no DOM — so the host
  // measures on its behalf and reports upward.
  const root = document.createElement('div')
  shadow.appendChild(root)

  // The last height we asked the layout to reserve, and how much of a
  // reservation never reaches the element. The legacy renderer spends some on
  // the widget's margins (element height = computedHeight - 2*margin); Nodes
  // 2.0 spends none. Learn it per mount rather than hardcoding either.
  let applied = -1
  let overhead = 0

  function measure() {
    // scrollHeight, NOT getBoundingClientRect(): both renderers draw the graph
    // through a CSS transform, so a client rect is in SCREEN pixels and scales
    // with zoom. Reserving that many *graph units* made the node grow by the
    // zoom factor — at 1.6x the node came out 60% too tall, with the extra
    // showing as dead space under the panel. scrollHeight is a layout metric,
    // unaffected by transforms.
    const need = root.scrollHeight
    if (need <= 0) return // detached: the host only mounts a visible node's element

    const have = container.clientHeight
    if (applied > 0 && have > 0) {
      const observed = applied - have
      if (observed >= 0 && Math.abs(observed - overhead) > 2) overhead = observed
    }

    const next = Math.max(0, Math.ceil(need + overhead))
    if (next === applied) return
    // What DOMWidgetImpl.computeLayoutSize reads when the pack gave no explicit
    // height. Without it the node reserves a flat 50px and clips the panel.
    applied = next
    container.style.setProperty('--comfy-widget-min-height', `${next}px`)
    onMeasured?.(next)
  }

  // Content height changes after render (fonts, images, wrapped text) and on
  // every update; the ALLOCATION changes when the node resizes. Both feed the
  // correction above, so observe both.
  const observer =
    typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
  observer?.observe(root)
  observer?.observe(container)

  function wire() {
    for (const el of shadow.querySelectorAll('[data-on]')) {
      for (const binding of el.getAttribute('data-on').split(/\s+/)) {
        const [evt, action] = binding.split(':')
        if (!evt || !action) continue
        const fn = (e) => {
          const detail = {
            key: el.getAttribute('data-key') || null,
            value: 'value' in el ? el.value : undefined,
            checked: 'checked' in el ? el.checked : undefined,
            type: e.type,
          }
          // Pointer, wheel and key data, when the event carries it — an
          // editor dragging spline points is coordinates or it is nothing.
          for (const k of ['offsetX', 'offsetY', 'clientX', 'clientY',
                           'movementX', 'movementY', 'button', 'buttons',
                           'deltaY', 'deltaX', 'key', 'code',
                           'shiftKey', 'ctrlKey', 'altKey', 'metaKey']) {
            if (e[k] !== undefined) detail[k] = e[k]
          }
          // The pack cannot preventDefault from across an async boundary; a
          // declared listener on the interactive types IS the intent.
          if (e.type === 'wheel' || e.type.startsWith('pointer')) {
            e.preventDefault()
            e.stopPropagation()
          }
          dispatch(action, detail)
        }
        el.addEventListener(evt, fn,
          evt === 'wheel' ? { passive: false } : undefined)
        listeners.push([el, evt, fn])
      }
    }
  }

  function clearListeners() {
    for (const [el, evt, fn] of listeners.splice(0)) el.removeEventListener(evt, fn)
  }

  return {
    update(markup) {
      clearListeners()
      root.replaceChildren(sanitizeMarkup(markup))
      wire()
      // Measure now for the common case, and let the observer catch whatever
      // settles a frame later.
      measure()
    },
    destroy() {
      clearListeners()
      observer?.disconnect()
      root.replaceChildren()
    },
    // test hooks only — the shadow root is closed, so tests need a way in
    __shadow: shadow,
    /**
     * What the panel needs vs what it got. A test asserts these match: too
     * little clips the pack's UI, too much leaves dead space in the node.
     * Both are layout px, so they are comparable at any zoom.
     */
    __size: () => ({
      content: root.scrollHeight,
      element: container.clientHeight,
      reserved: applied,
      overhead,
    }),
  }
}
