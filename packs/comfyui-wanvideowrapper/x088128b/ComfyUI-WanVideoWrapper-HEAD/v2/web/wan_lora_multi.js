// The published frontend surface; no private app or widget mutation.
import { comfy } from '/comfy/api/v2.js'

// One listing per menu build, shared by every Multi-LoRA node: the per-pack call
// rate is bounded, so nodes reuse the cached listing and "Refresh LoRA list" asks
// the host again. A failed listing is not kept; the next menu build retries.
let cached = null

async function listLoraNames() {
  // Named public method (route rule): logical names relative to models/loras,
  // deduplicated, in backend order; never host paths. It rejects on error.
  const names = await comfy.models.list('loras')
  if (!Array.isArray(names) || names.length > 16384 || names.some(name => typeof name !== 'string')) {
    throw new Error('LoRA catalogue must contain at most 16384 logical names')
  }
  return names
}

function loraNames(force) {
  if (force || cached === null) {
    const request = listLoraNames()
    cached = request
    request.catch(() => {
      if (cached === request) cached = null
    })
  }
  return cached
}

async function refreshChoices(node, force) {
  const choices = ['none', ...await loraNames(force)]
  for (let index = 0; index < 5; index++) {
    // Updating only choices preserves native none defaults and imported
    // selections. It never automatically selects a nonzero model.
    node.widgets.get(`lora_${index}`)?.setOption('values', choices)
  }
}

function refresh(node, force = false) {
  void refreshChoices(node, force).catch(error => console.warn('Wan LoRA catalogue refresh failed', error))
}

comfy.defs.extend('WanVideoLoraSelectMulti', builder => {
  builder.onCreated(node => refresh(node))
  builder.onConfigured(node => refresh(node))
  builder.addMenuItem({ label: 'Refresh LoRA list', run: node => refresh(node, true) })
})
