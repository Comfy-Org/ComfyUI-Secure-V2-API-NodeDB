// The published frontend surface; no private app or widget mutation.
import { comfy } from '/comfy/api/v2.js'

async function refreshChoices(node) {
  // Public authenticated host transport, using the existing confined model
  // catalogue route. No new pack/backend route or host path is introduced.
  const response = await comfy.backend.fetch('/models/loras')
  if (!response.ok) throw new Error(`LoRA catalogue returned HTTP ${response.status}`)
  const names = await response.json()
  if (!Array.isArray(names) || names.length > 16384 || names.some(name => typeof name !== 'string')) {
    throw new Error('LoRA catalogue must contain at most16384logical names')
  }
  const choices = ['none', ...names]
  for (let index = 0; index < 5; index++) {
    // Updating only choices preserves native none defaults and imported
    // selections. It never automatically selects a nonzero model.
    node.widgets.get(`lora_${index}`)?.setOption('values', choices)
  }
}

function refresh(node) {
  void refreshChoices(node).catch(error => console.warn('Wan LoRA catalogue refresh failed', error))
}

comfy.defs.extend('WanVideoLoraSelectMulti', builder => {
  builder.onCreated(node => refresh(node))
  builder.onConfigured(node => refresh(node))
  builder.addMenuItem({ label: 'Refresh LoRA list', run: node => refresh(node) })
})
