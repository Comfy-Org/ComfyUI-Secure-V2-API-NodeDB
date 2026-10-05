export const RESIZE_CONFIG = Object.freeze({
  handleRadiusPx: 10,
  hitRadiusPx: 18,
  fillColor: '#ffb02e',
  strokeColor: '#1a1a1a',
  alpha: 0.95,
  activeScale: 1.35,
  groupMinSize: Object.freeze({ width: 140, height: 80 }),
})

export function handleCenters(bounds) {
  const { x, y, width, height } = bounds
  return Object.freeze([
    Object.freeze({ corner: 'tl', x, y }),
    Object.freeze({ corner: 'tr', x: x + width, y }),
    Object.freeze({ corner: 'bl', x, y: y + height }),
    Object.freeze({ corner: 'br', x: x + width, y: y + height }),
  ])
}

export function hitTestHandles(point, centers, radius) {
  let best
  let bestDistance = radius * radius
  for (const center of centers) {
    const dx = point.x - center.x
    const dy = point.y - center.y
    const distance = dx * dx + dy * dy
    if (distance <= bestDistance) {
      best = center.corner
      bestDistance = distance
    }
  }
  return best
}

export function resizeFromCorner(position, size, corner, delta, minimum) {
  const left = corner === 'tl' || corner === 'bl'
  const top = corner === 'tl' || corner === 'tr'
  const minWidth = Number.isFinite(minimum.width)
    ? Math.max(0, minimum.width)
    : 0
  const minHeight = Number.isFinite(minimum.height)
    ? Math.max(0, minimum.height)
    : 0
  const anchorX = left ? position.x + size.width : position.x
  const anchorY = top ? position.y + size.height : position.y
  const draggedX = (left ? position.x : position.x + size.width) + delta.x
  const draggedY = (top ? position.y : position.y + size.height) + delta.y
  const width = Math.max(minWidth, left ? anchorX - draggedX : draggedX - anchorX)
  const height = Math.max(minHeight, top ? anchorY - draggedY : draggedY - anchorY)
  return Object.freeze({
    position: Object.freeze({
      x: left ? anchorX - width : anchorX,
      y: top ? anchorY - height : anchorY,
    }),
    size: Object.freeze({ width, height }),
  })
}

export function createResizeController() {
  let grab
  return Object.freeze({
    onPointerDown(pointer, target, hitRadius) {
      if (grab || !target) return undefined
      const corner = hitTestHandles(pointer, handleCenters(target.bounds), hitRadius)
      if (!corner) return undefined
      grab = {
        targetId: target.id,
        pointerId: pointer.pointerId,
        corner,
        position: { ...target.position },
        size: { ...target.size },
        start: { x: pointer.x, y: pointer.y },
        minimum: { ...target.minimum },
      }
      return Object.freeze({ type: 'grab', targetId: target.id, corner })
    },
    onPointerMove(pointer) {
      if (!grab || grab.pointerId !== pointer.pointerId) return undefined
      const geometry = resizeFromCorner(
        grab.position,
        grab.size,
        grab.corner,
        { x: pointer.x - grab.start.x, y: pointer.y - grab.start.y },
        grab.minimum,
      )
      return Object.freeze({ type: 'resize', targetId: grab.targetId, ...geometry })
    },
    onPointerEnd(pointerId) {
      if (!grab || (pointerId !== undefined && pointerId !== grab.pointerId)) {
        return undefined
      }
      const targetId = grab.targetId
      grab = undefined
      return Object.freeze({ type: 'release', targetId })
    },
    reset() {
      if (!grab) return undefined
      const targetId = grab.targetId
      grab = undefined
      return Object.freeze({ type: 'release', targetId })
    },
    get locked() {
      return grab !== undefined
    },
    get activeCorner() {
      return grab?.corner
    },
  })
}
