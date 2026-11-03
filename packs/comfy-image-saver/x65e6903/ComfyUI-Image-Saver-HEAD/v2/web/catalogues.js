import { comfy } from '/comfy/api/v2.js'

// Only the published named catalogue service reaches shared host resources.
for (const [type, input] of [
  ['Checkpoint Selector', 'ckpt_name'],
  ['Save Image w/Metadata', 'modelname']
]) {
  comfy.defs.extend(type, (definition) => {
    async function hydrate(node) {
      const widget = node.widgets.get(input)
      if (!widget) return
      const names = await comfy.models.list('checkpoints')
      widget.setOption('values', names)
      if (!widget.getValue() && names.length) widget.setValue(names[0])
    }
    definition.onCreated(hydrate)
    definition.onConfigured(hydrate)
  })
}
