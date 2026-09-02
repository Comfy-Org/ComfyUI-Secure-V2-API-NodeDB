import { comfy } from '/comfy/api/v2.js';

const VARIANT = 'vslinx-segment-prompts-v1';
const COLORS = ['#4da3ff', '#ff7847', '#5fd87a', '#e85fd8', '#ffd84d', '#5fe0e0'];
const remembered = new Map();
let active;

function previewUrl(ref) {
  if (!ref || typeof ref !== 'object') return '';
  const filename = String(ref.filename ?? '');
  if (!filename || filename.includes('\0')) return '';
  const query = new URLSearchParams({
    filename,
    subfolder: String(ref.subfolder ?? ''),
    type: String(ref.type ?? 'temp'),
  });
  return comfy.backend.url(`/view?${query}`);
}

async function respond(requestId, response) {
  const result = await comfy.backend.fetch('/secure-nodes/interactions/respond', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ request_id: String(requestId), response }),
  });
  return result.ok;
}

function closeActive() {
  active?.close();
  active = undefined;
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function show(detail) {
  const payload = detail?.payload;
  if (detail?.kind !== 'prompt-await' || payload?.variant !== VARIANT) return;
  const segments = Array.isArray(payload.segments) ? payload.segments.slice(0, 64) : [];
  if (!segments.length || typeof detail.request_id !== 'string') return;
  closeActive();

  let finished = false;
  let handle;
  const textareas = [];
  const finish = async (cancelled, prompts = []) => {
    if (finished) return;
    finished = true;
    await respond(detail.request_id, { cancelled, prompts });
    handle?.close();
    if (active === handle) active = undefined;
  };

  handle = comfy.ui.showDialog({
    key: `vslinx.interactiveDetailer.${detail.node_id}`,
    title: `Interactive Detailer — ${segments.length} segment${segments.length === 1 ? '' : 's'}`,
    render(container) {
      const doc = container.ownerDocument;
      style(container, { maxWidth: '860px', maxHeight: '82vh', overflow: 'auto' });

      const hint = doc.createElement('p');
      hint.textContent = 'Empty uses the base prompt. [SKIP] leaves that segment untouched.';
      hint.style.opacity = '0.72';
      container.append(hint);

      const overviewUrl = previewUrl(payload.overview?.preview);
      if (overviewUrl) {
        const canvas = style(doc.createElement('canvas'), {
          maxWidth: '100%', maxHeight: '34vh', borderRadius: '6px', cursor: 'pointer',
        });
        const image = doc.createElement('img');
        image.addEventListener('load', () => {
          canvas.width = image.naturalWidth;
          canvas.height = image.naturalHeight;
          const context = canvas.getContext('2d');
          context.drawImage(image, 0, 0);
          const scale = Number(payload.overview?.scale) || 1;
          for (const segment of segments) {
            const box = Array.isArray(segment.bbox) ? segment.bbox.map(Number) : [];
            if (box.length !== 4 || !box.every(Number.isFinite)) continue;
            const color = COLORS[(Number(segment.index) || 0) % COLORS.length];
            const [left, top, right, bottom] = box.map((value) => value * scale);
            context.strokeStyle = color;
            context.lineWidth = Math.max(2, canvas.width / 500);
            context.strokeRect(left, top, right - left, bottom - top);
            context.fillStyle = color;
            context.font = `bold ${Math.max(13, canvas.width / 45)}px sans-serif`;
            context.fillText(String((Number(segment.index) || 0) + 1), left + 4, top + 18);
          }
        });
        canvas.addEventListener('click', (event) => {
          const bounds = canvas.getBoundingClientRect();
          const x = (event.clientX - bounds.left) * canvas.width / Math.max(1, bounds.width);
          const y = (event.clientY - bounds.top) * canvas.height / Math.max(1, bounds.height);
          const scale = Number(payload.overview?.scale) || 1;
          for (let index = 0; index < segments.length; index += 1) {
            const box = Array.isArray(segments[index].bbox) ? segments[index].bbox.map(Number) : [];
            if (box.length !== 4) continue;
            if (x >= box[0] * scale && x <= box[2] * scale
                && y >= box[1] * scale && y <= box[3] * scale) {
              textareas[index]?.focus();
              break;
            }
          }
        });
        image.src = overviewUrl;
        container.append(canvas);
      }

      segments.forEach((segment, index) => {
        const row = style(doc.createElement('div'), {
          display: 'flex', gap: '12px', padding: '10px', margin: '8px 0',
          border: `1px solid ${COLORS[index % COLORS.length]}66`, borderRadius: '8px',
        });
        const thumbUrl = previewUrl(segment.preview);
        if (thumbUrl) {
          const thumb = style(doc.createElement('img'), {
            width: '96px', height: '96px', objectFit: 'cover', borderRadius: '6px',
          });
          thumb.src = thumbUrl;
          row.append(thumb);
        }
        const fields = style(doc.createElement('div'), {
          display: 'flex', flex: '1', flexDirection: 'column', gap: '5px',
        });
        const label = doc.createElement('label');
        const confidence = Number(segment.confidence);
        label.textContent = `#${index + 1} ${String(segment.label ?? 'segment')}`
          + (Number.isFinite(confidence) && confidence > 0 ? ` · ${(confidence * 100).toFixed(0)}%` : '');
        label.style.color = COLORS[index % COLORS.length];
        const textarea = style(doc.createElement('textarea'), {
          minHeight: '68px', width: '100%', resize: 'vertical', boxSizing: 'border-box',
        });
        const memoryKey = `${String(payload.node_id ?? detail.node_id)}:${index}`;
        textarea.value = remembered.get(memoryKey) ?? '';
        textarea.placeholder = 'positive prompt (empty = base prompt)';
        textarea.addEventListener('change', () => {
          const value = String(textarea.value ?? '');
          if (value.trim()) remembered.set(memoryKey, value);
          else remembered.delete(memoryKey);
        });
        textareas.push(textarea);
        fields.append(label, textarea);
        row.append(fields);
        container.append(row);
      });

      const controls = style(doc.createElement('div'), {
        display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px',
      });
      const cancel = doc.createElement('button');
      cancel.textContent = 'Cancel run';
      cancel.addEventListener('click', () => { void finish(true); });
      const base = doc.createElement('button');
      base.textContent = 'Base prompt for all';
      base.addEventListener('click', () => { void finish(false, segments.map(() => '')); });
      const confirm = doc.createElement('button');
      confirm.textContent = 'Detail with these prompts';
      confirm.addEventListener('click', () => {
        const prompts = textareas.map((textarea) => String(textarea.value ?? ''));
        prompts.forEach((value, index) => {
          const key = `${String(payload.node_id ?? detail.node_id)}:${index}`;
          if (value.trim()) remembered.set(key, value);
          else remembered.delete(key);
        });
        void finish(false, prompts);
      });
      controls.append(cancel, base, confirm);
      container.append(controls);
      textareas[0]?.focus();
    },
    destroy() { finished = true; },
  });
  active = handle;
}

comfy.backend.on('secure-node-interaction', show);
comfy.queue.onInterrupted(closeActive);
comfy.onExecutingNodeChanged((node) => { if (!node && active) closeActive(); });
