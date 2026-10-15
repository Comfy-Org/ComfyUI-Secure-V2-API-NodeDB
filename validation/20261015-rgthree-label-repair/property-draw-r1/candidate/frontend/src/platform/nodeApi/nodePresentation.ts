import type { LGraphNode } from '@/lib/litegraph/src/LGraphNode'

export interface NodePresentation {
  readonly chrome?: 'default' | 'none'
  /** Hide the title independently of the normal node body and slots. */
  readonly title?: 'default' | 'hidden'
  /** Fixed nodes keep their declared body rectangle in the DOM renderer. */
  readonly sizing?: 'content' | 'fixed'
  readonly resizable?: boolean
  readonly collapsible?: boolean
  /** Primary clicks pass through while pinned; editing and context menus remain. */
  readonly pinnedInteraction?: 'default' | 'pass-through'
}

const presentations = new Map<string, Readonly<NodePresentation>>()
const defaultPresentation: Readonly<NodePresentation> = Object.freeze({})

export function validateNodePresentation(
  value: unknown
): Readonly<NodePresentation> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Node presentation must be an object')
  }
  const allowed = new Set([
    'chrome',
    'title',
    'sizing',
    'resizable',
    'collapsible',
    'pinnedInteraction'
  ])
  for (const key of Object.keys(value)) {
    if (!allowed.has(key))
      throw new TypeError(`Unknown presentation field '${key}'`)
  }
  const result: {
    chrome?: 'default' | 'none'
    title?: 'default' | 'hidden'
    sizing?: 'content' | 'fixed'
    resizable?: boolean
    collapsible?: boolean
    pinnedInteraction?: 'default' | 'pass-through'
  } = {}
  if ('chrome' in value) {
    if (value.chrome !== 'default' && value.chrome !== 'none') {
      throw new TypeError('Invalid node chrome')
    }
    result.chrome = value.chrome
  }
  if ('title' in value) {
    if (value.title !== 'default' && value.title !== 'hidden') {
      throw new TypeError('Invalid node title presentation')
    }
    result.title = value.title
  }
  if ('sizing' in value) {
    if (value.sizing !== 'content' && value.sizing !== 'fixed') {
      throw new TypeError('Invalid node sizing presentation')
    }
    result.sizing = value.sizing
  }
  for (const key of ['resizable', 'collapsible'] as const) {
    if (key in value) {
      const flag: unknown = Reflect.get(value, key)
      if (typeof flag !== 'boolean')
        throw new TypeError(`${key} must be boolean`)
      result[key] = flag
    }
  }
  if ('pinnedInteraction' in value) {
    if (
      value.pinnedInteraction !== 'default' &&
      value.pinnedInteraction !== 'pass-through'
    ) {
      throw new TypeError('Invalid pinned interaction')
    }
    result.pinnedInteraction = value.pinnedInteraction
  }
  return Object.freeze(result)
}

export function registerNodePresentation(
  type: string,
  value: NodePresentation
): () => void {
  const presentation = validateNodePresentation(value)
  presentations.set(type, presentation)
  return () => {
    if (presentations.get(type) === presentation) presentations.delete(type)
  }
}

export function nodePresentation(type: string): Readonly<NodePresentation> {
  return presentations.get(type) ?? defaultPresentation
}

export function passesPinnedPrimaryClick(
  node: Pick<LGraphNode, 'type' | 'flags'>,
  button: number,
  doubleClick: boolean
): boolean {
  return (
    button === 0 &&
    !doubleClick &&
    nodePresentation(node.type).pinnedInteraction === 'pass-through' &&
    node.flags.pinned === true
  )
}
