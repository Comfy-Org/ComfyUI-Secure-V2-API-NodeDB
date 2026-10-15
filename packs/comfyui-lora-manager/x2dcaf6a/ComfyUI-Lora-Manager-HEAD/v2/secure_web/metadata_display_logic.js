// Native JsonDisplay value projection. No backend, DOM or provider substitution.
export const METADATA_COLORS = Object.freeze({
  key: '#6ad6f5', string: '#98c379', number: '#e5c07b',
  boolean: '#c678dd', null: '#7f848e'
});
const TOKEN = /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g;

export function executionMetadata(output) {
  if (output?.metadata === undefined) return { changed: false };
  let value = output.metadata;
  if (Array.isArray(value)) value = value[0];
  if (typeof value === 'string') {
    try { value = JSON.parse(value); }
    catch (error) { console.error('[JsonDisplayWidget] Failed to parse JSON:', error); }
  }
  return { changed: true, value };
}

export function restoreMetadataValue(value, current) {
  return value && typeof value === 'object' ? value : current;
}

export function metadataSerializeValue() {
  // Original Vue serializeValue is async and returns null for every context.
  return null;
}

export function displayTokens(value) {
  // Preserve native Object.keys(undefined) failure and JSON.stringify's own
  // conversion/errors. Do not reject nonfinite members, truncate, or preflight
  // depth/work/text/token limits absent from the pinned native component.
  if (value === null || Object.keys(value).length === 0) {
    return { placeholder: true, text: 'No metadata available', tokens: [] };
  }
  const text = value ? JSON.stringify(value, null, 2) : '';
  const tokens = []; let offset = 0;
  for (const match of text.matchAll(TOKEN)) {
    if (match.index > offset) tokens.push({ kind: 'plain', text: text.slice(offset, match.index) });
    let kind = 'number';
    if (match[0].startsWith('"')) kind = match[0].endsWith(':') ? 'key' : 'string';
    else if (/true|false/.test(match[0])) kind = 'boolean';
    else if (/null/.test(match[0])) kind = 'null';
    tokens.push({ kind, text: kind === 'key' ? match[0].slice(0,-1) : match[0] });
    if (kind === 'key') tokens.push({ kind: 'plain', text: ':' });
    offset = match.index + match[0].length;
  }
  if (offset < text.length) tokens.push({ kind: 'plain', text: text.slice(offset) });
  return { placeholder: false, text, tokens };
}
