/**
 * Overlay entry point. Installs the secure extension host into ComfyUI_frontend
 * through the generic `provideExtensionHost` seam.
 *
 * Loaded at startup by the frontend (see the bootstrap on the secure-v2-sdk
 * branch). If this module is absent, the frontend behaves exactly as stock:
 * extensions `import()` into the main document as before.
 *
 * Responsibilities:
 *   - own the single shared sandbox iframe + one worker per pack
 *   - serve the pack's `comfy.*` calls against the real V2 API
 *   - implement in-node UI: ops -> closed shadow root, element handles for
 *     imperative control
 */
import { SandboxHost } from './sandbox-host.mjs'
import { mountPackUI } from './ui-renderer.mjs'

const DEFAULT_GUEST_BOOTSTRAP_URL = new URL('./guest.mjs', import.meta.url).href

/** Closed geometry DTO for one pack-owned node surface. */
export function nodeCanvasBoundsData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).some((key) => !['x', 'y', 'width', 'height'].includes(key))) {
    throw new TypeError('invalid node canvas bounds')
  }
  const { x, y, width, height } = value
  if (![x, y, width, height].every((n) => typeof n === 'number' && Number.isFinite(n)) ||
      Math.abs(x) > 8192 || Math.abs(y) > 8192 || width < 1 || height < 1 ||
      width > 8192 || height > 8192 || Math.ceil(width) * Math.ceil(height) > 16_777_216) {
    throw new RangeError('node canvas bounds exceed finite coordinate or pixel limits')
  }
  return Object.freeze({ x, y, width, height })
}

/** Path segments a sandboxed pack may never address. */
const FORBIDDEN = new Set(['__proto__', 'prototype', 'constructor'])
const IMPORTER_MAX_BYTES = 16 * 1024 * 1024
const IMPORT_RESULT_MAX_BYTES = 8 * 1024 * 1024
const WORKFLOW_SNAPSHOT_MAX_BYTES = 8 * 1024 * 1024
const FILE_TRANSFER_MAX_BYTES = 16 * 1024 * 1024
const FILE_TRANSFER_MAX_TOTAL_BYTES = 256 * 1024 * 1024
const FILE_PICK_MAX_FILES = 50
const CRYPTO_PLAINTEXT_MAX_BYTES = 8 * 1024 * 1024
const CRYPTO_CIPHERTEXT_MAX_BYTES = CRYPTO_PLAINTEXT_MAX_BYTES + 16
const CRYPTO_AUTH_DATA_MAX_BYTES = 16 * 1024 * 1024
const IMPORTER_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/
const IMPORTER_EXTENSION = /^[a-z0-9][a-z0-9+_-]{0,15}$/
const IMPORTER_MIME = /^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}\/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$/
const COMBO_PREVIEW_CATEGORIES = new Set([
  'loras', 'checkpoints', 'unet', 'diffusion_models',
])
const COMBO_PREVIEW_EXTENSIONS = new Set([
  'safetensors', 'sft', 'pt', 'ckpt', 'gguf',
])
const COMBO_PREVIEW_MEDIA = new Set([
  'image/png', 'image/webp', 'image/jpeg', 'video/mp4', 'video/webm',
])
const LOCALIZATION_LOCALE = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$/
const LOCALIZATION_FORBIDDEN_KEYS = new Set([
  '__proto__', 'prototype', 'constructor',
])

/** Per-tag allowlist for element handles (the ImageRef pattern, for DOM). */
export const ELEMENT_POLICY = {
  video: {
    methods: ['play', 'pause', 'load'],
    get: ['currentTime', 'duration', 'paused', 'ended', 'videoWidth',
          'videoHeight', 'readyState', 'muted', 'volume'],
    set: ['currentTime', 'muted', 'volume', 'playbackRate', 'loop'],
    events: ['timeupdate', 'loadedmetadata', 'play', 'pause', 'ended', 'seeked'],
  },
  img: { methods: [], get: ['naturalWidth', 'naturalHeight', 'complete'],
         set: ['src', 'alt'], events: ['load', 'error'] },
  canvas: { methods: [], get: ['width', 'height'], set: ['width', 'height'],
            events: [] },
  input: { methods: ['focus', 'select'], get: ['value'], set: ['value'],
           events: ['input', 'change'] },
}

function resolveComfyPath(comfy, path) {
  const parts = String(path).split('.')
  if (parts[0] !== 'comfy') throw new Error(`sandbox may only call comfy.*: ${path}`)
  let obj = { comfy }
  let parent = null
  for (const p of [...parts]) {
    if (FORBIDDEN.has(p)) throw new Error(`forbidden path segment '${p}'`)
    if (obj == null) throw new Error(`no such api: ${path}`)
    parent = obj
    obj = obj[p]
  }
  if (typeof obj !== 'function') throw new Error(`not callable: ${path}`)
  return obj.bind(parent)
}

/** Validate the closed BadgeDef payload at the trust boundary. */
function badgeData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      typeof value.text !== 'string') {
    throw new TypeError('sandbox badge must contain string text')
  }
  const data = { text: value.text }
  for (const key of ['color', 'bgColor']) {
    if (value[key] !== undefined) {
      if (typeof value[key] !== 'string') {
        throw new TypeError(`sandbox badge ${key} must be a string`)
      }
      data[key] = value[key]
    }
  }
  return data
}

function boundedActionString(value, name, { optional = false,
                                             max = 512 } = {}) {
  if (optional && value === undefined) return undefined
  if (typeof value !== 'string' || value.length < 1 || value.length > max ||
      /[\0-\x1f\x7f]/.test(value)) {
    throw new TypeError(`${name} must be a non-empty bounded string`)
  }
  return value
}

/** Validate the data-only half of an action-bar contribution. */
function actionButtonData(value, { partial = false } = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('sandbox action-bar button must be an object')
  }
  const allowed = partial
    ? new Set(['icon', 'label', 'tooltip'])
    : new Set(['id', 'icon', 'label', 'tooltip'])
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      throw new TypeError(`unsupported action-bar button field '${key}'`)
    }
  }
  const data = {}
  if (!partial) {
    const id = boundedActionString(value.id, 'action-bar button id', {
      max: 128,
    })
    if (!id.includes('.') ||
        !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(id)) {
      throw new TypeError('action-bar button id must be namespaced')
    }
    data.id = id
  }
  if (!partial || Object.hasOwn(value, 'icon')) {
    data.icon = boundedActionString(value.icon, 'action-bar button icon', {
      max: 256,
    })
  }
  for (const key of ['label', 'tooltip']) {
    if (Object.hasOwn(value, key)) {
      data[key] = boundedActionString(
        value[key], `action-bar button ${key}`, { optional: true })
    }
  }
  return data
}

function topBarBadgeData(value, { partial = false } = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('sandbox top-bar badge must be an object')
  }
  const allowed = partial
    ? new Set(['text', 'label', 'variant', 'icon', 'tooltip'])
    : new Set(['id', 'text', 'label', 'variant', 'icon', 'tooltip'])
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      throw new TypeError(`unsupported top-bar badge field '${key}'`)
    }
  }
  const data = {}
  if (!partial) {
    const id = boundedActionString(value.id, 'top-bar badge id', { max: 128 })
    if (!id.includes('.') || !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(id)) {
      throw new TypeError('top-bar badge id must be namespaced')
    }
    data.id = id
  }
  for (const key of ['text', 'label', 'icon', 'tooltip']) {
    if ((!partial && key === 'text') || Object.hasOwn(value, key)) {
      data[key] = boundedActionString(
        value[key], `top-bar badge ${key}`,
        { optional: key !== 'text', max: key === 'icon' ? 256 : 512 })
    }
  }
  if (Object.hasOwn(value, 'variant')) {
    if (value.variant !== undefined &&
        !['info', 'warning', 'error'].includes(value.variant)) {
      throw new TypeError('top-bar badge variant is invalid')
    }
    data.variant = value.variant
  }
  return data
}

function dialogRegistrationData(value) {
  if (!value || typeof value !== 'object' ||
      typeof value.dialogId !== 'string' ||
      !/^d[1-9][0-9]{0,15}$/.test(value.dialogId) ||
      typeof value.key !== 'string' || !value.key.includes('.') ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value.key) ||
      (value.hasKeyDown !== undefined &&
       typeof value.hasKeyDown !== 'boolean')) {
    throw new TypeError('sandbox dialog registration is invalid')
  }
  const title = boundedActionString(value.title, 'dialog title', {
    optional: true, max: 512,
  })
  return {
    dialogId: value.dialogId,
    key: value.key,
    hasKeyDown: value.hasKeyDown === true,
    ...(title === undefined ? {} : { title }),
  }
}

function dialogKeyEventData(event) {
  const keyString = (value, name) => {
    if (typeof value !== 'string' || value.length > 64 ||
        /[\0-\x1f\x7f]/.test(value)) {
      throw new TypeError(`dialog ${name} is invalid`)
    }
    return value
  }
  return {
    key: keyString(event?.key ?? '', 'key'),
    code: keyString(event?.code ?? '', 'code'),
    repeat: event?.repeat === true,
    altKey: event?.altKey === true,
    ctrlKey: event?.ctrlKey === true,
    metaKey: event?.metaKey === true,
    shiftKey: event?.shiftKey === true,
    editableTarget: dialogKeyTargetIsEditable(event?.target),
  }
}

function dialogKeyTargetIsEditable(target) {
  if (!(target instanceof Element)) return false
  const editable = target.closest('input, textarea, select, [contenteditable]')
  if (!editable) return false
  return editable.matches('input, textarea, select') || editable.isContentEditable
}

function actionEventData(event) {
  const boundedNumber = (value, fallback = 0) =>
    Number.isFinite(value) && Math.abs(value) <= 10_000_000 ? value : fallback
  return {
    altKey: event?.altKey === true,
    ctrlKey: event?.ctrlKey === true,
    metaKey: event?.metaKey === true,
    shiftKey: event?.shiftKey === true,
    button: Number.isInteger(event?.button) &&
      event.button >= -1 && event.button <= 5 ? event.button : 0,
    buttons: Number.isInteger(event?.buttons) &&
      event.buttons >= 0 && event.buttons <= 31 ? event.buttons : 0,
    clientX: boundedNumber(event?.clientX),
    clientY: boundedNumber(event?.clientY),
  }
}

function stringList(value, name, pattern) {
  if (!Array.isArray(value) || value.length > 16) {
    throw new TypeError(`${name} must be an array of at most 16 strings`)
  }
  const out = value.map((item) => {
    const normalized = String(item).toLowerCase()
    if (typeof item !== 'string' || !pattern.test(normalized)) {
      throw new TypeError(`invalid ${name} entry`)
    }
    return normalized
  })
  if (new Set(out).size !== out.length) {
    throw new TypeError(`${name} entries must be unique`)
  }
  return out
}

function importerData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      !IMPORTER_ID.test(value.id || '')) {
    throw new TypeError('workflow importer requires a valid id')
  }
  const mimeTypes = stringList(value.mimeTypes || [], 'mimeTypes', IMPORTER_MIME)
  const extensions = stringList(
    value.extensions || [], 'extensions', IMPORTER_EXTENSION)
  if (!mimeTypes.length && !extensions.length) {
    throw new TypeError('workflow importer must declare a MIME type or extension')
  }
  if (!Number.isSafeInteger(value.maxBytes) || value.maxBytes < 1 ||
      value.maxBytes > IMPORTER_MAX_BYTES) {
    throw new TypeError(`workflow importer maxBytes must be 1..${IMPORTER_MAX_BYTES}`)
  }
  return { id: value.id, mimeTypes, extensions, maxBytes: value.maxBytes }
}

function comboPreviewData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      !IMPORTER_ID.test(value.id || '') || !value.id.includes('.') ||
      value.candidatePolicy !== 'adjacent-model-preview-v1') {
    throw new TypeError('combo preview declaration is invalid')
  }
  const keys = new Set(Object.keys(value))
  if (keys.size !== 5 || ![
    'id', 'modelCategories', 'extensions', 'candidatePolicy', 'media',
  ].every((key) => keys.has(key))) {
    throw new TypeError('combo preview declaration has unsupported fields')
  }
  const closed = (items, name, allowed) => {
    if (!Array.isArray(items) || !items.length || items.length > allowed.size ||
        items.some((item) => typeof item !== 'string' || !allowed.has(item)) ||
        new Set(items).size !== items.length) {
      throw new TypeError(`combo preview ${name} is invalid`)
    }
    return items.slice()
  }
  return {
    id: value.id,
    modelCategories: closed(
      value.modelCategories, 'modelCategories', COMBO_PREVIEW_CATEGORIES),
    extensions: closed(
      value.extensions, 'extensions', COMBO_PREVIEW_EXTENSIONS),
    candidatePolicy: value.candidatePolicy,
    media: closed(value.media, 'media', COMBO_PREVIEW_MEDIA),
  }
}

function comboPreviewAssignmentData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      new Set(Object.keys(value)).size !== 5 || ![
        'category', 'modelValue', 'sourceNodeId', 'imageIndex', 'policy',
      ].every((key) => Object.hasOwn(value, key)) ||
      !COMBO_PREVIEW_CATEGORIES.has(value.category) ||
      typeof value.modelValue !== 'string' ||
      value.modelValue.length < 1 || value.modelValue.length > 1024 ||
      /[\0-\x1f\x7f]/.test(value.modelValue) ||
      typeof value.sourceNodeId !== 'string' ||
      value.sourceNodeId.length < 1 || value.sourceNodeId.length > 256 ||
      /[\0-\x1f\x7f]/.test(value.sourceNodeId) ||
      !Number.isSafeInteger(value.imageIndex) || value.imageIndex < 0 ||
      value.imageIndex > 4095 ||
      value.policy !== 'adjacent-model-preview-v1') {
    throw new TypeError('combo preview assignment is invalid')
  }
  return {
    category: value.category,
    modelValue: value.modelValue,
    sourceNodeId: value.sourceNodeId,
    imageIndex: value.imageIndex,
    policy: value.policy,
  }
}

function managedViewDescriptor(comfy, value) {
  if (typeof value !== 'string' || value.length < 1 || value.length > 4096) {
    throw new TypeError('source node has no bounded image URL')
  }
  const base = new URL(comfy.backend.url('/'))
  const expected = new URL(comfy.backend.url('/view'))
  const parsed = new URL(value, base)
  if (parsed.origin !== expected.origin || parsed.pathname !== expected.pathname ||
      parsed.username || parsed.password || parsed.hash) {
    throw new TypeError('source image is not a managed Comfy view')
  }
  const allowed = new Set([
    'filename', 'subfolder', 'type', 'rand', 'preview', 'channel',
  ])
  for (const key of parsed.searchParams.keys()) {
    if (!allowed.has(key)) {
      throw new TypeError('source image has unsupported view options')
    }
  }
  if (parsed.searchParams.getAll('filename').length !== 1 ||
      parsed.searchParams.getAll('subfolder').length > 1 ||
      parsed.searchParams.getAll('type').length > 1) {
    throw new TypeError('source image has ambiguous view options')
  }
  const filename = parsed.searchParams.get('filename')
  const subfolder = parsed.searchParams.get('subfolder') || ''
  const type = parsed.searchParams.get('type') || 'output'
  if (!filename || !['input', 'output', 'temp'].includes(type)) {
    throw new TypeError('source image has an invalid managed descriptor')
  }
  return { filename, subfolder, type }
}

function dynamicMenuViewsData(value) {
  if (!Array.isArray(value) || value.length > 4096) {
    throw new TypeError('dynamic menu view is too large')
  }
  return value.map((entry) => {
    if (!Array.isArray(entry) || entry.length !== 2 ||
        typeof entry[0] !== 'string' || entry[0].length < 1 ||
        entry[0].length > 1024 || /[\0-\x1f\x7f]/.test(entry[0]) ||
        !Array.isArray(entry[1]) || entry[1].length > 128) {
      throw new TypeError('dynamic menu view is invalid')
    }
    const items = entry[1].map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item) ||
          Object.keys(item).length !== 2 ||
          typeof item.menuId !== 'string' || item.menuId.length < 1 ||
          item.menuId.length > 1024 || /[\0-\x1f\x7f]/.test(item.menuId) ||
          typeof item.label !== 'string' || item.label.length < 1 ||
          item.label.length > 512 || /[\0-\x08\x0b\x0c\x0e-\x1f\x7f]/
            .test(item.label)) {
        throw new TypeError('dynamic menu item is invalid')
      }
      return { menuId: item.menuId, label: item.label }
    })
    return [entry[0], items]
  })
}

function localizationCatalogData(locale, value) {
  if (typeof locale !== 'string' || locale.length > 32 ||
      !LOCALIZATION_LOCALE.test(locale) ||
      !value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('localization catalog declaration is invalid')
  }
  const topKeys = Object.keys(value)
  if (!topKeys.includes('messages') ||
      topKeys.some((key) => key !== 'messages' && key !== 'phrases') ||
      !value.messages || typeof value.messages !== 'object' ||
      Array.isArray(value.messages)) {
    throw new TypeError('localization catalog requires messages')
  }
  let entries = 0
  let bytes = 0
  const seen = new WeakSet()
  const addString = (text, maximum) => {
    if (typeof text !== 'string' || text.includes('\0')) {
      throw new TypeError('localization catalog contains an invalid string')
    }
    const size = new TextEncoder().encode(text).byteLength
    if (size > maximum || (bytes += size) > 4 * 1024 * 1024) {
      throw new TypeError('localization catalog exceeds its bounds')
    }
  }
  const walk = (input, depth) => {
    if (typeof input === 'string') {
      addString(input, 4096)
      return input
    }
    if (input === null) return null
    if (!input || typeof input !== 'object' || Array.isArray(input) ||
        depth > 16 || seen.has(input)) {
      throw new TypeError('localization message tree is invalid')
    }
    seen.add(input)
    const output = {}
    for (const [key, child] of Object.entries(input)) {
      if (LOCALIZATION_FORBIDDEN_KEYS.has(key) || ++entries > 20_000) {
        throw new TypeError('localization catalog has invalid keys or size')
      }
      addString(key, 512)
      output[key] = walk(child, depth + 1)
    }
    seen.delete(input)
    return output
  }
  const messages = walk(value.messages, 0)
  let phrases
  if (value.phrases !== undefined) {
    if (!value.phrases || typeof value.phrases !== 'object' ||
        Array.isArray(value.phrases)) {
      throw new TypeError('localization phrases must be an object')
    }
    phrases = {}
    for (const [source, translated] of Object.entries(value.phrases)) {
      if (LOCALIZATION_FORBIDDEN_KEYS.has(source) ||
          typeof translated !== 'string' || ++entries > 20_000) {
        throw new TypeError('localization phrase is invalid')
      }
      addString(source, 4096)
      addString(translated, 4096)
      phrases[source] = translated
    }
  }
  return { locale, catalog: { messages, ...(phrases ? { phrases } : {}) } }
}

function widgetOptionKey(value) {
  if (typeof value !== 'string' || value.length < 1 || value.length > 128 ||
      /[\0-\x1f\x7f]/.test(value) || FORBIDDEN.has(value)) {
    throw new TypeError('widget option key is invalid')
  }
  return value
}

function widgetOptionValueData(value) {
  let entries = 0
  const seen = new WeakSet()
  const walk = (input, depth) => {
    if (input === undefined || input === null || typeof input === 'boolean') {
      return input
    }
    if (typeof input === 'number') {
      if (!Number.isFinite(input)) {
        throw new TypeError('widget option number must be finite')
      }
      return input
    }
    if (typeof input === 'string') {
      if (input.length > 4096 || input.includes('\0')) {
        throw new TypeError('widget option string exceeds its bound')
      }
      return input
    }
    if (!input || typeof input !== 'object' || depth > 8 || seen.has(input)) {
      throw new TypeError('widget option value is not bounded plain data')
    }
    seen.add(input)
    if (Array.isArray(input)) {
      if (input.length > 256) throw new TypeError('widget option array is too large')
      const result = input.map((item) => {
        if (++entries > 2048) throw new TypeError('widget options are too large')
        return walk(item, depth + 1)
      })
      seen.delete(input)
      return result
    }
    const keys = Object.keys(input)
    if (keys.length > 256) throw new TypeError('widget option object is too large')
    const result = {}
    for (const key of keys) {
      widgetOptionKey(key)
      if (++entries > 2048) throw new TypeError('widget options are too large')
      result[key] = walk(input[key], depth + 1)
    }
    seen.delete(input)
    return result
  }
  const output = walk(value, 0)
  const encoded = JSON.stringify(output)
  if (encoded !== undefined &&
      new TextEncoder().encode(encoded).byteLength > 64 * 1024) {
    throw new TypeError('widget option value exceeds 64 KiB')
  }
  return output
}

function widgetOptionsData(value) {
  if (value === undefined) return undefined
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('widget options must be an object')
  }
  return widgetOptionValueData(value)
}

function importedFileData(value) {
  if (value == null) return undefined
  if (typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('workflow importer result must be an object')
  }
  const keys = Object.keys(value)
  if (keys.length !== 1 || (keys[0] !== 'workflow' && keys[0] !== 'prompt')) {
    throw new TypeError('workflow importer must return exactly workflow or prompt')
  }
  const payload = value[keys[0]]
  if (typeof payload !== 'string' &&
      (!payload || typeof payload !== 'object' || Array.isArray(payload))) {
    throw new TypeError(`workflow importer ${keys[0]} must be a string or object`)
  }
  const json = JSON.stringify({ [keys[0]]: payload })
  if (!json || new TextEncoder().encode(json).byteLength > IMPORT_RESULT_MAX_BYTES) {
    throw new TypeError('workflow importer result is too large or not JSON-safe')
  }
  // Reparse into a plain JSON tree. Structured clone permits cycles and
  // exotic built-ins; the frontend workflow loader deliberately receives
  // neither from an untrusted extension.
  return JSON.parse(json)
}

function safeBasename(value, what) {
  if (typeof value !== 'string' || value.length < 1 || value.length > 255 ||
      value === '.' || value === '..' || /[\\/\0-\x1f\x7f]/.test(value)) {
    throw new TypeError(`${what} must be a safe basename`)
  }
  return value
}

function filePickData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('files.pick requires an options object')
  }
  const mimeTypes = stringList(
    value.mimeTypes || [], 'mimeTypes', IMPORTER_MIME)
  const extensions = stringList(
    value.extensions || [], 'extensions', IMPORTER_EXTENSION)
  if (!mimeTypes.length && !extensions.length) {
    throw new TypeError('files.pick must declare a MIME type or extension')
  }
  if (!Number.isSafeInteger(value.maxBytes) || value.maxBytes < 1 ||
      value.maxBytes > FILE_TRANSFER_MAX_BYTES) {
    throw new TypeError(
      `files.pick maxBytes must be 1..${FILE_TRANSFER_MAX_BYTES}`)
  }
  return { mimeTypes, extensions, maxBytes: value.maxBytes }
}

function filePickManyData(value) {
  const declaration = filePickData(value)
  if (!Number.isSafeInteger(value.maxFiles) || value.maxFiles < 1 ||
      value.maxFiles > FILE_PICK_MAX_FILES) {
    throw new TypeError(
      `files.pickMany maxFiles must be 1..${FILE_PICK_MAX_FILES}`)
  }
  if (!Number.isSafeInteger(value.maxTotalBytes) ||
      value.maxTotalBytes < 1 ||
      value.maxTotalBytes > FILE_TRANSFER_MAX_TOTAL_BYTES ||
      value.maxTotalBytes < value.maxBytes) {
    throw new TypeError(
      `files.pickMany maxTotalBytes must be maxBytes..${FILE_TRANSFER_MAX_TOTAL_BYTES}`)
  }
  return {
    ...declaration,
    maxFiles: value.maxFiles,
    maxTotalBytes: value.maxTotalBytes,
    multiple: true,
  }
}

function fileMatches(file, declaration) {
  const name = String(file.name || '')
  const dot = name.lastIndexOf('.')
  const extension = dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
  const type = String(file.type || '').toLowerCase()
  return declaration.mimeTypes.includes(type) ||
    Boolean(extension && declaration.extensions.includes(extension))
}

function downloadFileData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('files.download requires an options object')
  }
  const name = safeBasename(value.name, 'files.download name')
  const mimeType = String(value.mimeType || '').toLowerCase()
  if (typeof value.mimeType !== 'string' || !IMPORTER_MIME.test(mimeType)) {
    throw new TypeError('files.download requires a safe MIME type')
  }
  if (!(value.bytes instanceof Uint8Array) ||
      value.bytes.byteLength > FILE_TRANSFER_MAX_BYTES) {
    throw new TypeError(
      `files.download bytes must be a Uint8Array of at most ${FILE_TRANSFER_MAX_BYTES} bytes`)
  }
  return { name, mimeType, bytes: value.bytes }
}

function workflowSnapshotData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('workflow snapshot must be an object')
  }
  const json = JSON.stringify(value)
  if (!json || new TextEncoder().encode(json).byteLength >
      WORKFLOW_SNAPSHOT_MAX_BYTES) {
    throw new TypeError('workflow snapshot is too large or not JSON-safe')
  }
  return JSON.parse(json)
}

function ollamaListRequest(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== 1 ||
      typeof value.endpoint !== 'string' || !value.endpoint.trim() ||
      value.endpoint.length > 2048 || value.endpoint.includes('\0')) {
    throw new TypeError(
      'integrations.ollama.listModels requires one bounded endpoint')
  }
  return { endpoint: value.endpoint.trim() }
}

function cryptoBytes(value, name, { exact = null, min = 0,
                                    max = null } = {}) {
  if (!(value instanceof Uint8Array)) {
    throw new TypeError(`${name} must be a Uint8Array`)
  }
  const size = value.byteLength
  if ((exact !== null && size !== exact) || size < min ||
      (max !== null && size > max)) {
    const bound = exact !== null ? `exactly ${exact}` : `${min}..${max}`
    throw new RangeError(`${name} must contain ${bound} bytes`)
  }
  // Detach the operation from any caller-owned view before the first await.
  return new Uint8Array(value)
}

function cryptoObject(value, name, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== keys.length ||
      keys.some((key) => !Object.hasOwn(value, key))) {
    throw new TypeError(`${name} requires exactly ${keys.join(', ')}`)
  }
  return value
}

function subtleCrypto() {
  const subtle = globalThis.crypto?.subtle
  if (!subtle) throw new Error('host WebCrypto is unavailable')
  return subtle
}

async function aesCbcEncrypt(value) {
  const data = cryptoObject(
    value, 'crypto.aesCbcEncrypt', ['key', 'iv', 'plaintext'])
  const key = cryptoBytes(data.key, 'AES-CBC key', { exact: 16 })
  const iv = cryptoBytes(data.iv, 'AES-CBC iv', { exact: 16 })
  const plaintext = cryptoBytes(data.plaintext, 'AES-CBC plaintext', {
    max: CRYPTO_PLAINTEXT_MAX_BYTES,
  })
  const subtle = subtleCrypto()
  const imported = await subtle.importKey(
    'raw', key, { name: 'AES-CBC' }, false, ['encrypt'])
  return new Uint8Array(await subtle.encrypt(
    { name: 'AES-CBC', iv }, imported, plaintext))
}

async function aesCbcDecrypt(value) {
  const data = cryptoObject(
    value, 'crypto.aesCbcDecrypt', ['key', 'iv', 'ciphertext'])
  const key = cryptoBytes(data.key, 'AES-CBC key', { exact: 16 })
  const iv = cryptoBytes(data.iv, 'AES-CBC iv', { exact: 16 })
  const ciphertext = cryptoBytes(data.ciphertext, 'AES-CBC ciphertext', {
    min: 16,
    max: CRYPTO_CIPHERTEXT_MAX_BYTES,
  })
  if (ciphertext.byteLength % 16 !== 0) {
    throw new RangeError('AES-CBC ciphertext must contain complete blocks')
  }
  const subtle = subtleCrypto()
  const imported = await subtle.importKey(
    'raw', key, { name: 'AES-CBC' }, false, ['decrypt'])
  return new Uint8Array(await subtle.decrypt(
    { name: 'AES-CBC', iv }, imported, ciphertext))
}

async function importHmacKey(value, usage) {
  const key = cryptoBytes(value, 'HMAC-SHA256 key', { min: 1, max: 64 })
  return subtleCrypto().importKey(
    'raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, [usage])
}

async function hmacSha256(value) {
  const input = cryptoObject(
    value, 'crypto.hmacSha256', ['key', 'data'])
  const data = cryptoBytes(input.data, 'HMAC-SHA256 data', {
    max: CRYPTO_AUTH_DATA_MAX_BYTES,
  })
  const key = await importHmacKey(input.key, 'sign')
  return new Uint8Array(await subtleCrypto().sign('HMAC', key, data))
}

async function verifyHmacSha256(value) {
  const input = cryptoObject(
    value, 'crypto.verifyHmacSha256', ['key', 'data', 'signature'])
  const data = cryptoBytes(input.data, 'HMAC-SHA256 data', {
    max: CRYPTO_AUTH_DATA_MAX_BYTES,
  })
  const signature = cryptoBytes(
    input.signature, 'HMAC-SHA256 signature', { exact: 32 })
  const key = await importHmacKey(input.key, 'verify')
  return Boolean(await subtleCrypto().verify('HMAC', key, signature, data))
}

async function browserPickFile(declaration) {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = declaration.multiple === true
  input.accept = [
    ...declaration.mimeTypes,
    ...declaration.extensions.map((extension) => `.${extension}`),
  ].join(',')
  input.hidden = true
  document.body.appendChild(input)
  try {
    return await new Promise((resolve) => {
      let settled = false
      const finish = (file) => {
        if (settled) return
        settled = true
        window.removeEventListener('focus', onFocus)
        resolve(file)
      }
      const onFocus = () => {
        // `cancel` is not implemented by every browser. File-change dispatches
        // before this turn when a selection was made; otherwise focus means
        // the native chooser closed without one.
        setTimeout(() => finish(input.multiple
          ? Array.from(input.files || [])
          : input.files?.[0]), 0)
      }
      input.addEventListener('change', () => finish(input.multiple
        ? Array.from(input.files || [])
        : input.files?.[0]), {
        once: true,
      })
      input.addEventListener('cancel', () => finish(undefined), { once: true })
      window.addEventListener('focus', onFocus)
      input.click()
    })
  } finally {
    input.remove()
  }
}

function browserDownloadFile({ name, mimeType, bytes }) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mimeType }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.hidden = true
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

export function isPackAssetUrl(entryUrl, assetUrl) {
  try {
    const entry = new URL(entryUrl)
    const asset = new URL(assetUrl)
    const root = /^\/extensions\/[^/]+\//.exec(entry.pathname)?.[0]
    return Boolean(
      root && asset.origin === entry.origin && asset.pathname.startsWith(root))
  } catch {
    return false
  }
}

export class SecureExtensionHost {
  /**
   * @param comfy        the real V2 comfy API (globalThis.comfy)
   * @param bootstrapUrl URL of the guest bootstrap module
   * @param match        (url) => boolean : which extensions we take over
   */
  constructor({ comfy, bootstrapUrl, match = () => true, capabilities = null,
                workflowSnapshot = null, filePicker = browserPickFile,
                fileDownloader = browserDownloadFile,
                provideComboOptionPreviewSource = null,
                registerLocalizationCatalog = null }) {
    this.name = 'secure-nodes-sandbox'
    this.policy = 'exclusive'
    this.comfy = comfy
    this.capabilities = capabilities
    this._workflowSnapshot = workflowSnapshot
    this._filePicker = filePicker
    this._fileDownloader = fileDownloader
    this._match = match
    this._uiByKey = new Map()      // `${pack}:${nodeId}:${widget}` -> ui handle
    this._elements = new Map()     // `${pack}:${name}` -> HTMLElement
    this._packEntries = new Map()
    this._definitionOwners = new Map()
    this._definitionDisposers = new Set()
    this._nodeCanvases = new Map()
    this._packCapabilities = new Map()
    this._packRouteBase = new Map()
    this._importers = new Map()    // `${pack}:${id}` -> bounded data
    this._actionButtons = new Map() // `${pack}:${id}` -> host handle
    this._topBarBadges = new Map() // `${pack}:${id}` -> host handle
    this._dialogs = new Map()
    this._dialogByKey = new Map()
    this._comboPreviews = new Map() // `${pack}:${id}` -> bounded policy
    this._localizationCatalogs = new Map() // `${pack}:${locale}` -> unsubscribe
    this._registerLocalizationCatalog = registerLocalizationCatalog
    this._provideComboOptionPreviewSource = provideComboOptionPreviewSource
    if (typeof provideComboOptionPreviewSource === 'function') {
      provideComboOptionPreviewSource({
        show: (value, anchor) => {
          void this._showComboOptionPreview(value, anchor)
        },
        hide: () => this._hideComboOptionPreview(),
      })
    }
    this._host = new SandboxHost({
      bootstrapUrl,
      onPackMessage: (pack, msg) => this._onPackMessage(pack, msg),
    })
    this._installGraphFeed()
  }

  _hideComboOptionPreview() {
    this._comboPreviewRequest = (this._comboPreviewRequest || 0) + 1
    if (!this._comboPreviewView) return
    this._comboPreviewView.root.remove()
    URL.revokeObjectURL(this._comboPreviewView.url)
    this._comboPreviewView = null
  }

  async _showComboOptionPreview(value, anchor) {
    this._hideComboOptionPreview()
    if (typeof value !== 'string' || value.length > 1024 ||
        !(anchor instanceof HTMLElement)) return
    const dot = value.lastIndexOf('.')
    const extension = dot < 0 ? '' : value.slice(dot + 1).toLowerCase()
    const policy = [...this._comboPreviews.values()].find(
      (entry) => entry.extensions.includes(extension))
    if (!policy) return
    const request = this._comboPreviewRequest
    let response
    try {
      response = await this.comfy.backend.fetch(
        '/secure-nodes/assets/model-preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            value,
            modelCategories: policy.modelCategories,
            candidatePolicy: policy.candidatePolicy,
            media: policy.media,
          }),
        })
    } catch {
      return
    }
    if (request !== this._comboPreviewRequest || !response?.ok) return
    const mimeType = String(
      response.headers?.get?.('content-type') || '').split(';', 1)[0]
    if (!policy.media.includes(mimeType)) return
    let blob
    try {
      blob = await response.blob()
    } catch {
      return
    }
    if (request !== this._comboPreviewRequest ||
        blob.size < 1 || blob.size > 64 * 1024 * 1024) return

    const url = URL.createObjectURL(blob)
    const root = document.createElement('div')
    Object.assign(root.style, {
      position: 'fixed', zIndex: '100000', width: '320px', maxHeight: '360px',
      padding: '6px', borderRadius: '8px', pointerEvents: 'none',
      background: 'rgba(16, 16, 20, 0.96)',
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)', overflow: 'hidden',
    })
    const media = document.createElement(
      mimeType.startsWith('video/') ? 'video' : 'img')
    media.src = url
    Object.assign(media.style, {
      display: 'block', width: '100%', maxHeight: '348px', objectFit: 'contain',
    })
    if (media instanceof HTMLVideoElement) {
      media.autoplay = true
      media.loop = true
      media.muted = true
      media.playsInline = true
    }
    root.append(media)
    document.body.append(root)
    const rect = anchor.getBoundingClientRect()
    const width = 332
    const left = rect.right + 8 + width <= window.innerWidth
      ? rect.right + 8 : Math.max(8, rect.left - width - 8)
    const top = Math.max(8, Math.min(
      rect.top, window.innerHeight - 376))
    root.style.left = `${left}px`
    root.style.top = `${top}px`
    this._comboPreviewView = { root, url }
  }

  // ---- ExtensionHostProvider contract ------------------------------------
  canLoad(url) { return this._match(url) }

  async load(url) {
    const pack = url.replace(/^\/extensions\//, '').split('/')[0] || url
    const abs = new URL(url, location.origin).href
    this._packEntries.set(pack, abs)
    // One worker per PACK: every entry module a pack ships loads into the same
    // worker, so its modules share one realm, one registration table and one
    // capability grant — and can import each other.
    //
    // The entry source is fetched HERE, same-origin, as the FALLBACK path.
    // The guest prefers importing the real URL — which is what gives a
    // multi-file pack a base URL for its relative imports — and that works
    // exactly when the asset origin answers CORS (the sandbox is an opaque
    // origin, so every module fetch from it is cross-origin). The retired
    // DEBT.md F5 blob-only path is what this replaces.
    const res = await fetch(abs)
    if (!res.ok) throw new Error(`pack fetch failed: ${res.status} ${abs}`)
    const packSource = await res.text()
    // Per-entry outcome, kept for diagnostics and e2e assertions — a red
    // matrix entry must stay observable, not vanish into a console line.
    this.loadResults ??= []
    try {
      const defs = await this._ensureDefs()
      const hasExecutionLifecycle =
        typeof this.comfy.executingNode === 'function' &&
        typeof this.comfy.onExecutingNodeChanged === 'function'
      const backendBase = this.comfy.backend.url('/')
      const backendAssetBase = typeof this.comfy.backend.assetUrl === 'function'
        ? this.comfy.backend.assetUrl('/') : new URL('/', backendBase).href
      const boot = {
        defs,
        backendBase,
        backendAssetBase,
        executionLifecycle: hasExecutionLifecycle,
        executingNode: hasExecutionLifecycle
          ? this._nodeSnapshot(this.comfy.executingNode()) : undefined,
      }
      let granted = this.capabilities
      if (granted == null) {
        try {
          const response = await this.comfy.backend.fetch(
            `/secure-nodes/extensions/${encodeURIComponent(pack)}/capabilities`)
          const value = response?.ok ? await response.json() : null
          granted = Array.isArray(value?.capabilities) &&
            value.capabilities.length <= 32 &&
            value.capabilities.every((item) => typeof item === 'string')
            ? value.capabilities : []
          if (typeof value?.route_base === 'string' && value.route_base) {
            this._packRouteBase.set(pack, value.route_base)
            boot.routeBase = value.route_base
          }
        } catch {
          granted = []
        }
      }
      this._packCapabilities.set(pack, new Set(granted || []))
      const outcome = await this._host.loadPack(
        pack, abs, granted || [], packSource, boot)
      this.loadResults.push({ pack, url, ok: true,
                              mode: outcome && outcome.mode })
    } catch (error) {
      this.loadResults.push({ pack, url, ok: false, error: String(error) })
      throw error
    }
  }

  /**
   * Optional host-wide file importer. The browser owns the File and reads it
   * only after a bounded declaration matches. Pack parsing stays in its
   * worker; undefined is the explicit native-import fallback.
   */
  async importFile(file) {
    const name = typeof file?.name === 'string' ? file.name : ''
    const type = typeof file?.type === 'string' ? file.type.toLowerCase() : ''
    if (!name || name.length > 512 || type.length > 128 ||
        !Number.isSafeInteger(file?.size) || file.size < 0) return undefined
    const dot = name.lastIndexOf('.')
    const extension = dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
    let bytes = null
    for (const rec of this._importers.values()) {
      const matches = rec.mimeTypes.includes(type) ||
        (extension && rec.extensions.includes(extension))
      if (!matches || file.size > rec.maxBytes) continue
      try {
        bytes ??= await file.arrayBuffer()
        if (bytes.byteLength !== file.size || bytes.byteLength > rec.maxBytes) {
          continue
        }
        const value = await this._askGuest(rec.pack, {
          t: 'importFile', importerId: rec.id, name, type, bytes,
        })
        const imported = importedFileData(value)
        if (imported !== undefined) return imported
      } catch (error) {
        console.warn(
          `[secure-nodes] workflow importer '${rec.pack}:${rec.id}' failed`, error)
      }
    }
    return undefined
  }

  async _snapshotWorkflow() {
    const snapshot = this._workflowSnapshot || (
      typeof this.comfy?.workflow?.snapshot === 'function'
        ? () => this.comfy.workflow.snapshot()
        : null)
    if (typeof snapshot !== 'function') {
      throw new Error('workflow snapshot is unavailable')
    }
    return workflowSnapshotData(await snapshot())
  }

  async _pickFile(value) {
    const declaration = filePickData(value)
    if (typeof this._filePicker !== 'function') {
      throw new Error('file picker is unavailable')
    }
    const file = await this._filePicker(declaration)
    if (file == null) return undefined
    const name = safeBasename(file.name, 'selected file name')
    const type = typeof file.type === 'string' ? file.type.toLowerCase() : ''
    if (type && !IMPORTER_MIME.test(type)) {
      throw new TypeError('selected file has an invalid MIME type')
    }
    if (!Number.isSafeInteger(file.size) || file.size < 0 ||
        file.size > declaration.maxBytes ||
        typeof file.arrayBuffer !== 'function' ||
        !fileMatches({ name, type }, declaration)) {
      throw new TypeError('selected file does not match the bounded declaration')
    }
    const buffer = await file.arrayBuffer()
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength !== file.size ||
        buffer.byteLength > declaration.maxBytes) {
      throw new TypeError('selected file changed or exceeded its declared bound')
    }
    return { name, type, bytes: new Uint8Array(buffer) }
  }

  async _pickFiles(value) {
    const declaration = filePickManyData(value)
    if (typeof this._filePicker !== 'function') {
      throw new Error('file picker is unavailable')
    }
    const selected = await this._filePicker(declaration)
    if (selected == null) return []
    const files = Array.isArray(selected) ? selected : Array.from(selected)
    if (files.length > declaration.maxFiles) {
      throw new TypeError('too many files were selected')
    }
    let totalBytes = 0
    const checked = []
    for (const file of files) {
      const name = safeBasename(file?.name, 'selected file name')
      const type = typeof file?.type === 'string' ? file.type.toLowerCase() : ''
      if (type && !IMPORTER_MIME.test(type)) {
        throw new TypeError('selected file has an invalid MIME type')
      }
      if (!Number.isSafeInteger(file?.size) || file.size < 0 ||
          file.size > declaration.maxBytes ||
          typeof file.arrayBuffer !== 'function' ||
          !fileMatches({ name, type }, declaration)) {
        throw new TypeError('selected file does not match the bounded declaration')
      }
      totalBytes += file.size
      if (totalBytes > declaration.maxTotalBytes) {
        throw new TypeError('selected files exceed the total byte limit')
      }
      checked.push({ file, name, type })
    }
    const result = []
    let actualTotal = 0
    for (const { file, name, type } of checked) {
      const buffer = await file.arrayBuffer()
      if (!(buffer instanceof ArrayBuffer) || buffer.byteLength !== file.size ||
          buffer.byteLength > declaration.maxBytes) {
        throw new TypeError('selected file changed or exceeded its declared bound')
      }
      actualTotal += buffer.byteLength
      if (actualTotal > declaration.maxTotalBytes) {
        throw new TypeError('selected files exceed the total byte limit')
      }
      result.push({ name, type, bytes: new Uint8Array(buffer) })
    }
    return result
  }

  async _downloadFile(value) {
    const data = downloadFileData(value)
    if (typeof this._fileDownloader !== 'function') {
      throw new Error('file download is unavailable')
    }
    await this._fileDownloader(data)
  }

  // ---- pack -> host ------------------------------------------------------
  async _onPackMessage(pack, msg) {
    if (!msg || !msg.t) return
    const reply = (ok, value, error) =>
      this._host.send(pack, { t: 'ret', id: msg.id, ok, value, error })

    try {
      if (msg.t === 'call') {                       // comfy.* RPC
        if (msg.path === 'comfy.workflow.snapshot') {
          return reply(true, await this._snapshotWorkflow())
        }
        if (msg.path === 'comfy.files.pick') {
          return reply(true, await this._pickFile(msg.args?.[0]))
        }
        if (msg.path === 'comfy.files.pickMany') {
          return reply(true, await this._pickFiles(msg.args?.[0]))
        }
        if (msg.path === 'comfy.files.download') {
          await this._downloadFile(msg.args?.[0])
          return reply(true, null)
        }
        if (msg.path === 'comfy.crypto.aesCbcEncrypt') {
          return reply(true, await aesCbcEncrypt(msg.args?.[0]))
        }
        if (msg.path === 'comfy.crypto.aesCbcDecrypt') {
          return reply(true, await aesCbcDecrypt(msg.args?.[0]))
        }
        if (msg.path === 'comfy.crypto.hmacSha256') {
          return reply(true, await hmacSha256(msg.args?.[0]))
        }
        if (msg.path === 'comfy.crypto.verifyHmacSha256') {
          return reply(true, await verifyHmacSha256(msg.args?.[0]))
        }
        if (msg.path === 'comfy.integrations.ollama.listModels') {
          const request = ollamaListRequest(msg.args?.[0])
          const response = await this.comfy.backend.fetch(
            '/secure-nodes/integrations/ollama/models', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(request),
            })
          if (!response.ok) {
            throw new Error(`Ollama model listing failed: HTTP ${response.status}`)
          }
          const value = await response.json()
          if (!value || typeof value !== 'object' ||
              !Array.isArray(value.models) || value.models.length > 512 ||
              value.models.some((model) =>
                typeof model !== 'string' || !model || model.length > 512)) {
            throw new Error('Ollama model listing returned an invalid response')
          }
          return reply(true, [...new Set(value.models)])
        }
        if (msg.path === 'comfy.commands.playSound') {
          const src = msg.args?.[0]?.src
          if (typeof src !== 'string' ||
              !isPackAssetUrl(this._packEntries.get(pack), src)) {
            throw new Error('sound source must be an asset in this node pack')
          }
        }
        const fn = resolveComfyPath(this.comfy, msg.path)
        const args = (msg.args || []).map((a) => this._reviveArg(pack, a))
        const value = await fn(...args)
        return reply(true, this._sanitizeReturn(value))
      }

      if (msg.t === 'extend') {                     // declare-then-apply
        this._applyExtend(pack, msg)
        return reply(true, null)
      }

      if (msg.t === 'define') {                     // pack-owned node type
        this._applyDefine(pack, msg)
        return reply(true, null)
      }

      if (msg.t === 'importerreg') {
        const data = importerData(msg.def)
        const key = `${pack}:${data.id}`
        if (this._importers.has(key)) {
          throw new Error(`duplicate workflow importer '${data.id}'`)
        }
        this._importers.set(key, { pack, ...data })
        return reply(true, null)
      }

      if (msg.t === 'importerremove') {
        this._importers.delete(`${pack}:${String(msg.importerId || '')}`)
        return reply(true, null)
      }

      if (msg.t === 'combopreviewreg') {
        const data = comboPreviewData(msg.def)
        const key = `${pack}:${data.id}`
        if (this._comboPreviews.has(key)) {
          throw new Error(`duplicate combo preview '${data.id}'`)
        }
        this._comboPreviews.set(key, { pack, ...data })
        return reply(true, null)
      }

      if (msg.t === 'combopreviewremove') {
        this._comboPreviews.delete(`${pack}:${String(msg.previewId || '')}`)
        this._hideComboOptionPreview()
        return reply(true, null)
      }

      if (msg.t === 'combopreviewassign') {
        const data = comboPreviewAssignmentData(msg.assignment)
        const node = this.comfy.graph.node(data.sourceNodeId)
        if (!node) {
          throw new Error(`no such preview source node: ${data.sourceNodeId}`)
        }
        const images = node.getOutputImages()
        if (!Array.isArray(images) || data.imageIndex >= images.length) {
          throw new Error('preview source image index is unavailable')
        }
        const source = managedViewDescriptor(
          this.comfy, images[data.imageIndex])
        const response = await this.comfy.backend.fetch(
          '/secure-nodes/assets/assign-model-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              category: data.category,
              modelValue: data.modelValue,
              source,
              policy: data.policy,
            }),
          })
        if (!response?.ok) {
          throw new Error(`model preview assignment failed (${response?.status})`)
        }
        await this.comfy.defs.refresh()
        return reply(true, null)
      }

      if (msg.t === 'localereg') {
        if (!this._packCapabilities.get(pack)?.has('localization')) {
          throw new Error("frontend capability 'localization' is not granted")
        }
        if (typeof this._registerLocalizationCatalog !== 'function') {
          throw new Error('host localization catalog provider is unavailable')
        }
        const data = localizationCatalogData(msg.locale, msg.catalog)
        const key = `${pack}:${data.locale}`
        if (this._localizationCatalogs.has(key)) {
          throw new Error(`duplicate localization catalog '${data.locale}'`)
        }
        const remove = this._registerLocalizationCatalog(
          pack, data.locale, data.catalog)
        if (typeof remove !== 'function') {
          throw new Error('host localization provider returned no unsubscribe')
        }
        this._localizationCatalogs.set(key, remove)
        if (this.comfy.settings.get('Comfy.Locale') === data.locale) {
          await this.comfy.defs.refresh()
        }
        return reply(true, null)
      }

      if (msg.t === 'localeremove') {
        const locale = String(msg.locale || '')
        const key = `${pack}:${locale}`
        const remove = this._localizationCatalogs.get(key)
        if (!remove) throw new Error(`no localization catalog '${locale}'`)
        remove()
        this._localizationCatalogs.delete(key)
        if (this.comfy.settings.get('Comfy.Locale') === locale) {
          await this.comfy.defs.refresh()
        }
        return reply(true, null)
      }

      if (msg.t === 'answer') {                     // guest answering our ask
        const pending = this._asks?.get(msg.reqId)
        if (!pending) return
        this._asks.delete(msg.reqId)
        msg.ok ? pending.resolve(msg.value)
               : pending.reject(new Error(msg.error))
        return
      }

      if (msg.t === 'dialogreg') {
        this._openDialog(pack, msg)
        return reply(true, null)
      }

      if (msg.t === 'dialogupdate') {
        const rec = this._dialogs.get(`${pack}:${String(msg.dialogId || '')}`)
        if (!rec || rec.closed) throw new Error('sandbox dialog is not open')
        if (typeof msg.markup !== 'string' ||
            new TextEncoder().encode(msg.markup).byteLength > 2 * 1024 * 1024) {
          throw new TypeError('sandbox dialog markup exceeds its bounds')
        }
        rec.markup = msg.markup
        rec.ui?.update(msg.markup)
        return reply(true, null)
      }

      if (msg.t === 'dialogclose') {
        const rec = this._dialogs.get(`${pack}:${String(msg.dialogId || '')}`)
        if (!rec || rec.closed) return reply(true, null)
        try { rec.handle?.close() } finally {
          this._finishDialog(pack, rec)
        }
        return reply(true, null)
      }

      if (msg.t === 'ui') {                         // mount / update node UI
        const hostKey = `${pack}:${msg.key}`
        let ui = this._uiByKey.get(hostKey)
        if (!ui) {
          ui = this._mountNodeUI(pack, hostKey, msg.key, msg.nodeId, msg.name)
        }
        ui.update(msg.markup)
        return reply(true, null)
      }

      if (msg.t === 'elem') {                       // element handle op
        return reply(...this._elementOp(pack, msg))
      }

      if (msg.t === 'backendfetch') {               // Response cannot cross
        const path = String(msg.path ?? '')
        if (path.startsWith('/ext/')) {
          // Pack endpoints are exclusive to the pack that declared them, so a
          // worker may address its own base and nothing else. The base is a
          // secret, but a leaked one must still not be usable by its finder.
          const base = this._packRouteBase.get(pack)
          if (!base || !path.startsWith(`/ext/${base}/`)) {
            throw new Error('pack routes are private to the pack that declares them')
          }
        }
        const res = await this.comfy.backend.fetch(path, msg.init)
        const body = await res.text()
        return reply(true, { ok: res.ok, status: res.status, body })
      }

      if (msg.t === 'systemmonitor') {
        if (!this._packCapabilities.get(pack)?.has('system.monitor')) {
          throw new Error("frontend capability 'system.monitor' is not granted")
        }
        if (typeof this.comfy.system?.monitor !== 'function') {
          throw new Error('host system monitor is unavailable')
        }
        return reply(true, await this.comfy.system.monitor())
      }

      if (msg.t === 'nodecanvasmount') {
        const node = this._scopedNode(msg)
        if (!node || this._definitionOwners.get(node.type) !== pack) {
          throw new Error('node canvas requires a node type defined by this pack')
        }
        if (typeof msg.surfaceId !== 'string' || !/^[a-z0-9-]{1,64}$/i.test(msg.surfaceId)) {
          throw new TypeError('invalid node canvas surface id')
        }
        const bounds = nodeCanvasBoundsData(msg.bounds)
        if (msg.layer !== undefined && msg.layer !== 'foreground') {
          throw new TypeError('invalid node canvas layer')
        }
        const key = JSON.stringify([pack, String(node.graphId), String(node.id)])
        this._checkNodeCanvasBudget(pack, key, bounds)
        this._removeNodeCanvas(key)
        const rec = { pack, nodeId: String(node.id), graphId: String(node.graphId),
          surfaceId: msg.surfaceId, bounds, bitmap: null, revision: -1, surface: null }
        rec.surface = node.canvas({ bounds, layer: msg.layer, draw: (ctx) => {
          if (rec.bitmap) ctx.drawImage(rec.bitmap, rec.bounds.x, rec.bounds.y)
        } })
        this._nodeCanvases.set(key, rec)
        return reply(true, null)
      }
      if (msg.t === 'nodecanvasframe') {
        const key = JSON.stringify([pack, String(msg.graphId), String(msg.nodeId)])
        const rec = this._nodeCanvases.get(key)
        const bitmap = msg.bitmap
        try {
          if (!rec || rec.surfaceId !== msg.surfaceId ||
              !Number.isSafeInteger(msg.revision) || msg.revision <= rec.revision) return
          const node = this._scopedNode(msg)
          if (!node || this._definitionOwners.get(node.type) !== pack) {
            this._removeNodeCanvas(key)
            throw new Error('node canvas owner is no longer present')
          }
          const bounds = nodeCanvasBoundsData(msg.bounds)
          this._checkNodeCanvasBudget(pack, key, bounds)
          if (!(bitmap instanceof ImageBitmap) || bitmap.width !== Math.ceil(bounds.width) ||
              bitmap.height !== Math.ceil(bounds.height)) {
            throw new TypeError('node canvas bitmap does not match its bounded geometry')
          }
          rec.bitmap?.close()
          rec.bitmap = bitmap
          rec.bounds = bounds
          rec.revision = msg.revision
          rec.surface.setBounds(bounds)
        } finally {
          if (rec?.bitmap !== bitmap) bitmap?.close?.()
        }
        return
      }
      if (msg.t === 'nodecanvasremove') {
        const key = JSON.stringify([pack, String(msg.graphId), String(msg.nodeId)])
        if (this._nodeCanvases.get(key)?.surfaceId === msg.surfaceId) {
          this._removeNodeCanvas(key)
        }
        return reply(true, null)
      }

      if (msg.t === 'canvasmount') {                // guest-drawn canvas widget
        const node = this.comfy.graph.node(String(msg.nodeId))
        if (!node) return reply(false, null, `no such node: ${msg.nodeId}`)
        const key = `${pack}:${msg.nodeId}:${msg.name}`
        this._canvasWidgets ??= new Map()
        const rec = { bitmap: null, size: null, surface: null }
        this._canvasWidgets.set(key, rec)
        const allowedHandlers = new Set([
          'onPointerDown', 'onPointerMove', 'onPointerUp', 'onContextMenu',
        ])
        if (!Array.isArray(msg.handlers) || msg.handlers.length > 4 ||
            msg.handlers.some((name) => !allowedHandlers.has(name)) ||
            new Set(msg.handlers).size !== msg.handlers.length) {
          return reply(false, null, 'invalid canvas pointer handlers')
        }
        const pointerHandler = (handler) => (detail) => {
          const bounded = (value) => Number.isFinite(value) &&
            Math.abs(value) <= 10_000_000 ? value : 0
          const source = detail?.event || detail
          this._host.send(pack, {
            t: 'canvasevent', nodeId: msg.nodeId, name: msg.name, handler,
            x: bounded(detail?.x), y: bounded(detail?.y),
            event: {
              type: typeof source?.type === 'string' ? source.type.slice(0, 32) : '',
              detail: Number.isInteger(source?.detail) && source.detail >= 0 &&
                source.detail <= 4 ? source.detail : 0,
              ...actionEventData(source),
            },
          })
        }
        const pointerHandlers = Object.fromEntries(
          msg.handlers.map((handler) => [handler, pointerHandler(handler)]))
        rec.surface = node.widgets.canvas({
          ...msg.opts,
          ...pointerHandlers,
          name: msg.name,
          draw: (ctx, size) => {
            // The host paints the LAST bitmap every frame, so pan/zoom stays
            // host-instant; the guest redraws only when its state changes —
            // and when the size does, which it learns from this very pass.
            if (!rec.size || rec.size[0] !== size[0] || rec.size[1] !== size[1]) {
              rec.size = [size[0], size[1]]
              this._host.send(pack, { t: 'canvassize', nodeId: msg.nodeId,
                                      name: msg.name, size: rec.size })
            }
            if (rec.bitmap) ctx.drawImage(rec.bitmap, 0, 0, size[0], size[1])
          },
        })
        return reply(true, null)
      }

      if (msg.t === 'canvasbitmap') {               // fresh pixels from guest
        const rec = this._canvasWidgets?.get(`${pack}:${msg.nodeId}:${msg.name}`)
        if (!rec) return
        rec.bitmap = msg.bitmap
        rec.surface?.redraw?.()
        return
      }

      if (msg.t === 'uibitmap') {                   // pixels for a mounted <canvas>
        const ui = this._uiByKey.get(`${pack}:${msg.key}`)
        if (!ui) return
        ui.bitmaps ??= new Map()
        ui.bitmaps.set(msg.stubId, msg.bitmap)
        ui.paintBitmaps?.()
        return
      }

      if (msg.t === 'badge') {
        const node = this.comfy.graph.node(String(msg.nodeId))
        if (!node) return reply(false, null, `no such node: ${msg.nodeId}`)
        this._badges ??= new Map()
        const rec = { def: null, remove: null }
        const apply = (def, hasClick) => {
          rec.def = {
            ...badgeData(def),
            ...(hasClick === true
              ? { onClick: () => {
                  this._host.send(pack, { t: 'badgeclick', badgeId: msg.badgeId })
                } }
              : {}),
          }
        }
        apply(msg.def, msg.hasClick)
        // The provider itself is host-owned and synchronous. Pack code and
        // closures remain in the worker; `badgeview` only replaces this tiny
        // data snapshot when sandbox state changes.
        rec.remove = node.addBadge(() => rec.def)
        this._badges.set(`${pack}:${msg.badgeId}`, rec)
        return reply(true, null)
      }

      if (msg.t === 'badgeview') {
        for (const update of msg.updates || []) {
          const rec = this._badges?.get(`${pack}:${update.badgeId}`)
          if (!rec) continue
          rec.def = {
            ...badgeData(update.def),
            ...(update.hasClick === true
              ? { onClick: () => {
                  this._host.send(pack, { t: 'badgeclick',
                                          badgeId: update.badgeId })
                } }
              : {}),
          }
        }
        return reply(true, null)
      }

      if (msg.t === 'badgeremove') {
        const rec = this._badges?.get(`${pack}:${msg.badgeId}`)
        if (typeof rec?.remove === 'function') rec.remove()
        this._badges?.delete(`${pack}:${msg.badgeId}`)
        return reply(true, null)
      }

      if (msg.t === 'measurepath') {
        // Real SVG geometry, computed once per `d` change and returned as
        // data: total length plus an even sampling the guest interpolates.
        // 256 samples is well under a pixel of error at editor scale and
        // keeps the message small.
        this._pathEl ??= (() => {
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
          svg.setAttribute('width', '0')
          svg.setAttribute('height', '0')
          svg.style.position = 'absolute'
          svg.style.visibility = 'hidden'
          const path = document.createElementNS(
            'http://www.w3.org/2000/svg', 'path')
          svg.appendChild(path)
          document.body.appendChild(svg)
          return path
        })()
        this._pathEl.setAttribute('d', msg.d)
        const length = this._pathEl.getTotalLength()
        const SAMPLES = 256
        const points = []
        for (let i = 0; i <= SAMPLES; i++) {
          const pt = this._pathEl.getPointAtLength((length * i) / SAMPLES)
          points.push([pt.x, pt.y])
        }
        return reply(true, { length, points })
      }

      if (msg.t === 'commandreg') {
        // Data + a run trampoline; the closure stays in the worker.
        this.comfy.commands.register({
          ...msg.def,
          run: () => { this._host.send(pack, { t: 'command', id: msg.def.id }) },
        })
        return reply(true, null)
      }

      if (msg.t === 'uiactionreg') {
        const data = actionButtonData(msg.def)
        const key = `${pack}:${data.id}`
        if (this._actionButtons.has(key)) {
          throw new Error(`duplicate action-bar button '${data.id}'`)
        }
        const handle = this.comfy.ui.addActionBarButton({
          ...data,
          run: (event) => {
            this._host.send(pack, {
              t: 'uiaction', id: data.id, event: actionEventData(event),
            })
          },
        })
        if (!handle || typeof handle.update !== 'function' ||
            typeof handle.remove !== 'function') {
          throw new Error('action-bar button host returned an invalid handle')
        }
        this._actionButtons.set(key, handle)
        return reply(true, null)
      }

      if (msg.t === 'uiactionupdate') {
        const id = String(msg.id || '')
        const handle = this._actionButtons.get(`${pack}:${id}`)
        if (!handle) throw new Error(`no action-bar button '${id}'`)
        handle.update(actionButtonData(msg.changes, { partial: true }))
        return reply(true, null)
      }

      if (msg.t === 'uiactionremove') {
        const id = String(msg.id || '')
        const key = `${pack}:${id}`
        const handle = this._actionButtons.get(key)
        if (!handle) throw new Error(`no action-bar button '${id}'`)
        handle.remove()
        this._actionButtons.delete(key)
        return reply(true, null)
      }

      if (msg.t === 'uitopbarreg') {
        const data = topBarBadgeData(msg.def)
        const key = `${pack}:${data.id}`
        if (this._topBarBadges.has(key)) {
          throw new Error(`duplicate top-bar badge '${data.id}'`)
        }
        const handle = this.comfy.ui.addTopBarBadge(data)
        if (!handle || typeof handle.update !== 'function' ||
            typeof handle.remove !== 'function') {
          throw new Error('top-bar badge host returned an invalid handle')
        }
        this._topBarBadges.set(key, handle)
        return reply(true, null)
      }

      if (msg.t === 'uitopbarupdate') {
        const id = String(msg.id || '')
        const handle = this._topBarBadges.get(`${pack}:${id}`)
        if (!handle) throw new Error(`no top-bar badge '${id}'`)
        handle.update(topBarBadgeData(msg.changes, { partial: true }))
        return reply(true, null)
      }

      if (msg.t === 'uitopbarremove') {
        const id = String(msg.id || '')
        const key = `${pack}:${id}`
        const handle = this._topBarBadges.get(key)
        if (!handle) throw new Error(`no top-bar badge '${id}'`)
        handle.remove()
        this._topBarBadges.delete(key)
        return reply(true, null)
      }

      if (msg.t === 'settingsdeclare') {
        // Data-only declare; the pack's onChange stayed guest-side. Answer
        // with the STORED value — a user's saved choice beats the default the
        // guest seeded, and it must correct the cache before gates read it.
        this.comfy.settings.declare(msg.def)
        return reply(true, this._sanitizeReturn(
          this.comfy.settings.get(msg.def.id)))
      }

      if (msg.t === 'serializeview') {       // pack's saved-workflow blob
        this._serializeView ??= new Map()
        for (const [key, value] of msg.payloads) {
          this._serializeView.set(`${pack}:${key}`, value)
        }
        return
      }

      if (msg.t === 'menuview') {            // per-node menu item visibility
        this._menuView ??= new Map()
        for (const [key, shown] of msg.vis) {
          this._menuView.set(`${pack}:${key}`, shown)
        }
        return
      }

      if (msg.t === 'menudynamicview') {
        this._menuDynamicView ??= new Map()
        for (const [key, items] of dynamicMenuViewsData(msg.views)) {
          this._menuDynamicView.set(`${pack}:${key}`, items)
        }
        return
      }

      if (msg.t === 'nodeop') return reply(...this._nodeOp(msg))
      if (msg.t === 'graphop') return reply(...this._graphOp(pack, msg))
      if (msg.t === 'sub') return reply(...this._subscribe(pack, msg))
      if (msg.t === 'unsub') return reply(...this._unsubscribe(pack, msg))

      if (msg.t === 'subwidget') {                  // per-widget change events
        const node = this.comfy.graph.node(String(msg.nodeId))
        const w = node && node.widgets.get(msg.name)
        if (!w) return reply(false, null, `no widget '${msg.name}' on ${msg.nodeId}`)
        const unsub = w.on(msg.event, (...eventArgs) => {
          this._host.send(pack, {
            t: 'event', subId: msg.subId,
            args: eventArgs.map((v) => this._sanitizeReturn(v)),
          })
        })
        this._subs ??= new Map()
        this._subs.set(`${pack}:${msg.subId}`, unsub)
        return reply(true, null)
      }

      if (msg.t === 'packerror') {                  // guest-side hook failure
        this.packErrors ??= []
        this.packErrors.push({ pack, hook: msg.hook, error: msg.error })
        console.error(`[secure-nodes] pack '${pack}' ${msg.hook}:`, msg.error)
        return
      }
    } catch (e) {
      return reply(false, null, String((e && e.message) || e))
    }
  }

  /** Values returned to a pack must be structured-cloneable and inert. */
  _sanitizeReturn(v) {
    if (v == null) return v
    const t = typeof v
    if (t === 'string' || t === 'number' || t === 'boolean') return v
    if (Array.isArray(v)) return v.map((x) => this._sanitizeReturn(x))
    // Binary payloads are data, and enumerating their keys yields {} — which
    // is how a preview frame's Blob arrived as nothing. They clone natively.
    if (v instanceof Blob || v instanceof ArrayBuffer ||
        ArrayBuffer.isView(v) ||
        (typeof ImageBitmap !== 'undefined' && v instanceof ImageBitmap)) {
      return v
    }
    if (t === 'object') {
      const out = {}
      for (const k of Object.keys(v)) {
        const val = v[k]
        if (typeof val === 'function') continue      // never hand back callables
        out[k] = this._sanitizeReturn(val)
      }
      return out
    }
    return undefined                                 // functions, symbols: dropped
  }

  _reviveArg(pack, a) { return a }

  // ---- graph state for the guest -----------------------------------------

  /**
   * A node, as data. This is what a guest-side handle reads from: hook and
   * menu dispatches carry one so the receiving closure's synchronous reads
   * answer from state that was true at dispatch, and the epoch push carries
   * one per node so `comfy.graph.node()` works between dispatches.
   */
  _nodeSnapshot(node, { includeResolvedSources = true } = {}) {
    if (!node) return undefined
    const base = node.snapshot() || {}
    const widgets = []
    try {
      for (const w of node.widgets.all()) {
        let options
        try {
          options = widgetOptionsData(
            this._sanitizeReturn(w.getOptions?.()))
        } catch { /* exotic host-only options do not cross */ }
        widgets.push({
          name: w.name,
          widgetType: w.widgetType,
          label: this._sanitizeReturn(w.getLabel?.()),
          value: this._sanitizeReturn(w.getValue()),
          hidden: !!w.isHidden?.(),
          disabled: !!w.isDisabled?.(),
          serialized: w.isSerialized?.() !== false,
          height: this._sanitizeReturn(w.getHeight?.()),
          ...(options === undefined ? {} : { options }),
        })
      }
    } catch { /* a node with no widget collection stays widgetless */ }
    let outputImages = []
    let displayedImageIndex
    try {
      const values = node.getOutputImages?.()
      if (Array.isArray(values)) {
        outputImages = values.slice(0, 256).filter(
          (value) => typeof value === 'string' && value.length <= 4096)
      }
      const selected = node.getDisplayedImageIndex?.()
      if (Number.isSafeInteger(selected) && selected >= 0 &&
          selected < outputImages.length) {
        displayedImageIndex = selected
      }
    } catch { /* nodes without media stay empty */ }
    const slots = (collection, withLinks) => {
      const out = []
      try {
        for (const [index, s] of collection.all().entries()) {
          const snapshot = s.snapshot?.() || {}
          const slot = {
            ...this._sanitizeReturn(snapshot),
            id: String(s.id ?? snapshot.id ?? `${withLinks}:${index}`),
            index,
            name: s.name,
            type: String(s.type ?? '*'),
            label: s.label,
          }
          if (withLinks === 'inputs') {
            // What a guest-side resolver needs of `self.inputs`: whether the
            // slot is fed, by whom, and with what arriving type.
            const source = s.source?.()
            slot.connected = !!source || !!s.isConnected
            slot.connectedType = s.connectedType
            slot.isWidgetInput = !!s.isWidgetInput
            slot.widgetConfig = this._sanitizeReturn(s.widgetConfig?.())
            if (includeResolvedSources) {
              slot.resolvedSource = this._sanitizeReturn(s.resolvedSource?.())
            }
            if (source) {
              slot.sourceNodeId = String(source.nodeId)
              slot.sourceOutput = source.outputIndex
            }
            slot.link = this._sanitizeReturn(s.link?.())
          }
          if (withLinks === 'outputs') {
            slot.connected = !!s.isConnected
            slot.links = this._sanitizeReturn(s.links?.() || [])
            slot.targets = (slot.links || []).map((l) => ({
              nodeId: String(l.targetNodeId ?? ''),
              inputIndex: l.targetIndex,
            }))
          }
          out.push(slot)
        }
      } catch { /* slotless */ }
      return out
    }
    return {
      ...base,
      id: String(node.id),
      graphId: node.graphId,
      type: node.type,
      properties: this._sanitizeReturn(node.getProperties?.() ?? {}),
      widgets,
      serializingWidgets: !!node.isSerializingWidgets?.(),
      outputImages,
      displayedImageIndex,
      inputs: slots(node.inputs, 'inputs'),
      outputs: slots(node.outputs, 'outputs'),
    }
  }

  /**
   * What was true of the user's gesture when a dispatch left the host. The
   * pointer and the selection are read synchronously by pack closures
   * (`add(type, { position: pointerPosition() })`, "act on selection" menu
   * items), and a value captured at gesture time is exactly what those
   * closures mean — fresher than any poll the guest could make.
   */
  _gestureCtx() {
    try {
      const g = this.comfy.graph
      return {
        pointer: g.pointerPosition(),
        selection: g.selection().map((n) => String(n.id)),
      }
    } catch {
      return { pointer: undefined, selection: [] }
    }
  }

  /**
   * Node mutations a guest may perform, by name. A closed table rather than
   * path resolution: everything here names one intended operation on one
   * node the guest could already see.
   */
  _nodeOp(msg) {
    const node = this._scopedNode(msg)
    if (!node) return [false, null, `no such node: ${msg.nodeId}`]
    const a = msg.args || []
    const slotRef = (value) => Number.isInteger(value)
      ? { index: value } : value
    const OPS = {
      'setTitle': () => node.setTitle(a[0]),
      'setPosition': () => node.setPosition(a[0]),
      'setSize': () => node.setSize(a[0]),
      'setColor': () => node.setColor(a[0]),
      'setBgColor': () => node.setBgColor(a[0]),
      'setMode': () => node.setMode(a[0]),
      'setCollapsed': () => node.setCollapsed(a[0]),
      'setPinned': () => node.setPinned(a[0]),
      'setResizable': () => node.setResizable(a[0]),
      'setProperty': () => node.setProperty(a[0], a[1]),
      'setSizeConstraints': () => node.setSizeConstraints(a[0]),
      'setSerializeWidgets': () => node.setSerializeWidgets(a[0]),
      'inputs.modify': () => {
        const inp = node.inputs.get(slotRef(a[0]))
        if (!inp) throw new Error(`no input ${a[0]} on ${msg.nodeId}`)
        inp.modify(a[1])
      },
      'outputs.modify': () => {
        const out = node.outputs.get(slotRef(a[0]))
        if (!out) throw new Error(`no output ${a[0]} on ${msg.nodeId}`)
        out.modify(a[1])
      },
      'inputs.add': () => { node.inputs.add(a[0], a[1], a[2]) },
      'outputs.add': () => { node.outputs.add(a[0], a[1], a[2]) },
      'inputs.remove': () => { node.inputs.remove(slotRef(a[0])) },
      'outputs.remove': () => { node.outputs.remove(slotRef(a[0])) },
      'inputs.reorder': () => { node.inputs.reorder(a[0]) },
      'outputs.reorder': () => { node.outputs.reorder(a[0]) },
      'outputs.disconnect': () => {
        const out = node.outputs.get(slotRef(a[0]))
        if (!out) throw new Error(`no output ${a[0]} on ${msg.nodeId}`)
        out.disconnect(a[1] != null ? String(a[1]) : undefined)
      },
      'outputs.moveLinksTo': () => {
        const out = node.outputs.get(slotRef(a[0]))
        if (!out) throw new Error(`no output ${a[0]} on ${msg.nodeId}`)
        out.moveLinksTo(slotRef(a[1]))
      },
      'remove': () => node.remove(),
      'widgets.setValue': () => {
        const w = node.widgets.get(a[0])
        if (!w) throw new Error(`no widget '${a[0]}' on ${msg.nodeId}`)
        w.setValue(a[1])
      },
      'widgets.setHidden': () => {
        const w = node.widgets.get(a[0])
        if (!w) throw new Error(`no widget '${a[0]}' on ${msg.nodeId}`)
        w.setHidden(a[1])
      },
      'widgets.setDisabled': () => {
        const w = node.widgets.get(a[0])
        if (!w) throw new Error(`no widget '${a[0]}' on ${msg.nodeId}`)
        w.setDisabled(a[1])
      },
      'widgets.setOption': () => {
        const w = node.widgets.get(a[0])
        if (!w) throw new Error(`no widget '${a[0]}' on ${msg.nodeId}`)
        w.setOption(widgetOptionKey(a[1]), widgetOptionValueData(a[2]))
      },
      'widgets.setLabel': () => {
        const w = node.widgets.get(a[0])
        if (!w) throw new Error(`no widget '${a[0]}' on ${msg.nodeId}`)
        if (typeof a[1] !== 'string' || a[1].length > 1024 || /\0/.test(a[1])) {
          throw new TypeError('widget label must be bounded text')
        }
        w.setLabel(a[1])
      },
      'widgets.add': () => { node.widgets.add(a[0]) },
      'widgets.remove': () => { node.widgets.remove(a[0]) },
      'widgets.reorder': () => { node.widgets.reorder(a[0]) },
      'widgets.move': () => { node.widgets.move(a[0], a[1]) },
      'outputs.connectTo': () => {
        const out = node.outputs.get(slotRef(a[0]))
        if (!out) throw new Error(`no output ${a[0]} on ${msg.nodeId}`)
        out.connectTo(String(a[1]), a[2])
      },
      'inputs.disconnect': () => {
        const inp = node.inputs.get(slotRef(a[0]))
        if (!inp) throw new Error(`no input ${a[0]} on ${msg.nodeId}`)
        inp.disconnect()
      },
    }
    const op = Object.hasOwn(OPS, msg.op) ? OPS[msg.op] : undefined
    if (!op) return [false, null, `node op '${msg.op}' not permitted`]
    op()
    return [true, this._nodeSnapshot(node)]
  }

  _graphOp(pack, msg) {
    const g = this.comfy.graph
    const a = msg.args || []
    if (msg.op === 'add') {
      const node = g.add(a[0], a[1])
      return [true, this._nodeSnapshot(node)]
    }
    if (msg.op === 'select') {
      const handles = (a[0] || [])
        .map((id) => g.node(String(id)))
        .filter(Boolean)
      g.select(handles, a[1])
      return [true, null]
    }
    if (msg.op === 'centerOn') {
      const node = g.node(String(a[0]))
      if (node) g.centerOn(node)
      return [true, null]
    }
    if (msg.op === 'remove') return [true, g.remove(String(a[0]))]
    if (msg.op === 'summary') {
      return [true, g.nodes().map((n) => this._nodeSnapshot(n))]
    }
    return [false, null, `graph op '${msg.op}' not permitted`]
  }

  /**
   * Event subscriptions. Paths are allowlisted by shape — a dotted chain of
   * plain properties ending in a listener-taking member — and every listener
   * argument is flattened before it crosses: a live handle becomes identity.
   */
  _subscribe(pack, msg) {
    const ALLOWED = new Set([
      'on', 'onWorkflowLoaded', 'onReady', 'onNodeChanged', 'onNodeDragEnd',
      'onNodeMoved', 'onViewportChanged', 'onPreview',
      'onExecutingNodeChanged',
      'backend.on', 'queue.onBeforeRun', 'queue.onAfterRun', 'queue.onRejected',
      'settings.onChange',
    ])
    if (!ALLOWED.has(msg.path)) {
      return [false, null, `subscription '${msg.path}' not permitted`]
    }
    let target = this.comfy
    const parts = msg.path.split('.')
    for (const p of parts.slice(0, -1)) target = target[p]
    const register = target[parts.at(-1)].bind(target)
    const flatten = (v) => {
      if (msg.path === 'onExecutingNodeChanged') {
        return this._nodeSnapshot(v)
      }
      return v && typeof v === 'object' && typeof v.id !== 'undefined' && v.type
        ? { id: String(v.id), type: v.type }
        : this._sanitizeReturn(v)
    }
    const listener = (...eventArgs) => {
      if (msg.path === 'backend.on' &&
          msg.args?.[0] === 'secure-node-interaction') {
        const detail = eventArgs[0]
        if (!detail || typeof detail !== 'object' || detail.pack !== pack) return
        const routedDetail = { ...detail }
        delete routedDetail.pack
        eventArgs = [routedDetail, ...eventArgs.slice(1)]
      }
      this._host.send(pack, {
        t: 'event', subId: msg.subId, args: eventArgs.map(flatten),
      })
    }
    // Most members take the listener last (`on(event, fn)`); onNodeChanged
    // takes it first (`onNodeChanged(fn, options?)`).
    const unsub = msg.path === 'onNodeChanged'
      ? register(listener, ...(msg.args || []))
      : register(...(msg.args || []), listener)
    this._subs ??= new Map()
    this._subs.set(`${pack}:${msg.subId}`, unsub)
    return [true, null]
  }

  _unsubscribe(pack, msg) {
    const key = `${pack}:${msg.subId}`
    const unsub = this._subs?.get(key)
    if (typeof unsub === 'function') unsub()
    this._subs?.delete(key)
    return [true, null]
  }

  /**
   * Keeps every guest's graph replica current: an epoch push (full node
   * summaries, stamped with the document id) whenever a workflow finishes
   * loading, and incremental node add/remove pushes between epochs. The
   * document id is what lets a guest DISCARD rather than patch — a swap must
   * not leave one pack's cache on the old document while another moved on.
   */
  _installGraphFeed() {
    const pushEpoch = () => {
      const payload = {
        t: 'epoch',
        documentId: this.comfy.workflow.documentId(),
        nodes: this.comfy.graph.nodes().map((n) => this._nodeSnapshot(n)),
      }
      this._host.sendAll(payload)
    }
    this.comfy.onWorkflowLoaded(() => pushEpoch())
    this.comfy.defs.extend(() => true, (b) => {
      b.onCreated((node) => {
        this._host.sendAll({ t: 'nodeAdded', node: this._nodeSnapshot(node) })
      })
      b.onRemoved((node) => {
        this._host.sendAll({ t: 'nodeRemoved', nodeId: String(node.id) })
      })
    })
  }

  _elementOp(pack, msg) {
    const el = this._elements.get(`${pack}:${msg.name}`)
    if (!el) return [false, null, 'unknown element']
    const policy = ELEMENT_POLICY[el.tagName.toLowerCase()]
    if (!policy) return [false, null, `no policy for <${el.tagName.toLowerCase()}>`]
    if (msg.op === 'invoke') {
      if (!policy.methods.includes(msg.method))
        return [false, null, `method '${msg.method}' not permitted`]
      const r = el[msg.method](...(msg.args || []))
      if (r && typeof r.then === 'function') r.catch(() => {})
      return [true, null]
    }
    if (msg.op === 'get') {
      if (!policy.get.includes(msg.prop))
        return [false, null, `property '${msg.prop}' not permitted`]
      return [true, el[msg.prop]]
    }
    if (msg.op === 'set') {
      if (!policy.set.includes(msg.prop))
        return [false, null, `property '${msg.prop}' not permitted`]
      el[msg.prop] = msg.value
      return [true, null]
    }
    if (msg.op === 'listen') {
      if (!policy.events.includes(msg.event))
        return [false, null, `event '${msg.event}' not permitted`]
      el.addEventListener(msg.event, () => {
        this._host.send(pack, { t: 'elemEvent', name: msg.name, event: msg.event,
          detail: { currentTime: el.currentTime, duration: el.duration,
                    value: el.value } })
      })
      return [true, null]
    }
    return [false, null, 'unknown element op']
  }

  /**
   * Register the pack's recorded `defs.extend` as a real extension.
   *
   * The pack's builder callback already ran in the worker; what arrives here is
   * data. We re-emit it against the real builder, and every lifecycle hook the
   * pack declared becomes a message back to the worker, where its actual
   * closure runs.
   */
  _applyExtend(pack, { regId, selector, hooks = [], declared = [], widgets = [],
                       menuItems = [], hasSerialize = false,
                       hasPromptSerialize = false }) {
    this.comfy.defs.extend(selector, (b) => {
      for (const [method, value] of declared) {
        if (typeof b[method] === 'function') b[method](value)
      }
      for (const w of widgets) {
        if (typeof b.addWidget === 'function') b.addWidget(w)
      }
      const buildMenu = (item) => {
        const out = { label: item.label }
        if (item.order !== undefined) out.order = item.order
        if (item.hasWhen) {
          // Read synchronously at menu-open from the guest's materialized
          // answer. Unknown means the guest has not evaluated this node yet;
          // SHOW it rather than hide, because a spurious item is visible and
          // recoverable while a silently missing one is the failure mode this
          // whole design exists to avoid — and say so once.
          out.when = (node) => {
            const key = `${pack}:${regId}:${item.menuId}:${node.id}`
            const known = this._menuView?.get(key)
            if (known === undefined) {
              this._menuMisses ??= new Set()
              if (!this._menuMisses.has(key)) {
                this._menuMisses.add(key)
                console.warn(
                  `[secure-nodes] '${item.label}' visibility not yet computed ` +
                  `for node ${node.id}; showing it`)
              }
              return true
            }
            return known
          }
        }
        if (item.items) {
          out.items = item.items.map(buildMenu)
        } else if (item.hasDynamicItems) {
          out.items = (node) => {
            const key = `${pack}:${regId}:${item.menuId}:${node.id}`
            const current = this._menuDynamicView?.get(key)
            return Array.isArray(current) ? current.map(buildMenu) : []
          }
        } else {
          out.run = (node) => {
            this._host.send(pack, {
              t: 'menu',
              regId,
              menuId: item.menuId,
              node: { id: String(node.id), type: node.type },
              snapshot: this._nodeSnapshot(node),
              ctx: this._gestureCtx(),
            })
          }
        }
        return out
      }
      for (const item of menuItems) {
        if (typeof b.addMenuItem !== 'function') continue
        b.addMenuItem(buildMenu(item))
      }
      if (hasSerialize && typeof b.onSerialize === 'function') {
        // The pack's blob, read synchronously from the guest's materialized
        // view. The guest recomputes after every dispatch that could have
        // changed its state, so the value here is at most one dispatch old —
        // and a dispatch is exactly what a state change requires.
        b.onSerialize((node) => {
          const value = this._serializeView?.get(
            `${pack}:${regId}:${String(node.id)}`)
          return value ?? {}
        })
      }
      if (hasPromptSerialize && typeof b.onPromptSerialize === 'function') {
        b.onPromptSerialize(async (node) => {
          await this._refreshReplica(pack, node)
          return this._askGuest(pack, {
            t: 'promptSerialize', regId, nodeId: String(node.id),
          })
        })
      }
      for (const hook of hooks) {
        if (typeof b[hook] !== 'function') continue
        b[hook]((node, arg) => {
          // Node handles hold live authority and must never cross. The guest
          // rebuilds a handle over the SNAPSHOT — state as data, true at
          // dispatch — and mutations come back as explicit nodeop messages
          // through the same policy table.
          this._host.send(pack, {
            t: 'hook',
            regId,
            hook,
            node: { id: String(node.id), type: node.type },
            snapshot: this._nodeSnapshot(node),
            ctx: this._gestureCtx(),
            arg: this._sanitizeReturn(arg),
          })
        })
      }
    })
  }

  /**
   * A pack-owned node type. Data registers directly; the definition's
   * functions stayed in the worker: lifecycle hooks ride the hook channel,
   * and resolve/supply become ASYNC trampolines — the published resolution
   * contract now awaits them on the prompt path — that refresh the guest's
   * replica and ask it to answer from its own copy of the pack's logic.
   */
  _scopedNode(msg) {
    const graph = this.comfy.graph
    if (msg.graphId == null) return graph.node(String(msg.nodeId))
    const scopes = [graph, graph.root?.(), ...(graph.subgraphs?.() || [])]
    return scopes.find((scope) => scope && String(scope.id) === String(msg.graphId))
      ?.node(String(msg.nodeId))
  }

  _removeNodeCanvas(key) {
    const rec = this._nodeCanvases.get(key)
    if (!rec) return
    this._nodeCanvases.delete(key)
    rec.bitmap?.close()
    rec.bitmap = null
    rec.surface?.remove()
    this._host.send(rec.pack, { t: 'nodecanvasremoved', nodeId: rec.nodeId,
      graphId: rec.graphId, surfaceId: rec.surfaceId })
  }

  _checkNodeCanvasBudget(pack, replacingKey, bounds) {
    let count = 1
    let pixels = Math.ceil(bounds.width) * Math.ceil(bounds.height)
    for (const [key, rec] of this._nodeCanvases) {
      if (rec.pack !== pack || key === replacingKey) continue
      count++
      pixels += Math.ceil(rec.bounds.width) * Math.ceil(rec.bounds.height)
    }
    if (count > 256 || pixels > 67_108_864) {
      throw new RangeError('pack node canvas count or pixel budget exceeded')
    }
  }

  _applyDefine(pack, { regId, def, hooks = [], hasSerialize = false,
                       hasPromptSerialize = false, has = {} }) {
    const definition = { ...def }
    for (const hook of hooks) {
      definition[hook] = (node, arg) => {
        this._host.send(pack, {
          t: 'hook', regId, hook,
          node: { id: String(node.id), type: node.type },
          snapshot: this._nodeSnapshot(node),
          ctx: this._gestureCtx(),
          arg: this._sanitizeReturn(arg),
        })
      }
    }
    if (hasSerialize) {
      definition.onSerialize = (node) => this._serializeView?.get(
        `${pack}:${regId}:${String(node.id)}`) ?? {}
    }
    if (hasPromptSerialize) {
      definition.onPromptSerialize = async (node) => {
        await this._refreshReplica(pack, node)
        return this._askGuest(pack, {
          t: 'promptSerialize', regId, nodeId: String(node.id),
        })
      }
    }
    if (has.resolve) {
      definition.resolve = async (view) => {
        await this._refreshReplica(pack)
        return this._askGuest(pack, {
          t: 'resolve', defType: def.type, nodeId: view.self.id,
        })
      }
    }
    if (has.supply) {
      definition.supply = async (view) => {
        await this._refreshReplica(pack)
        return this._askGuest(pack, {
          t: 'supply', defType: def.type, nodeId: view.self.id,
          unconnected: this._sanitizeReturn(view.unconnectedInputs()),
        })
      }
    }
    const removed = definition.onRemoved
    definition.onRemoved = (node) => {
      this._removeNodeCanvas(JSON.stringify([pack, String(node.graphId), String(node.id)]))
      removed?.(node)
    }
    const dispose = this.comfy.defs.define(definition)
    this._definitionOwners.set(def.type, pack)
    this._definitionDisposers.add(dispose)
  }

  /** Host→guest request; the guest replies on the 'answer' channel. */
  _askGuest(pack, payload) {
    this._asks ??= new Map()
    this._askSeq = (this._askSeq ?? 0) + 1
    const reqId = `q${this._askSeq}`
    return new Promise((resolve, reject) => {
      this._asks.set(reqId, { resolve, reject })
      this._host.send(pack, { ...payload, reqId })
      setTimeout(() => {
        if (!this._asks.has(reqId)) return
        this._asks.delete(reqId)
        reject(new Error(`guest '${pack}' did not answer ${payload.t}`))
      }, 5000)
    })
  }

  /**
   * Pushes current node snapshots to one pack, throttled to once per tick —
   * a prompt build asks one resolver per relay node, and each ask must see
   * link and widget state as of THIS build, not the last epoch.
   */
  _refreshReplica(pack, currentNode) {
    this._refreshing ??= new Map()
    let pending = this._refreshing.get(pack)
    if (!pending) {
      pending = Promise.resolve().then(() => {
        this._refreshing.delete(pack)
        const nodes = this.comfy.graph.nodes().map((n) => this._nodeSnapshot(
          n, { includeResolvedSources: false }))
        // A prompt hook receives the authoritative live handle for the node
        // being serialized. Prefer that snapshot over a graph-enumeration
        // replica, whose widget cache may trail a just-completed edit by one
        // event turn.
        if (currentNode) {
          const current = this._nodeSnapshot(
            currentNode, { includeResolvedSources: false })
          const index = nodes.findIndex(
            (node) => String(node.id) === String(current.id))
          if (index >= 0) nodes[index] = current
          else nodes.push(current)
        }
        this._host.send(pack, {
          t: 'epoch',
          documentId: this.comfy.workflow.documentId(),
          nodes,
        })
      })
      this._refreshing.set(pack, pending)
    }
    return pending
  }

  /**
   * The def catalogue the guest matches selectors against and reads `b.def`
   * from — fetched once, shared by every pack this host spawns.
   *
   * The frontend registers node definitions AFTER extensions load, so at pack
   * load time `comfy.defs.all()` is empty and cannot seed this. The backend
   * already knows: `/object_info` is the source the frontend itself registers
   * from. Project it onto the public NodeDef shape. Small enum choices remain
   * useful definition data; unbounded model/file catalogues stay behind their
   * dedicated catalogue APIs instead of bloating every worker bootstrap.
   */
  async _ensureDefs() {
    this._defs ??= (async () => {
      try {
        const res = await this.comfy.backend.fetch('/object_info')
        if (!res.ok) throw new Error(`object_info: HTTP ${res.status}`)
        const raw = await res.json()
        const slot = ([name, spec]) => {
          const declared = spec?.[0]
          const options = spec?.[1]
          const out = {
            name,
            type: Array.isArray(declared) ? 'COMBO' : String(declared ?? '*'),
            options: options && typeof options === 'object'
              ? this._sanitizeReturn(options)
              : {},
          }
          // Small enum vocabularies are useful definition data. Model/file
          // catalogues can contain tens of thousands of names, so those stay
          // behind their dedicated catalogue APIs instead of multiplying into
          // every pack worker's bootstrap.
          if (Array.isArray(declared) && declared.length <= 256 &&
              declared.every((value) =>
                typeof value === 'string' || typeof value === 'number')) {
            const bytes = new TextEncoder().encode(JSON.stringify(declared)).length
            if (bytes <= 64 * 1024) out.values = declared.slice()
          }
          return out
        }
        return Object.entries(raw).map(([name, def]) => ({
          type: name,
          title: def.display_name || name,
          category: def.category || '',
          description: def.description || '',
          source: def.python_module || undefined,
          isOutputNode: !!def.output_node,
          hidden: this._sanitizeReturn(def.input?.hidden || {}),
          inputs: [
            ...Object.entries(def.input?.required || {}).map(slot),
            ...Object.entries(def.input?.optional || {}).map(slot),
          ],
          outputs: (def.output || []).map((type, i) => ({
            name: def.output_name?.[i] ?? String(type),
            type: Array.isArray(type) ? 'COMBO' : String(type),
            ...(typeof def.output_tooltips?.[i] === 'string'
              ? { tooltip: def.output_tooltips[i] }
              : {}),
          })),
        }))
      } catch (error) {
        // A guest without defs falls back to selector-shipping registration,
        // which works for every builder that never reads `b.def`. Say which
        // packs got the degraded world rather than letting them find out.
        console.warn('[secure-nodes] def catalogue unavailable:', error)
        return []
      }
    })()
    return this._defs
  }

  _finishDialog(pack, rec) {
    if (rec.closed) return
    rec.closed = true
    if (rec.keyListener) {
      for (const target of rec.keyTargets) {
        target.removeEventListener('keydown', rec.keyListener)
      }
    }
    rec.ui?.destroy()
    this._uiByKey.delete(rec.uiKey)
    this._dialogs.delete(`${pack}:${rec.dialogId}`)
    const logicalKey = `${pack}:${rec.key}`
    if (this._dialogByKey.get(logicalKey) === rec) {
      this._dialogByKey.delete(logicalKey)
    }
    this._host.send(pack, { t: 'dialogclosed', dialogId: rec.dialogId })
  }

  _openDialog(pack, value) {
    const data = dialogRegistrationData(value)
    const recordKey = `${pack}:${data.dialogId}`
    if (this._dialogs.has(recordKey)) {
      throw new Error(`duplicate sandbox dialog '${data.dialogId}'`)
    }
    const logicalKey = `${pack}:${data.key}`
    const previous = this._dialogByKey.get(logicalKey)
    if (previous) {
      try { previous.handle?.close() } finally {
        this._finishDialog(pack, previous)
      }
    }
    const rec = {
      ...data,
      closed: false,
      handle: null,
      ui: null,
      markup: null,
      uiKey: `${pack}:dialog:${data.dialogId}`,
      keyTargets: [],
      keyListener: null,
    }
    this._dialogs.set(recordKey, rec)
    this._dialogByKey.set(logicalKey, rec)
    try {
      const handle = this.comfy.ui.showDialog({
        key: `extension-${pack}:${data.key}`,
        ...(data.title === undefined ? {} : { title: data.title }),
        render: (container) => {
          if (rec.closed) return
          rec.ui = this.attachNodeUI(
            pack, rec.uiKey, `dialog:${data.dialogId}`, container, null)
          if (rec.markup !== null) rec.ui.update(rec.markup)
          if (data.hasKeyDown) {
            const seen = new WeakSet()
            rec.keyListener = (event) => {
              if (rec.closed || seen.has(event)) return
              seen.add(event)
              const detail = dialogKeyEventData(event)
              if (!detail.editableTarget) {
                event.preventDefault()
                event.stopPropagation()
              }
              this._host.send(pack, {
                t: 'dialogkey', dialogId: data.dialogId,
                detail,
              })
            }
            rec.keyTargets = [container, rec.ui.__shadow]
            for (const target of rec.keyTargets) {
              target.addEventListener('keydown', rec.keyListener)
            }
            if (!container.hasAttribute('tabindex')) container.tabIndex = -1
            queueMicrotask(() => {
              if (!rec.closed && !container.contains(document.activeElement)) {
                container.focus({ preventScroll: true })
              }
            })
          }
        },
        destroy: () => this._finishDialog(pack, rec),
      })
      if (!handle || typeof handle.close !== 'function') {
        throw new Error('dialog host returned an invalid handle')
      }
      rec.handle = handle
      return rec
    } catch (error) {
      this._finishDialog(pack, rec)
      throw error
    }
  }

  /**
   * Create a UI container inside a node, on the pack's behalf, using the real
   * `widgets.mount`. Called lazily on a pack's first render to a key, so the
   * pack never has to name a moment at which the node body exists.
   */
  _mountNodeUI(pack, hostKey, packKey, nodeId, name) {
    const node = this.comfy.graph.node(String(nodeId))
    if (!node) throw new Error(`no such node: ${nodeId}`)
    let ui = null
    node.widgets.mount({
      name,
      // Decoration, not state: this panel reports what happened, so it has no
      // business in `widgets_values` or in the next prompt.
      serialize: false,
      hideOnZoom: false,
      render: (container) => {
        ui = this.attachNodeUI(pack, hostKey, packKey, container, node)
      },
    })
    if (!ui) throw new Error('widgets.mount did not call render()')
    return ui
  }

  /** Wrap a container in the sanitising renderer and route its events back. */
  attachNodeUI(pack, hostKey, packKey, container, node) {
    const ui = mountPackUI(
      container,
      (action, detail) =>
        this._host.send(pack, { t: 'uiEvent', key: packKey, action, detail }),
      // The pack's panel grows when its content does (a row appears once the
      // node has run), and `widgets.mount` documents "omit height to size to
      // content" but reserves a flat 50px instead. The renderer measured the
      // content for us; re-declaring autoHeight re-runs the node's fit.
      () => {
        try {
          node?.setSizeConstraints?.({ autoHeight: true })
        } catch {
          // Sizing is cosmetic: never let it break the pack's UI.
        }
      })
    // A mounted tree may contain guest-drawn <canvas> stubs. Each update
    // replaces the shadow's children — blank canvases — so the cached
    // bitmaps repaint after every render and whenever fresh pixels arrive.
    ui.paintBitmaps = () => {
      if (!ui.bitmaps) return
      for (const [stubId, bitmap] of ui.bitmaps) {
        const canvas = ui.__shadow.querySelector(
          `canvas[data-key="${stubId}"]`)
        canvas?.getContext('2d')?.drawImage(
          bitmap, 0, 0, canvas.width, canvas.height)
      }
    }
    // Materialized measurement: the pack has no layout, so the host measures
    // every keyed element after each render and ships the rects. The corpus
    // idiom is `(e.clientX - rect.left) * (canvas.width / rect.width)` inside
    // a pointer handler — a synchronous read that cannot cross a boundary, so
    // it reads a value that is at most one frame old instead.
    const reportRects = () => {
      const rects = []
      for (const el of ui.__shadow.querySelectorAll('[data-key]')) {
        const r = el.getBoundingClientRect()
        rects.push([el.getAttribute('data-key'), {
          x: r.x, y: r.y, top: r.top, left: r.left, right: r.right,
          bottom: r.bottom, width: r.width, height: r.height,
        }])
      }
      if (rects.length) {
        this._host.send(pack, { t: 'uirects', key: packKey, rects })
      }
    }
    const update = ui.update.bind(ui)
    ui.update = (markup) => {
      update(markup)
      ui.paintBitmaps()
      // After layout, not during it — a rect read in the same frame as the
      // DOM write reports the pre-layout box.
      requestAnimationFrame(reportRects)
    }
    ui.reportRects = reportRects
    this._uiByKey.set(hostKey, ui)
    return ui
  }

  registerElement(pack, name, el) { this._elements.set(`${pack}:${name}`, el) }

  get packCount() { return this._host.packCount }

  /**
   * Diagnostics for tests. The pack's shadow roots are CLOSED, so a test cannot
   * reach them from the page — but the host created them and legitimately holds
   * the references. This exposes a read-only snapshot, and no new authority: a
   * page script could already call every one of these APIs directly.
   */
  inspect() {
    const panels = []
    for (const [key, ui] of this._uiByKey) {
      const sr = ui.__shadow
      if (!sr) continue
      const testids = {}
      for (const el of sr.querySelectorAll('[data-testid]')) {
        testids[el.getAttribute('data-testid')] = el.textContent
      }
      panels.push({
        key,
        testids,
        size: ui.__size?.() ?? null,
        elementCount: sr.querySelectorAll('*').length,
        hasStyle: !!sr.querySelector('style'),
        // must always be 0: proof the sanitiser dropped script
        scriptCount: sr.querySelectorAll('script').length,
        text: sr.textContent.replace(/\s+/g, ' ').trim().slice(0, 200),
      })
    }
    return { packCount: this.packCount, panels }
  }

  destroy() {
    for (const key of [...this._nodeCanvases.keys()]) this._removeNodeCanvas(key)
    for (const dispose of this._definitionDisposers) dispose?.()
    this._definitionDisposers.clear()
    this._definitionOwners.clear()
    this._importers.clear()
    this._comboPreviews.clear()
    this._hideComboOptionPreview()
    this._provideComboOptionPreviewSource?.(undefined)
    for (const remove of this._localizationCatalogs.values()) {
      try { remove() } catch { /* teardown is best-effort */ }
    }
    this._localizationCatalogs.clear()
    this._packCapabilities.clear()
    this._packRouteBase.clear()
    for (const handle of this._actionButtons.values()) {
      try { handle.remove() } catch { /* teardown is best-effort */ }
    }
    this._actionButtons.clear()
    for (const handle of this._topBarBadges.values()) {
      try { handle.remove() } catch { /* teardown is best-effort */ }
    }
    this._topBarBadges.clear()
    for (const [key, rec] of [...this._dialogs]) {
      const pack = key.slice(0, key.lastIndexOf(':'))
      try { rec.handle?.close() } catch {}
      this._finishDialog(pack, rec)
    }
    this._dialogs.clear()
    this._dialogByKey.clear()
    this._host.destroy()
  }
}

/**
 * Install into the frontend. Returns the host so a caller/test can inspect it.
 * `provideExtensionHost` is the frontend's generic seam.
 */
export async function install({ provideExtensionHost, comfy,
                                bootstrapUrl = DEFAULT_GUEST_BOOTSTRAP_URL,
                                match, capabilities, workflowSnapshot,
                                filePicker, fileDownloader,
                                provideComboOptionPreviewSource,
                                registerLocalizationCatalog } = {}) {
  const host = new SecureExtensionHost({
    comfy: comfy ?? globalThis.comfy, bootstrapUrl, match, capabilities,
    workflowSnapshot, filePicker, fileDownloader,
    provideComboOptionPreviewSource,
    registerLocalizationCatalog,
  })
  provideExtensionHost(host)
  return host
}
