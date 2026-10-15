import type { LGraphNode } from '@/lib/litegraph/src/LGraphNode'
import { reportError } from '@/platform/telemetry/reportError'

import { ComfyApiError } from './errors'
import type { Bounds } from './nodeHandle'

export interface NodeCanvasDef {
  /** Finite local drawing bounds, independent of the serialized node rectangle. */
  readonly bounds: Bounds
  /** Pack content overlays the ordinary body/slots; no layout or hit-test changes. */
  readonly layer?: 'foreground'
  /** Draws in node-local coordinates into a private canvas. */
  draw(context: CanvasRenderingContext2D): void
}

export interface NodeCanvasHandle {
  setBounds(bounds: Bounds): void
  redraw(): void
  remove(): void
}

interface Surface {
  readonly node: LGraphNode
  readonly canvas: HTMLCanvasElement
  readonly draw: NodeCanvasDef['draw']
  bounds: Readonly<Bounds>
  removed: boolean
}

const surfaces = new WeakMap<LGraphNode, Surface>()
const listeners = new WeakMap<LGraphNode, Set<() => void>>()

export function validateNodeCanvasBounds(value: unknown): Readonly<Bounds> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Canvas bounds must be an object')
  }
  if (
    Object.keys(value).some(
      (key) => !['x', 'y', 'width', 'height'].includes(key)
    ) ||
    !('x' in value) ||
    !('y' in value) ||
    !('width' in value) ||
    !('height' in value)
  ) {
    throw new TypeError('Canvas bounds require x, y, width, and height')
  }
  const { x, y, width, height } = value
  if (
    typeof x !== 'number' ||
    typeof y !== 'number' ||
    typeof width !== 'number' ||
    typeof height !== 'number' ||
    ![x, y, width, height].every(Number.isFinite) ||
    Math.abs(x) > 8192 ||
    Math.abs(y) > 8192 ||
    width < 1 ||
    height < 1 ||
    width > 8192 ||
    height > 8192 ||
    Math.ceil(width) * Math.ceil(height) > 16_777_216
  ) {
    throw new RangeError(
      'Canvas bounds exceed finite coordinate or pixel limits'
    )
  }
  return Object.freeze({ x, y, width, height })
}

function notify(node: LGraphNode) {
  node.setDirtyCanvas(true, true)
  for (const listener of listeners.get(node) ?? []) listener()
}

export function removeNodeCanvas(node: LGraphNode): void {
  const surface = surfaces.get(node)
  if (!surface) return
  surface.removed = true
  surface.canvas.width = surface.canvas.height = 0
  surfaces.delete(node)
  notify(node)
}

export function createNodeCanvas(
  node: LGraphNode,
  def: NodeCanvasDef
): NodeCanvasHandle {
  if (def.layer !== undefined && def.layer !== 'foreground')
    throw new TypeError('Invalid node canvas layer')
  if (typeof def.draw !== 'function')
    throw new TypeError('Canvas draw must be a function')
  const bounds = validateNodeCanvasBounds(def.bounds)
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  if (!context) {
    canvas.width = canvas.height = 0
    const error = new ComfyApiError('A 2D canvas context is unavailable')
    reportError(error, {
      errorType: 'node_canvas_context_unavailable',
      context: { recovery: 'previous_surface_preserved' }
    })
    throw error
  }
  const surface: Surface = {
    node,
    bounds,
    draw: def.draw,
    canvas,
    removed: false
  }
  const drawFrame = () => {
    const { x, y, width, height } = surface.bounds
    surface.canvas.width = Math.ceil(width)
    surface.canvas.height = Math.ceil(height)
    context.setTransform(1, 0, 0, 1, -x, -y)
    surface.draw(context)
  }
  function redraw() {
    if (surface.removed) return
    drawFrame()
    notify(node)
  }
  try {
    drawFrame()
  } catch (error) {
    canvas.width = canvas.height = 0
    reportError(error, {
      errorType: 'node_canvas_initial_draw_failed',
      context: { recovery: 'previous_surface_preserved' }
    })
    throw error
  }
  removeNodeCanvas(node)
  surfaces.set(node, surface)
  notify(node)
  return Object.freeze({
    redraw,
    setBounds(next: Bounds) {
      if (surface.removed) {
        const error = new ComfyApiError('Canvas surface was removed')
        reportError(error, {
          errorType: 'node_canvas_surface_removed',
          context: { recovery: 'mutation_rejected' }
        })
        throw error
      }
      surface.bounds = validateNodeCanvasBounds(next)
      redraw()
    },
    remove() {
      if (surfaces.get(node) === surface) removeNodeCanvas(node)
    }
  })
}

export function drawNodeCanvas(
  node: LGraphNode,
  context: CanvasRenderingContext2D
): void {
  const surface = surfaces.get(node)
  if (!surface || surface.removed) return
  context.drawImage(surface.canvas, surface.bounds.x, surface.bounds.y)
}

/** Drawing may extend beyond the saved, unrotated interaction rectangle. */
export function nodeCanvasBounds(
  node: LGraphNode
): Readonly<Bounds> | undefined {
  return surfaces.get(node)?.bounds
}

export function mountNodeCanvas(
  node: LGraphNode,
  container: HTMLElement
): () => void {
  function update() {
    const surface = surfaces.get(node)
    if (!surface) {
      container.replaceChildren()
      return
    }
    const { x, y, width, height } = surface.bounds
    Object.assign(surface.canvas.style, {
      position: 'absolute',
      left: `${x}px`,
      top: `${y}px`,
      width: `${Math.ceil(width)}px`,
      height: `${Math.ceil(height)}px`,
      pointerEvents: 'none'
    })
    if (surface.canvas.parentElement !== container)
      container.replaceChildren(surface.canvas)
  }
  const set = listeners.get(node) ?? new Set<() => void>()
  listeners.set(node, set)
  set.add(update)
  update()
  return () => {
    set.delete(update)
    if (!set.size) listeners.delete(node)
    container.replaceChildren()
  }
}
