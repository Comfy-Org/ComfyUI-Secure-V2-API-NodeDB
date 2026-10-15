import type { NodeHandle, WidgetHandle, NodeCanvasHandle, NodeCanvasDef, NodeDefinition, NodePresentation } from './successor-candidate/pack/comfy-api'

declare const publicNode: NodeHandle
declare const publicWidget: WidgetHandle

const explicitLabel: string | undefined = publicWidget.getLabel()
publicNode.setResizable(true)
const drawingSurface: NodeCanvasHandle = publicNode.canvas({
  bounds: { x: -4, y: -3, width: 80, height: 30 },
  layer: 'foreground',
  draw(context) { context.fillText(explicitLabel ?? '', 0, 0) }
})
drawingSurface.setBounds({ x: 0, y: 0, width: 100, height: 40 })
drawingSurface.redraw()
drawingSurface.remove()
const declaredNode: NodeDefinition = {
  type: 'consumer-example',
  execution: 'frontend',
  presentation: { title: 'hidden', sizing: 'fixed', collapsible: false },
  onCreated(node) { node.setResizable(false) }
}
const annotation: NodePresentation = {
  chrome: 'none', resizable: false, collapsible: false, pinnedInteraction: 'pass-through'
}
// @ts-expect-error Only boolean resize policy is public.
publicNode.setResizable('yes')
// @ts-expect-error Explicit labels retain undefined rather than becoming widget.name.
const requiredLabel: string = publicWidget.getLabel()
// @ts-expect-error The only canvas layer is foreground.
const badCanvas: NodeCanvasDef = { bounds: { x: 0, y: 0, width: 1, height: 1 }, layer: 'host-dom', draw() {} }
// @ts-expect-error Presentation is a closed DTO.
const badPresentation: NodePresentation = { privatePanel: true }
void [declaredNode, annotation, drawingSurface]
