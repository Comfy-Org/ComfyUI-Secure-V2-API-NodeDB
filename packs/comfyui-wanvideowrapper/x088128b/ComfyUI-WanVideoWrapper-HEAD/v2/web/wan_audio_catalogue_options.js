// Ordered model menus over the existing public backend and widget APIs.
// Names remain names: no folder prefixes, deduplication or fallback entries.
const pendingRefresh = new WeakMap()
const routes = Object.freeze({
  MultiTalkModelLoader: ['/models/unet_gguf', '/models/diffusion_models'],
  OviMMAudioVAELoader: ['/models/vae', '/models/mmaudio']
})
const widgets = Object.freeze({
  MultiTalkModelLoader: ['model'],
  OviMMAudioVAELoader: ['vae', 'vocoder']
})

async function catalogue(comfy, route) {
  const response = await comfy.backend.fetch(route)
  if (!response.ok) throw new Error(`Wan catalogue ${route} returned HTTP ${response.status}`)
  const names = await response.json()
  if (!Array.isArray(names) || names.some(name => typeof name !== 'string')) {
    throw new TypeError(`Wan catalogue ${route} did not return a string list`)
  }
  return names
}

export async function refreshAudioModelUnion(comfy, node, nodeType) {
  const sources = routes[nodeType]
  const targets = widgets[nodeType]
  if (!sources || !targets) throw new Error('Unknown Wan audio model menu')
  const token = {}
  pendingRefresh.set(node, token)
  // The original first listing finishes before the second is requested.
  // A missing catalogue must fail; /models/gguf/choices is intentionally
  // avoided because it silently turns an absent unet_gguf catalogue into [].
  const first = await catalogue(comfy, sources[0])
  const second = await catalogue(comfy, sources[1])
  if (pendingRefresh.get(node) !== token) return false
  const values = first.concat(second)
  const selected = targets.map(name => ({name, widget: node.widgets.get(name)}))
  for (const {name, widget} of selected) {
    if (!widget) throw new Error(`Wan audio model widget ${name} is unavailable`)
  }
  for (const {widget} of selected) {
    widget.setOption('values', values)
    const current = widget.getValue()
    if (values.length && (current === null || current === undefined || current === '')) {
      widget.setValue(values[0])
    }
  }
  return true
}
