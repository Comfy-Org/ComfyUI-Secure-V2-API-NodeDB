// Native Create Hook selection values; no model lookup, size cap or row filter.
import { mergeLoras } from './stacker_merge.js';
import { applyLoraValuesToText } from './stacker_syntax.js';

export function createHookRowsFromText(text, rows) {
  return mergeLoras(text, rows);
}

export function createHookTextFromRows(text, rows) {
  return applyLoraValuesToText(text, rows);
}

export function createHookActiveNames(value) {
  const names = new Set();
  value.forEach(lora => { if (lora.active) names.add(lora.name); });
  return names;
}

export function restoreCreateHookRows(text, savedValue) {
  return mergeLoras(text, savedValue || []);
}

// onCreated runs after reconstruction. Retain the restored optional socket.
export function planCreateHookInput(inputs) {
  const existing = inputs.filter(input => input.name === 'prev_hooks');
  if (existing.length > 1 || (existing.length && existing[0].type !== 'HOOKS')) {
    throw new Error('Existing Create Hook prev_hooks socket is ambiguous/incompatible');
  }
  return existing.length ? null : { name: 'prev_hooks', type: 'HOOKS', shape: 'optional' };
}

// Object.is retains undefined, NaN and Infinity distinctions for own-write
// delivery suppression; JSON.stringify would silently collapse these values.
export function sameCreateHookRows(left, right) {
  if (left === right) return true;
  if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return false;
  return left.every((row, index) => {
    const peer = right[index];
    if (row === peer) return true;
    if (!row || !peer || typeof row !== 'object' || typeof peer !== 'object') return false;
    const keys = Object.keys(row), other = Object.keys(peer);
    return keys.length === other.length && keys.every(key =>
      Object.hasOwn(peer, key) && Object.is(row[key], peer[key]));
  });
}
