import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { LGraph, LGraphNode, LiteGraph } from '@/lib/litegraph/src/litegraph'
import { graphToPrompt } from '@/utils/executionUtil'

import { serializeWorkflow } from './asyncWidgetSerialization'
import { createGraphApi } from './graphHandle'
import { subscribeAsyncWidgetSerialization } from './widgetHandle'

const nodeType = 'SimpleReadableMetadataSaveTextSG'

class MetadataTextNode extends LGraphNode {
  constructor() {
    super('Simple Readable Metadata Save Text-SG', nodeType)
    this.comfyClass = nodeType
    this.serialize_widgets = true
    this.addInput('text', 'STRING')
    this.addWidget('text', 'filename_prefix', 'ComfyUI_text', () => undefined)
    this.addWidget('combo', 'file_format', 'txt', () => undefined, {
      values: ['txt', 'json', 'md']
    })
    this.addWidget('toggle', 'pretty_json', true, () => undefined)
  }
}

function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((complete) => {
    resolve = complete
  })
  return { promise, resolve }
}

function fixture() {
  const graph = new LGraph()
  const node = LiteGraph.createNode(nodeType)
  if (!node) throw new Error('Metadata acceptance node was not registered')
  graph.add(node)
  const handle = createGraphApi(() => graph).node(String(node.id))
  const filename = handle?.widgets.get('filename_prefix')
  if (!filename) throw new Error('Metadata filename widget missing')
  filename.setValue('authored_Ω')
  return { graph, node, filename }
}

describe('Metadata widget state through canonical save and queue', () => {
  beforeEach(() => {
    LiteGraph.registerNodeType(nodeType, MetadataTextNode)
  })

  afterEach(() => {
    LiteGraph.unregisterNodeType(nodeType)
  })

  it('awaits the save projection and restores its value in a fresh graph', async () => {
    const { graph, filename } = fixture()
    const entered = deferred()
    const release = deferred()
    const stop = subscribeAsyncWidgetSerialization(
      filename,
      async ({ value }) => {
        entered.resolve()
        await release.promise
        return { changed: true, value: `saved_${value}` }
      }
    )
    let completed = false
    const pending = serializeWorkflow(graph).then((data) => {
      completed = true
      return data
    })
    try {
      await entered.promise
      expect(completed).toBe(false)
      release.resolve()
      const saved = await pending
      expect(saved.nodes[0].widgets_values).toEqual([
        'saved_authored_Ω',
        'txt',
        true
      ])
      expect(filename.getValue()).toBe('authored_Ω')
      const restored = new LGraph()
      restored.configure(JSON.parse(JSON.stringify(saved)))
      const reopened = createGraphApi(() => restored).nodes()[0]
      expect(reopened.widgets.get('filename_prefix')?.getValue()).toBe(
        'saved_authored_Ω'
      )
      const queued = await graphToPrompt(restored)
      expect(queued.output[reopened.id].inputs.filename_prefix).toBe(
        'saved_authored_Ω'
      )
    } finally {
      release.resolve()
      stop()
    }
  })

  it('awaits separate embedded and queued values without changing the editor', async () => {
    const { graph, node, filename } = fixture()
    const entered = deferred()
    const release = deferred()
    const stop = subscribeAsyncWidgetSerialization(
      filename,
      async ({ context, value }) => {
        if (context === 'prompt') {
          entered.resolve()
          await release.promise
        }
        return { changed: true, value: `${context}_${value}` }
      }
    )
    let completed = false
    const pending = graphToPrompt(graph).then((data) => {
      completed = true
      return data
    })
    try {
      await entered.promise
      expect(completed).toBe(false)
      release.resolve()
      const queued = await pending
      expect(queued.workflow.nodes[0].widgets_values).toEqual([
        'embedded_authored_Ω',
        'txt',
        true
      ])
      expect(queued.output[String(node.id)].inputs.filename_prefix).toBe(
        'prompt_authored_Ω'
      )
      expect(filename.getValue()).toBe('authored_Ω')
    } finally {
      release.resolve()
      stop()
    }
  })

  it('refuses a queue whose authored value changes while the worker projection waits', async () => {
    const { graph, filename } = fixture()
    const entered = deferred()
    const release = deferred()
    const stop = subscribeAsyncWidgetSerialization(filename, async () => {
      entered.resolve()
      await release.promise
      return { changed: true, value: 'stale_projection' }
    })
    const pending = graphToPrompt(graph)
    try {
      await entered.promise
      filename.setValue('new_author_value')
      release.resolve()
      await expect(pending).rejects.toThrow(/changed during.*serialization/)
      expect(filename.getValue()).toBe('new_author_value')
    } finally {
      release.resolve()
      stop()
    }
  })
})
