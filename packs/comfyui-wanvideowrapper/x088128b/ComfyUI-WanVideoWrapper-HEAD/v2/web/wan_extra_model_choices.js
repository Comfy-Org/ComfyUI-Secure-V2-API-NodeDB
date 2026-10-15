import { comfy } from '/comfy/api/v2.js'

// PARTIAL menu: the original offers models/unet_gguf (GGUF files the original
// pack registers itself at import) followed by models/diffusion_models. Pack JS
// calls no core URL (route rule), and unet_gguf is not a public model folder,
// so only the diffusion_models entries are offered until the host supports
// pack-declared model folders.
let cached = null

async function listDiffusionModels() {
  const names = await comfy.models.list('diffusion_models')
  if (!Array.isArray(names) || names.length > 16384 || names.some(name => typeof name !== 'string')) {
    throw new Error('Wan model catalogue must contain at most 16384 names')
  }
  return names
}

// One listing per menu build, shared by both node types (the per-pack call
// rate is bounded); "Refresh model list" asks the host again.
function diffusionModels(force) {
  if (force || cached === null) {
    const request = listDiffusionModels()
    cached = request
    request.catch(() => {
      if (cached === request) cached = null
    })
  }
  return cached
}

async function refresh(node, name, force) {
  const choices = [...await diffusionModels(force)]
  const widget = node.widgets.get(name)
  if (!widget) return
  widget.setOption('values', choices)
  const selected = widget.getValue()
  // A newly created empty combo receives the native first-item default.
  // Recheck after the request so imported selections survive configuration.
  if (choices.length && (selected == null || selected === '')) widget.setValue(choices[0])
}

for (const [type, widget] of [
  ['WanVideoVACEModelSelect', 'vace_model'],
  ['WanVideoExtraModelSelect', 'extra_model']
]) {
  comfy.defs.extend(type, builder => {
    const update = (node, force = false) =>
      void refresh(node, widget, force).catch(error => console.warn('Wan model catalogue refresh failed', error))
    builder.onCreated(node => update(node))
    builder.onConfigured(node => update(node))
    builder.addMenuItem({ label: 'Refresh model list', run: node => update(node, true) })
  })
}
