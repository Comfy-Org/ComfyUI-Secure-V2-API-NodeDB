import { LGraph, LGraphNode, LiteGraph } from '@/lib/litegraph/src/litegraph'
import { createGraphApi } from '@/platform/nodeApi/graphHandle'
import { serializeWorkflow } from '@/platform/nodeApi/asyncWidgetSerialization'
import { subscribeAsyncWidgetSerialization } from '@/platform/nodeApi/widgetHandle'
import { graphToPrompt } from '@/utils/executionUtil'
import { SecureExtensionHost } from './provider/host-entry.mjs'

const type = 'SimpleReadableMetadataSaveTextSG'
class TextNode extends LGraphNode {
  constructor() {
    super('Simple Readable Metadata Save Text-SG', type)
    this.comfyClass = type
    this.serialize_widgets = true
    this.addInput('text', 'STRING')
    this.addWidget('text', 'filename_prefix', 'ComfyUI_text', () => undefined)
    this.addWidget('combo', 'file_format', 'txt', () => undefined, { values: ['txt', 'json', 'md'] })
    this.addWidget('toggle', 'pretty_json', true, () => undefined)
  }
}
LiteGraph.registerNodeType(type, TextNode)
const graph = new LGraph()
const node = LiteGraph.createNode(type)
if (!node) throw Error('Missing Metadata class')
graph.add(node)
const api = createGraphApi(() => graph)
const handle = api.node(String(node.id))
if (!handle) throw Error('Missing Metadata node')
const filename = handle.widgets.get('filename_prefix')
if (!filename) throw Error('Missing Metadata filename widget')
filename.setValue('author_Ω')
const registrations: ((node: typeof handle, event: object) => void)[] = []
const response = (body: object) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } })
const comfy = {
  graph: api,
  workflow: { documentId: () => 'metadata-author-story' },
  onWorkflowLoaded: () => () => undefined,
  backend: { url: (path: string) => new URL(path, location.origin).href, fetch: async () => response({}) },
  defs: { extend(_selector: string, register: (builder: object) => void) {
    register({ onCreated(callback: (node: typeof handle, event: object) => void) { registrations.push(callback) }, onExecuted() {}, onRemoved() {}, onConfigure() {} })
    return () => undefined
  } }
}
const host = new SecureExtensionHost({ comfy, bootstrapUrl: './provider/guest.mjs', capabilities: [], subscribeWidgetSerialization: subscribeAsyncWidgetSerialization })
const state = { ready: false, result: undefined as object | undefined }
Object.assign(window, {
  __state: () => state,
  __start: async () => {
    await host.load('/extensions/MetadataStory/entry.js')
    registrations.forEach(callback => callback(handle, {}))
    state.ready = true
  },
  __subscriptions: () => host._subs?.size,
  __run: async () => {
    const saved = await serializeWorkflow(graph)
    const live = filename.getValue()
    const restored = new LGraph()
    restored.configure(JSON.parse(JSON.stringify(saved)))
    const reopened = await graphToPrompt(restored)
    const queued = await graphToPrompt(graph)
    filename.setValue('refuse')
    let refusal = ''
    try { await graphToPrompt(graph) } catch (error) { refusal = String(error) }
    filename.setValue('recovered')
    const recovered = await graphToPrompt(graph)
    state.result = { queueInputs: queued.output[String(node.id)].inputs, saved: saved.nodes[0].widgets_values, live, reopened: Object.values(reopened.output)[0].inputs.filename_prefix, embedded: queued.workflow.nodes[0].widgets_values, prompt: queued.output[String(node.id)].inputs.filename_prefix, refusal, recovered: recovered.output[String(node.id)].inputs.filename_prefix, sandbox: document.querySelector('iframe')?.getAttribute('sandbox') }
    return state.result
  },
  __finish: () => { host.destroy(); LiteGraph.unregisterNodeType(type) }
})
