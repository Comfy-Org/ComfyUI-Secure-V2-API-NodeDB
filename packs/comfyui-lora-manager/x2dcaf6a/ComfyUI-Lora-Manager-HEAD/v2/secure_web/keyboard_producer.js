// Private compatibility selection, not a published platform or route upgrade.
import { createSyntaxSelection, planLoraInsertion } from './autocomplete_insert.js';
import { expectedOrigins, tuple } from './keyboard_bindings.js';

const utf8 = new TextEncoder();
const MAX_RESPONSE = 1024 * 1024; // Existing bounded route response envelope.
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

export function assertKeyboardSelection(selected) {
  if (!selected || selected.format !== 'ned-loader-keyboard-private-selection/1' ||
      selected.private_compatibility_selected !== true || selected.exclusive_entry !== 'validation-entry.js') {
    throw new Error('An explicit private keyboard candidate selection is required');
  }
  for (const [name, value] of Object.entries(tuple)) {
    if (selected.tuple?.[name] !== value) throw new Error('Keyboard source tuple mismatch: ' + name);
  }
  for (const [path, sha256] of Object.entries(expectedOrigins)) {
    if (selected.installed_origins?.[path]?.sha256 !== sha256) {
      throw new Error('Actual installed origin must bind ' + path);
    }
  }
  for (const name of ['profile_receipt', 'registration_receipt', 'auth_storage_receipt',
    'settings_get_receipt', 'usage_producer_receipt', 'capacity_receipt']) {
    const receipt = selected[name];
    if (!receipt || typeof receipt.path !== 'string' || !receipt.path || !hash(receipt.sha256)) {
      throw new Error('Real selected ' + name + ' is required');
    }
  }
  // These source checks cannot authenticate receipts or confer runtime admission.
  // The owner must separately qualify the actual installed full settings GET.
  return selected;
}

export function createKeyboardProducer(comfy, selected) {
  assertKeyboardSelection(selected);
  const syntax = createSyntaxSelection(); // Native per-owner format cache rules.
  let syntaxObserved = false;
  async function json(route) {
    const response = await comfy.http.fetch(route, { method: 'GET' });
    const text = await response.text();
    if (typeof text !== 'string' || text.length > MAX_RESPONSE || utf8.encode(text).length > MAX_RESPONSE) {
      throw new Error('Insertion producer response exceeds the existing route envelope');
    }
    if (!response.ok) throw new Error('Insertion producer refused: ' + response.status);
    return JSON.parse(text);
  }
  async function resolve(item, appendComma, current) {
    if (!current()) return null;
    if (!syntaxObserved) {
      const settings = await json('/lm/settings');
      if (!current()) return null;
      if (!settings || settings.success !== true || !settings.settings ||
          typeof settings.settings !== 'object' || Array.isArray(settings.settings)) {
        throw new Error('A successful genuine settings projection is required');
      }
      syntax.received(settings); syntaxObserved = true;
    }
    const data = await json('/lm/loras/usage-tips-by-path?relative_path=' + encodeURIComponent(item));
    if (!current()) return null;
    if (!data || data.success !== true || !Object.hasOwn(data, 'usage_tips')) {
      throw new Error('A successful genuine usage-tip response is required');
    }
    const insertText = planLoraInsertion(item, syntax.get(), data, appendComma);
    if (utf8.encode(insertText).length > 262144) throw new Error('Insertion text exceeds Loader ownership');
    return insertText;
  }
  return Object.freeze({
    resolve,
    async prepare(items, appendComma, current) {
      if (!Array.isArray(items) || !items.length || items.length > 100 ||
          items.some(item => typeof item !== 'string')) throw new Error('Invalid owned menu');
      // Real full GET, not a syntax-only imitation or a secret-bearing store read.
      // Failed/unselected producer clears readiness; it is not default1 success.
      const plans = new Map();
      // One serial request per selected name; no hidden retries or background cache.
      // Declarations remain empty until every possible acceptance target is ready.
      for (const item of items) {
        if (!current()) return null;
        const insertText = await resolve(item, appendComma, current);
        if (insertText === null || !current()) return null;
        plans.set(item, insertText);
      }
      return plans;
    }
  });
}
