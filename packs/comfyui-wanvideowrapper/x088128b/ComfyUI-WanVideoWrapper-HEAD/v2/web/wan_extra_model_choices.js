import { comfy } from '/comfy/api/v2.js'

async function catalogue(route) {
  const response = await comfy.backend.fetch(route)
  if (!response.ok) throw new Error(`Wan model catalogue returned HTTP ${response.status}`)
  const names = await response.json()
  if (!Array.isArray(names) || names.length > 16384 || names.some(name => typeof name !== 'string')) {
    throw new Error('Wan model catalogue must contain at most 16384 names')
  }
  return names
}

async function refresh(node, name) {
  // Match the pinned order: GGUF catalogue first, then diffusion models.
  // The existing GGUF endpoint supplies no connector entries or none sentinel.
  const [gguf, diffusion] = await Promise.all([
    catalogue('/models/gguf/choices'), catalogue('/models/diffusion_models')
  ])
  const choices = [...gguf, ...diffusion]
  const widget = node.widgets.get(name)
  if (!widget) return
  widget.setOption('values', choices)
  const selected = widget.getValue()
  // A newly created empty combo receives the native first-item default.
  // Recheck after the requests so imported selections survive configuration.
  if (choices.length && (selected == null || selected === '')) widget.setValue(choices[0])
}

for (const [type, widget] of [
  ['WanVideoVACEModelSelect', 'vace_model'],
  ['WanVideoExtraModelSelect', 'extra_model']
]) {
  comfy.defs.extend(type, builder => {
    const update = node => void refresh(node, widget).catch(error => console.warn('Wan model catalogue refresh failed', error))
    builder.onCreated(update)
    builder.onConfigured(update)
    builder.addMenuItem({ label: 'Refresh model list', run: update })
  })
}
