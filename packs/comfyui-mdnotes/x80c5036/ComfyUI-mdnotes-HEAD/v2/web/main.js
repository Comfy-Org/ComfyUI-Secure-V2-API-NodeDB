import { comfy } from '/comfy/api/v2.js';

const SAVE_ON_CLOSE = 'comfyui-mdnotes.savingOptions.saveOnClose';
const SIMILARITY = 'comfyui-mdnotes.markdownEditor.similarityThreshold';
const NOTE_STORE = 'mdnotes/notes.json';
const MAX_NOTE_BYTES = 512 * 1024;

comfy.settings.declare({ id: SAVE_ON_CLOSE,
  name: 'Save after closing the markdown editor?', type: 'boolean',
  defaultValue: false });
comfy.settings.declare({ id: SIMILARITY,
  name: 'Similarity threshold for searching markdown notes', type: 'slider',
  defaultValue: 0.5, attrs: { min: 0.1, max: 1, step: 0.1 } });

function notify(severity, detail) {
  comfy.commands.notify({ severity, summary: 'MDNotes', detail });
}

function modelFolders(type) {
  if (type === 'ckpt') return ['checkpoints'];
  if (type === 'lora') return ['loras'];
  if (type === 'unet') return ['unet', 'diffusion_models'];
  return [];
}

function normalizeModelName(value) {
  return String(value).replace(/\\/g, '/').replace(/^\/+/, '');
}

function notePath(folder, modelName) {
  const normalized = normalizeModelName(modelName);
  const slash = normalized.lastIndexOf('/');
  const parent = slash < 0 ? '' : normalized.slice(0, slash + 1);
  const filename = normalized.slice(slash + 1).replace(/\.[^.]+$/, '');
  return `${folder}/${parent}${filename}.md`;
}

async function readNotes() {
  try {
    const decoded = JSON.parse(await comfy.storage.get(NOTE_STORE) || '{}');
    if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded))
      return Object.create(null);
    const notes = Object.create(null);
    for (const [key, value] of Object.entries(decoded)) {
      if (typeof value === 'string' && key.length <= 4096 && !key.includes('\0'))
        notes[key] = value;
    }
    return notes;
  } catch (_error) { return Object.create(null); }
}

function similarity(a, b) {
  a = String(a).toLowerCase(); b = String(b).toLowerCase();
  if (a === b) return 1;
  const previous = new Array(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i += 1) {
    let diagonal = 0;
    for (let j = 1; j <= b.length; j += 1) {
      const old = previous[j];
      previous[j] = a[i - 1] === b[j - 1] ? diagonal + 1
        : Math.max(previous[j], previous[j - 1]);
      diagonal = old;
    }
  }
  return (2 * previous[b.length]) / Math.max(1, a.length + b.length);
}

function closestAuthoredNote(notes, suggested) {
  const directory = suggested.slice(0, suggested.lastIndexOf('/') + 1);
  const stem = suggested.slice(directory.length, -3);
  const candidates = Object.keys(notes).filter((key) =>
    key.startsWith(directory) && key.endsWith('.md'));
  let selected; let score = -1;
  for (const candidate of candidates) {
    const value = similarity(stem,
      candidate.slice(directory.length).replace(/\.md$/i, ''));
    if (value > score) { score = value; selected = candidate; }
  }
  const threshold = Number(comfy.settings.get(SIMILARITY) ?? 0.5);
  return selected && score >= threshold ? selected : undefined;
}

async function resolveModel(target) {
  if (!comfy.models)
    throw new Error('this host does not provide the secure model catalogue');
  const requested = normalizeModelName(target.path);
  for (const folder of modelFolders(target.type)) {
    const names = await comfy.models.list(folder);
    const modelName = names.find((name) =>
      normalizeModelName(name) === requested);
    if (modelName !== undefined) return { folder, modelName };
  }
  throw new Error('the selected model is no longer in the managed catalogue');
}

async function loadNote(target) {
  const { folder, modelName } = await resolveModel(target);
  const notes = await readNotes();
  const suggested = notePath(folder, modelName);
  const selected = closestAuthoredNote(notes, suggested);
  if (selected !== undefined)
    return { content: notes[selected], rel_file_path: selected,
      created: false, source: 'authored' };

  const sidecar = await comfy.models.readSidecar(folder, modelName, '.md');
  if (sidecar !== undefined)
    return { content: sidecar, rel_file_path: suggested,
      created: false, source: 'sidecar' };
  return { content: '', rel_file_path: suggested, created: true, source: 'new' };
}

async function saveNote(path, content) {
  if (new TextEncoder().encode(content).length > MAX_NOTE_BYTES)
    throw new Error('note exceeds 512 KiB');
  const notes = await readNotes(); notes[path] = content;
  await comfy.storage.set(NOTE_STORE, JSON.stringify(notes));
}

function targets(node) {
  const result = [];
  for (const widget of node.widgets.all()) {
    const name = String(widget.name || '').toLowerCase();
    const value = String(widget.getValue() ?? '');
    if (!value || value === 'None' || widget.isHidden()) continue;
    if (name.includes('ckpt'))
      result.push({ label: 'checkpoint', type: 'ckpt', path: value });
    else if (name.includes('unet') || name.includes('dfm'))
      result.push({ label: 'unet', type: 'unet', path: value });
    else if (name.includes('lora')) {
      const ordinal = result.filter((item) => item.type === 'lora').length + 1;
      result.push({ label: `lora ${ordinal}`, type: 'lora', path: value });
    }
  }
  return result;
}

function appendInline(doc, parent, text) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;
  let at = 0;
  for (const match of text.matchAll(pattern)) {
    parent.append(doc.createTextNode(text.slice(at, match.index)));
    const token = match[0];
    let element;
    if (token.startsWith('`')) {
      element = doc.createElement('code'); element.textContent = token.slice(1, -1);
    } else if (token.startsWith('**')) {
      element = doc.createElement('strong'); element.textContent = token.slice(2, -2);
    } else if (token.startsWith('*')) {
      element = doc.createElement('em'); element.textContent = token.slice(1, -1);
    } else {
      const parts = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(token);
      element = doc.createElement('a'); element.textContent = parts[1];
      element.href = parts[2]; element.target = '_blank';
      element.rel = 'noopener noreferrer';
    }
    parent.append(element); at = match.index + token.length;
  }
  parent.append(doc.createTextNode(text.slice(at)));
}

function renderMarkdown(doc, root, markdown) {
  root.replaceChildren();
  let code = null;
  for (const line of String(markdown).split(/\r?\n/)) {
    if (line.startsWith('```')) {
      if (code) { root.append(code); code = null; }
      else code = doc.createElement('pre');
      continue;
    }
    if (code) { code.textContent += `${line}\n`; continue; }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const element = heading ? doc.createElement(`h${heading[1].length}`)
      : bullet ? doc.createElement('li') : doc.createElement('p');
    appendInline(doc, element, heading ? heading[2] : bullet ? bullet[1] : line);
    root.append(element);
  }
  if (code) root.append(code);
}

function wrapSelection(textarea, before, after = before) {
  const start = textarea.selectionStart; const end = textarea.selectionEnd;
  textarea.setRangeText(`${before}${textarea.value.slice(start, end)}${after}`,
    start, end, 'select');
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  textarea.focus();
}

async function openEditor(target) {
  let note;
  try {
    note = await loadNote(target);
  } catch (error) { notify('error', `Could not open note: ${error}`); return; }
  if (note.created)
    notify('warning', 'Found no note; ready to create one.');
  else if (note.source === 'sidecar')
    notify('info', 'Loaded the model sidecar. Edits save to your private note.');

  let textarea; let dirty = false; let saving = false;
  const save = async () => {
    if (!dirty || saving) return true;
    saving = true;
    try {
      await saveNote(note.rel_file_path, textarea.value);
      dirty = false; notify('success', 'Note is saved!'); return true;
    } catch (error) { notify('error', `Could not save note: ${error}`); return false; }
    finally { saving = false; }
  };

  let handle;
  handle = comfy.ui.showDialog({
    key: `endericedragon.mdnotes.${target.type}.${target.path}`,
    title: `MDNotes — ${target.path}`,
    render(container) {
      const doc = container.ownerDocument;
      const shell = doc.createElement('div');
      shell.style.cssText = 'display:grid;gap:10px;min-width:min(76vw,900px)';
      const toolbar = doc.createElement('div');
      toolbar.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap';
      textarea = doc.createElement('textarea'); textarea.value = String(note.content || '');
      textarea.setAttribute('aria-label', 'Markdown note');
      textarea.style.cssText = 'box-sizing:border-box;width:100%;min-height:42vh;resize:vertical;font:14px/1.5 ui-monospace,monospace';
      const preview = doc.createElement('div');
      preview.style.cssText = 'max-height:32vh;overflow:auto;padding:8px;border:1px solid currentColor';
      const formats = [['Bold', '**', '**'], ['Italic', '*', '*'],
        ['Code', '`', '`'], ['Heading', '## ', ''], ['Link', '[', '](https://)']];
      for (const [label, before, after] of formats) {
        const button = doc.createElement('button'); button.textContent = label;
        button.setAttribute('type', 'button');
        button.setAttribute('aria-label', `Format as ${label.toLowerCase()}`);
        button.addEventListener('click', () => wrapSelection(textarea, before, after));
        toolbar.append(button);
      }
      const controls = doc.createElement('div');
      controls.style.cssText = 'display:flex;justify-content:flex-end;gap:8px';
      const cancel = doc.createElement('button'); cancel.textContent = 'Cancel';
      cancel.setAttribute('type', 'button');
      cancel.addEventListener('click', () => { handle.close(); });
      const okay = doc.createElement('button'); okay.textContent = 'Save';
      okay.setAttribute('type', 'button');
      okay.addEventListener('click', async () => {
        if (await save()) handle.close();
      });
      controls.append(cancel, okay); shell.append(toolbar, textarea, preview, controls);
      container.append(shell);
      const update = () => {
        dirty = textarea.value !== String(note.content || '');
        renderMarkdown(doc, preview, textarea.value);
      };
      textarea.addEventListener('input', update); update(); textarea.focus();
    },
    onKeyDown(event) {
      if (!event.repeat && (event.ctrlKey || event.metaKey)
          && event.key.toLowerCase() === 's')
        void save();
    },
    destroy() {
      if (dirty && comfy.settings.get(SAVE_ON_CLOSE) === true)
        void save();
    },
  });
}

comfy.defs.extend(/./, (builder) => {
  builder.addMenuItem({
    label: '✍️ Show model note',
    when: (node) => targets(node).length > 0,
    items: (node) => targets(node).map((target) => ({
      label: `Show note of ${target.label}`,
      run: () => { void openEditor(target); },
    })),
  });
});
