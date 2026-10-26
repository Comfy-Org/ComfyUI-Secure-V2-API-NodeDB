import { comfy } from '/comfy/api/v2.js'

// Only the published named catalogue service reaches shared host resources.
for (const [type, input] of [
  ['Checkpoint_Selector_efcbbd2520fd995e676f4966', 'ckpt_name'],
  ['Save_Image_w_Metadata_6be3a4fb3d0e4c56fec9513e', 'modelname']
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
