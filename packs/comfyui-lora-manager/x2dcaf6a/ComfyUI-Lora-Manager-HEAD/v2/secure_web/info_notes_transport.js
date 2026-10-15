// Pack-owned route consumer. Trusted host binds account and pack; durable text
// and route envelopes each have a 1MiB profile, not the old temporary fixture.
import { logicalName } from './catalogue_selection.js';

const MAX_RECORD = 1024 * 1024;
const MAX_ENVELOPE = MAX_RECORD;
const utf8 = new TextEncoder();
const digest = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const revision = value => value === null ||
  (typeof value === 'string' && value.length > 0 && utf8.encode(value).length <= 1024);

function metadataCopy(value) {
  if (!value || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype)
    throw new Error('Model metadata must be a plain object');
  const pending = [[value, 0]], seen = new Set();
  let count = 0, bytes = 0;
  while (pending.length) {
    const [item, depth] = pending.pop();
    if (++count > 65536 || depth > 32) throw new Error('Model record exceeds work bounds');
    if (item === null || typeof item === 'boolean') continue;
    if (typeof item === 'string') {
      if (item.length > MAX_RECORD || (bytes += utf8.encode(item).length) > MAX_RECORD)
        throw new Error('Model record exceeds byte bounds');
    } else if (typeof item === 'number') {
      if (!Number.isFinite(item)) throw new Error('Model record must be finite');
    } else if (typeof item === 'object') {
      if (seen.has(item)) throw new Error('Model record must be an acyclic tree');
      seen.add(item);
      if (!Array.isArray(item) && Object.getPrototypeOf(item) !== Object.prototype)
        throw new Error('Model record must be plain JSON');
      const entries = Array.isArray(item) ? item : Object.entries(item).flat();
      if (entries.length + pending.length + count > 65536) throw new Error('Model record exceeds work bounds');
      for (const child of entries) pending.push([child, depth + 1]);
    } else throw new Error('Model record must be closed JSON');
  }
  const text = JSON.stringify(value);
  if (utf8.encode(text).length > MAX_RECORD) throw new Error('Encoded model record exceeds bounds');
  return JSON.parse(text);
}

export function createInfoNotesTransport(backend) {
  if (!backend || typeof backend.ownFetch !== 'function')
    throw new Error('A pack-owned route transport is required');
  const request = async (path, init) => {
    const response = await backend.ownFetch(path, init);
    const text = await response.text();
    // This is post-receipt validation, not proof of the host's bulk frame cap.
    if (typeof text !== 'string' || text.length > MAX_ENVELOPE || utf8.encode(text).length > MAX_ENVELOPE)
      throw new Error('Model route response exceeds bounds');
    const data = JSON.parse(text);
    if (!response.ok) throw new Error(typeof data?.error === 'string' ? data.error : 'Model record request failed');
    return data;
  };
  return Object.freeze({
    async readRecord(name) {
      logicalName(name);
      const data = await request('info-record?name=' + encodeURIComponent(name), { method: 'GET' });
      if (!data || Object.keys(data).sort().join(',') !== 'metadata,revision,sha256' ||
          !digest(data.sha256) || !revision(data.revision)) throw new Error('Invalid model record response');
      return { sha256: data.sha256, revision: data.revision,
        metadata: data.metadata === null ? null : metadataCopy(data.metadata) };
    },
    async compareAndSet(name, record) {
      logicalName(name);
      if (!record || Object.keys(record).sort().join(',') !== 'metadata,revision,sha256' ||
          !digest(record.sha256) || !revision(record.revision)) throw new Error('Invalid model commit identity');
      const body = JSON.stringify({ name, sha256: record.sha256, revision: record.revision,
        metadata: metadataCopy(record.metadata) });
      if (utf8.encode(body).length > MAX_ENVELOPE) throw new Error('Model commit envelope exceeds bounds');
      const data = await request('info-record-cas', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
      });
      if (!data || Object.keys(data).sort().join(',') !== 'revision,updated' ||
          typeof data.updated !== 'boolean' || !revision(data.revision)) throw new Error('Invalid model commit acknowledgement');
      return data;
    },
  });
}
