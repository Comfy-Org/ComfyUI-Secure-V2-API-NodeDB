import { comfy } from '/comfy/api/v2.js'
import { commonPrefix } from './common.js'

const STATUS = {
  executing: 'Executing',
  executed: 'Executed',
  error: 'Execution error'
}

class CrystoolsProgressBar {
  id = 'Crystools.ProgressBar'
  currentStatus = STATUS.executed
  currentProgress = 0
  currentNode
  timeStart = 0
  visible = true
  badge

  display() {
    if (!this.visible) {
      this.badge?.remove()
      this.badge = undefined
      return
    }

    let text = 'cached'
    let variant
    if (this.currentStatus === STATUS.executing) {
      text = `${this.currentProgress}%`
    } else if (this.currentStatus === STATUS.error) {
      text = 'ERROR'
      variant = 'error'
    } else if (this.timeStart > 0) {
      text = new Date(Date.now() - this.timeStart).toISOString().slice(11, 19)
    }

    if (this.badge) {
      this.badge.update({ text, variant })
    } else {
      this.badge = comfy.ui.addTopBarBadge({
        id: 'Crystools.progress',
        label: 'Progress',
        text,
        variant,
        tooltip: 'Current execution progress'
      })
    }
  }

  centerNode() {
    if (!this.currentNode) return
    const root = comfy.graph.root() ?? comfy.graph
    for (const graph of [root, ...root.subgraphs()]) {
      const node = graph.node(String(this.currentNode))
      if (node) {
        graph.centerOn(node)
        return
      }
    }
  }

  setup = () => {
    comfy.settings.declare({
      id: this.id,
      name: 'Show progress',
      category: ['Crystools', `${commonPrefix} Progress Bar`, 'Show'],
      type: 'boolean',
      defaultValue: true,
      onChange: (visible) => {
        this.visible = visible
        this.display()
      }
    })

    this.visible = comfy.settings.get(this.id) ?? true
    comfy.ui.addActionBarButton({
      id: 'Crystools.centerExecutingNode',
      icon: 'pi-crosshairs',
      tooltip: 'Go to the current working node',
      run: () => this.centerNode()
    })
    this.display()

    comfy.backend.on('status', (detail) => {
      if (this.currentStatus !== STATUS.error) {
        this.currentStatus = detail?.exec_info.queue_remaining
          ? STATUS.executing
          : STATUS.executed
      }
      this.display()
    })
    comfy.backend.on('progress', ({ value, max, node }) => {
      const progress = Math.floor((value / max) * 100)
      if (Number.isFinite(progress) && progress >= 0 && progress <= 100) {
        this.currentProgress = progress
        this.currentNode = node
      }
      this.display()
    })
    comfy.backend.on('executed', ({ node }) => {
      if (node) this.currentNode = node
      this.display()
    })
    comfy.backend.on('execution_start', () => {
      this.currentStatus = STATUS.executing
      this.timeStart = Date.now()
      this.display()
    })
    comfy.backend.on('execution_error', () => {
      this.currentStatus = STATUS.error
      this.display()
    })
  }
}

// COSMETIC: the host renders a text badge instead of accepting a pack-owned
// partial-width progress strip inside core's queue-button container.

const progress = new CrystoolsProgressBar()
comfy.onReady(progress.setup)
