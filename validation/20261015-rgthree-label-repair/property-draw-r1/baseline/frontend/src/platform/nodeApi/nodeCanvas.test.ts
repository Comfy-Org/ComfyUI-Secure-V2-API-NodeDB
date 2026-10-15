import { createTestingPinia } from '@pinia/testing'
import { setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { reportError } from '@/platform/telemetry/reportError'
import { createMockCanvasRenderingContext2D } from '@/utils/__tests__/litegraphTestUtils'

import { ComfyApiError } from './errors'
import {
  createNodeCanvas,
  mountNodeCanvas,
  nodeCanvasBounds
} from './nodeCanvas'

vi.mock('@/platform/telemetry/reportError', () => ({ reportError: vi.fn() }))

describe('node canvas failure recovery', () => {
  beforeEach(() => {
    setActivePinia(createTestingPinia({ stubActions: false }))
  })

  const bounds = { x: 0, y: 0, width: 40, height: 20 }
  const canvasPrototype: {
    getContext(contextId: '2d'): CanvasRenderingContext2D | null
  } = HTMLCanvasElement.prototype

  it('retains the mounted surface when a replacement has no 2D context', () => {
    const node = new LGraphNode('Drawing', 'Drawing')
    const context = createMockCanvasRenderingContext2D()
    const getContext = vi
      .spyOn(canvasPrototype, 'getContext')
      .mockReturnValue(context)
    const draw = vi.fn()
    const previous = createNodeCanvas(node, { bounds, draw })
    const container = document.createElement('div')
    const unmount = mountNodeCanvas(node, container)
    const mounted = container.firstChild
    const create = vi.spyOn(document, 'createElement')
    const failedDraw = vi.fn()
    getContext.mockReturnValueOnce(null)

    expect(() => createNodeCanvas(node, { bounds, draw: failedDraw })).toThrow(
      ComfyApiError
    )
    expect(nodeCanvasBounds(node)).toEqual(bounds)
    expect(container.firstChild).toBe(mounted)
    expect(create.mock.results.at(-1)?.value).toMatchObject({
      width: 0,
      height: 0,
      parentElement: null
    })
    expect(failedDraw).not.toHaveBeenCalled()
    previous.redraw()
    expect(draw).toHaveBeenCalledTimes(2)
    expect(reportError).toHaveBeenCalledWith(expect.any(ComfyApiError), {
      errorType: 'node_canvas_context_unavailable',
      context: { recovery: 'previous_surface_preserved' }
    })
    previous.remove()
    unmount()
  })

  it('releases a replacement whose first draw fails and retains the old surface', () => {
    const node = new LGraphNode('Drawing', 'Drawing')
    vi.spyOn(canvasPrototype, 'getContext').mockReturnValue(
      createMockCanvasRenderingContext2D()
    )
    const previous = createNodeCanvas(node, { bounds, draw: vi.fn() })
    const container = document.createElement('div')
    const unmount = mountNodeCanvas(node, container)
    const mounted = container.firstChild
    const create = vi.spyOn(document, 'createElement')
    const error = new Error('Drawing failed')

    expect(() =>
      createNodeCanvas(node, {
        bounds: { ...bounds, width: 60 },
        draw() {
          throw error
        }
      })
    ).toThrow(error)
    expect(nodeCanvasBounds(node)).toEqual(bounds)
    expect(container.firstChild).toBe(mounted)
    expect(create.mock.results.at(-1)?.value).toMatchObject({
      width: 0,
      height: 0,
      parentElement: null
    })
    expect(reportError).toHaveBeenCalledWith(error, {
      errorType: 'node_canvas_initial_draw_failed',
      context: { recovery: 'previous_surface_preserved' }
    })
    previous.remove()
    unmount()
  })

  it('reports a removed handle mutation without recreating its canvas', () => {
    const node = new LGraphNode('Drawing', 'Drawing')
    vi.spyOn(canvasPrototype, 'getContext').mockReturnValue(
      createMockCanvasRenderingContext2D()
    )
    const draw = vi.fn()
    const surface = createNodeCanvas(node, { bounds, draw })
    surface.remove()

    expect(() => surface.setBounds({ ...bounds, width: 60 })).toThrow(
      ComfyApiError
    )
    expect(nodeCanvasBounds(node)).toBeUndefined()
    surface.redraw()
    expect(draw).toHaveBeenCalledTimes(1)
    expect(reportError).toHaveBeenCalledWith(expect.any(ComfyApiError), {
      errorType: 'node_canvas_surface_removed',
      context: { recovery: 'mutation_rejected' }
    })
  })
})
