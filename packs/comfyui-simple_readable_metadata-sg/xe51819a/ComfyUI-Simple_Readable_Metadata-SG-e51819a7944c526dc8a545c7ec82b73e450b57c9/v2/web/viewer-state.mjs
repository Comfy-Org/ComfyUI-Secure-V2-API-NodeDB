import { LIMITS, ProfileError, prettyData, allMatches, filterLineRows, highlight, escapeText, makeMeter } from './viewer-profile.mjs';
export const STATE_KEYS = ['text','pretty_json_text','theme','word_wrap','text_filter','line_filter','pretty_json_mode','font_size','filter_text','line_filter_text'];
const bytes = value => new TextEncoder().encode(value).length;
export function admittedText(value) {
  if (typeof value !== 'string' || value.length > LIMITS.textBytes || bytes(value) > LIMITS.textBytes) throw new ProfileError('64KiB text bound');
  return value;
}
function admittedPretty(value) {
  if (typeof value !== 'string' || value.length > LIMITS.prettyBytes || bytes(value) > LIMITS.prettyBytes) throw new ProfileError('pretty output budget');
  return value;
}
export function initialState(properties = {}) {
  const font = properties.font_size ?? 14;
  if (!Number.isInteger(font) || font < 6 || font > 72) throw new ProfileError('font size 6..72');
  return { text: admittedText(properties.text ?? ''), pretty_json_text: admittedPretty(properties.pretty_json_text ?? ''),
    theme: properties.theme === 'Light' ? 'Light' : 'Dark', word_wrap: properties.word_wrap ?? true,
    text_filter: properties.text_filter ?? false, line_filter: properties.line_filter ?? false,
    pretty_json_mode: properties.pretty_json_mode ?? false, font_size: font,
    filter_text: admittedText(properties.filter_text ?? ''), line_filter_text: admittedText(properties.line_filter_text ?? ''),
    current: -1, status: '', closed: false, revision: 0, confirmDelete: false };
}
export function serializeState(state) { return Object.fromEntries(STATE_KEYS.map(key => [key, state[key]])); }
export function updateText(state, text) {
  state.text = admittedText(text); state.pretty_json_text = ''; state.pretty_json_mode = false; state.current = -1; state.revision++;
}
export function viewData(state) {
  const meter = makeMeter(); let text = state.pretty_json_mode ? state.pretty_json_text : state.text;
  let lineMatches = 0;
  if (state.line_filter && state.line_filter_text) { const rows = filterLineRows(state.line_filter_text, text, meter); lineMatches = rows.length; text = rows.join('\n'); }
  // Native source assigns the chosen raw/filtered text to textarea.value before
  // highlight, counters and selection; that browser property normalizes lines.
  text = text.replaceAll('\r\n','\n').replaceAll('\r','\n');
  const matches = state.text_filter && state.filter_text ? allMatches(state.filter_text, text, meter) : [];
  return { text, matches, marked: matches.length ? highlight(text, matches, state.current) : escapeText(text), transitions: meter.transitions,
    counter: `${text.length} chars | ${text.trim() ? text.trim().split(/\s+/).length : 0} words | ${text ? text.split('\n').length : 0} lines`,
    matchCounter: `${state.current >= 0 && state.current < matches.length ? state.current + 1 : 0} / ${matches.length}`,
    lineCounter: state.line_filter && state.line_filter_text ? `${lineMatches} lines` : '0 lines' };
}
export function togglePretty(state) {
  if (!state.pretty_json_mode) { state.pretty_json_text = prettyData(state.text.trim()); state.pretty_json_mode = true; }
  else state.pretty_json_mode = false;
  state.current = -1;
}
export function positivePrompt(text) {
  admittedText(text); let buffer = [], capturing = false;
  for (const line of text.split('\n')) {
    if (line.trim().startsWith('Positive:')) { capturing = true; const content = line.substring(line.indexOf('Positive:') + 9).trim(); if (content) buffer.push(content); continue; }
    if (capturing) {
      const trimmed = line.trim();
      if (trimmed.startsWith('Negative:') || trimmed.startsWith('Negative prompt:') || /^(===|[\u{1F300}-\u{1F9FF}]|Step|Size|Model)/u.test(trimmed) || trimmed === '') break;
      buffer.push(line);
    }
  }
  let result = buffer.length ? buffer.join('\n').trim() : '';
  if (!buffer.length && (text.includes('Steps:') || text.includes('Negative prompt:'))) {
    let cut = text.length;
    for (const marker of ['Negative prompt:','Steps:']) { const index = text.indexOf(marker); if (index !== -1) cut = Math.min(cut,index); }
    if (cut < text.length) result = text.substring(0,cut).trim();
  }
  return result === '(empty)' ? '' : result;
}
export function exportName(date = new Date()) {
  const pad = value => String(value).padStart(2,'0');
  return `comfy_${pad(date.getDate())}-${pad(date.getMonth()+1)}-${date.getFullYear()}_${pad(date.getHours())}_${pad(date.getMinutes())}_${pad(date.getSeconds())}.txt`;
}
