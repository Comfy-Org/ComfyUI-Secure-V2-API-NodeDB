import { comfy } from '/comfy/api/v2.js'

function fillMetadata(container, metadata) {
  const details = document.createElement('details')
  const summary = document.createElement('summary')
  summary.textContent = 'Metadata'
  details.append(summary)
  const table = document.createElement('table')
  for (const [key, value] of Object.entries(metadata)) {
    const row = document.createElement('tr')
    const label = document.createElement('th')
    label.textContent = key
    label.style.textAlign = 'left'
    const cell = document.createElement('td')
    cell.textContent = String(value)
    cell.style.whiteSpace = 'pre-wrap'
    cell.style.overflowWrap = 'anywhere'
    row.append(label, cell)
    table.append(row)
  }
  details.append(table)
  container.replaceChildren(details)
}

for (const type of ['WanVideoLoraSelect', 'WanVideoLoraSelectByName']) {
  comfy.defs.extend(type, builder => {
    // One owned surface per node; its destroy hook releases the render closure.
    const panels = new Map()
    builder.onExecuted((node, result) => {
      const metadata = result.raw.wan_lora_metadata?.[0]
      if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return
      let panel = panels.get(node.id)
      if (panel) {
        panel.metadata = metadata
        if (panel.container) fillMetadata(panel.container, metadata)
        return
      }
      panel = { metadata, container: null }
      panels.set(node.id, panel)
      node.widgets.mount({
        name: 'wan_lora_metadata', serialize: false, sendToPrompt: false,
        render(container) {
          panel.container = container
          fillMetadata(container, panel.metadata)
        },
        destroy() {
          panel.container = null
          panels.delete(node.id)
        }
      })
    })
  })
}
