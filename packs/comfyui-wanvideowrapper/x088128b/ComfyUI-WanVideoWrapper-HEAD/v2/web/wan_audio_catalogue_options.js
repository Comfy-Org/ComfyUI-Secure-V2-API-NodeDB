// Ordered model menus over the public model listing (comfy.models.list). Pack
// JS calls no core URL (route rule). Names remain names: no folder prefixes,
// deduplication or fallback entries.
//
// PARTIAL menus: the original lists models/unet_gguf + models/diffusion_models
// (MultiTalk) and models/vae + models/mmaudio (Ovi). unet_gguf and mmaudio are
// folders the original pack registers itself at import; they are not public
// model folders, so their entries are unavailable here until the host supports
// pack-declared model folders. The remaining folders keep the original order.
const pendingRefresh = new WeakMap()
const folders = Object.freeze({
  MultiTalkModelLoader: ['diffusion_models'],
  OviMMAudioVAELoader: ['vae']
})
const widgets = Object.freeze({
  MultiTalkModelLoader: ['model'],
  OviMMAudioVAELoader: ['vae', 'vocoder']
})
// One listing per folder per menu build (the per-pack call rate is bounded);
// "Refresh model list" asks the host again. Failed listings are not kept.
const listings = new Map()

async function listFolder(comfy, folder) {
  const names = await comfy.models.list(folder)
  if (!Array.isArray(names) || names.length > 16384 || names.some(name => typeof name !== 'string')) {
    throw new TypeError(`Wan catalogue ${folder} did not return a string list`)
  }
  return names
}

function catalogue(comfy, folder, force) {
  if (force || !listings.has(folder)) {
    const request = listFolder(comfy, folder)
    listings.set(folder, request)
    request.catch(() => {
      if (listings.get(folder) === request) listings.delete(folder)
    })
  }
  return listings.get(folder)
}

export async function refreshAudioModelUnion(comfy, node, nodeType, force = false) {
  const sources = folders[nodeType]
  const targets = widgets[nodeType]
  if (!sources || !targets) throw new Error('Unknown Wan audio model menu')
  const token = {}
  pendingRefresh.set(node, token)
  // Listings are requested in order; a missing or failed listing fails the
  // refresh instead of silently becoming an empty menu.
  const values = []
  for (const folder of sources) values.push(...await catalogue(comfy, folder, force))
  if (pendingRefresh.get(node) !== token) return false
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
