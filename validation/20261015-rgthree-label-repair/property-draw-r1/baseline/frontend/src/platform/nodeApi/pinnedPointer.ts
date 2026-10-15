/** Host renderer routing for an opt-in, pinned node. No graph API escapes. */
export function createPinnedPointerForwarder(options: {
  enabled(): boolean
  forwardToCanvas(event: PointerEvent): void
  doubleClick?(event: PointerEvent): void
}) {
  let lastDown: { time: number; x: number; y: number } | undefined
  let active:
    | { id: number; target?: Element; event: PointerEvent; editing: boolean }
    | undefined
  let pendingClick: { target?: Element; editing: boolean } | undefined

  function clear() {
    active = undefined
    document.removeEventListener('pointerup', released, true)
    document.removeEventListener('pointercancel', released, true)
  }
  function released(event: Event) {
    const pointerId = (event as PointerEvent).pointerId
    // A recipient may capture the original pointer. Then its native release
    // never bubbles through this node, but must still clear our routing state.
    queueMicrotask(() => {
      if (active?.id === pointerId) clear()
    })
  }
  function forward(event: PointerEvent) {
    event.stopPropagation()
    event.preventDefault()
    if (active?.editing) return
    if (active?.target?.isConnected) {
      active.target.dispatchEvent(new PointerEvent(event.type, event))
    } else {
      options.forwardToCanvas(event)
    }
  }
  return {
    handle(event: PointerEvent): boolean {
      if (event.type === 'pointerdown') {
        if (event.button !== 0 || !options.enabled()) return false
        const source = event.currentTarget
        const delta = lastDown ? event.timeStamp - lastDown.time : Infinity
        const doubleClick =
          !!lastDown &&
          delta >= 0 &&
          delta < 300 &&
          Math.hypot(event.clientX - lastDown.x, event.clientY - lastDown.y) <=
            5
        lastDown = doubleClick
          ? undefined
          : { time: event.timeStamp, x: event.clientX, y: event.clientY }
        clear()
        const target =
          !doubleClick && source instanceof Element
            ? document
                .elementsFromPoint(event.clientX, event.clientY)
                .find((element) => {
                  const owner = element.closest('.lg-node[data-node-id]')
                  return (
                    !source.contains(element) &&
                    !!owner &&
                    owner.getAttribute('data-pinned-pass-through') !== 'true'
                  )
                })
            : undefined
        active = {
          id: event.pointerId,
          target: target || undefined,
          event,
          editing: doubleClick
        }
        pendingClick = { target: target || undefined, editing: doubleClick }
        document.addEventListener('pointerup', released, true)
        document.addEventListener('pointercancel', released, true)
        forward(event)
        if (doubleClick) {
          // The first click may have been captured by a lower node, so the
          // browser cannot reliably generate dblclick on this node itself.
          if (source instanceof Element) {
            try {
              source.setPointerCapture(event.pointerId)
            } catch {
              /* detached/synthetic input */
            }
          }
          options.doubleClick?.(event)
        }
        return true
      }
      if (!active || active.id !== event.pointerId) return false
      if (!['pointermove', 'pointerup', 'pointercancel'].includes(event.type))
        return false
      forward(event)
      if (event.type === 'pointercancel') pendingClick = undefined
      if (event.type !== 'pointermove') clear()
      return true
    },
    click(event: MouseEvent): boolean {
      if (!pendingClick || event.button !== 0) return false
      const recipient = pendingClick
      pendingClick = undefined
      event.stopPropagation()
      event.preventDefault()
      // Synthetic pointer events do not produce a DOM click. Replay it only
      // when the native click still targets this node; pointer capture may
      // already have delivered the native click to the underlying recipient.
      if (!recipient.editing && recipient.target?.isConnected) {
        recipient.target.dispatchEvent(new MouseEvent('click', event))
      }
      return true
    },
    dispose() {
      if (active && !active.editing) {
        forward(new PointerEvent('pointercancel', active.event))
      }
      clear()
      lastDown = undefined
      pendingClick = undefined
    }
  }
}
