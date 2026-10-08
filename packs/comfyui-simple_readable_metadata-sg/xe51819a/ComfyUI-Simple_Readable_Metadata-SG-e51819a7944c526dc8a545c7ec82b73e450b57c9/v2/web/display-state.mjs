import { LIMITS, ProfileError } from './viewer-profile.mjs';
export function textLines(value) {
  if (!Array.isArray(value) || value.length > 1024 || value.some(line => typeof line !== 'string'))
    throw new ProfileError('display requires bounded string lines');
  const bytes = new TextEncoder().encode(value.join('\n')).length;
  if (bytes > LIMITS.textBytes) throw new ProfileError('display text budget');
  return value.slice();
}
export function resultLines(result) { return textLines(result?.raw?.text ?? result?.text ?? []); }
export function mountedLines(node, name, select) {
  let element, closed = false;
  const disposers = [];
  const render = () => {
    if (closed || !element) return;
    element.textContent = select().join('\n');
  };
  node.widgets.mount({ name, serialize: false, sendToPrompt: false,
    render(container) {
      element = container.ownerDocument.createElement('pre');
      element.style.cssText = 'font:12px monospace;white-space:pre-wrap;margin:0';
      container.append(element); render();
    },
    destroy() { if (closed) return; closed = true; for (const off of disposers.splice(0)) off(); element = undefined; },
  });
  return { render, disposers, get closed() { return closed; } };
}
export function imageProperties(width, height) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || width * height > 16777216)
    throw new ProfileError('preview dimensions profile');
  let a = width, b = height; while (b) { const old = b; b = a % b; a = old; }
  const standard = [[1,'1:1'],[1.25,'5:4'],[1.33333,'4:3'],[1.5,'3:2'],[1.6,'16:10'],[1.66667,'5:3'],
    [1.77778,'16:9'],[1.88889,'17:9'],[2,'2:1'],[2.33333,'21:9'],[2.35,'2.35:1'],[2.39,'2.39:1'],[2.4,'12:5']];
  let nearest = null, difference = Infinity;
  for (const [ratio, label] of standard) { const diff = Math.abs(width / height - ratio); if (diff < difference) { difference = diff; nearest = label; } }
  if (difference > .05) nearest = null;
  const exact = `${width / a}:${height / a}`;
  return [`${width}x${height} | ${(width * height / 1000000).toFixed(2)}MP`,
    `Ratio: ${exact} or ${(width / height).toFixed(2)}:1${nearest && nearest !== exact ? ` or ~${nearest}` : ''}`,
    `Tensor Size: ${(width * height * 3 * 4 / 1048576).toFixed(2)}MB`];
}
export function managedView(comfy, label) {
  if (typeof label !== 'string' || !label || label.length > 1024 || label.startsWith('/') || label.includes('\\') || /[\u0000-\u001f\u007f]/.test(label))
    throw new ProfileError('preview managed label required');
  const parts = label.split('/'); if (parts.some(p => !p || p === '.' || p === '..')) throw new ProfileError('preview traversal refused');
  const file = parts.pop();
  return comfy.backend.url(`/view?filename=${encodeURIComponent(file)}&type=input&subfolder=${encodeURIComponent(parts.join('/'))}`);
}
