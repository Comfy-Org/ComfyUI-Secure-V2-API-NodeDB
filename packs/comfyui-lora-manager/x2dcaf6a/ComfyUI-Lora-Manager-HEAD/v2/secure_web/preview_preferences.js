// Two fields only; unrelated whole-record settings remain on the trusted owner.
const utf8 = new TextEncoder();
const limit = 1024 * 1024;
const revision = value => value === null || (typeof value === 'string' && value.length > 0 && utf8.encode(value).length <= 1024);
function values(value) {
  if (!value || Object.getPrototypeOf(value) !== Object.prototype ||
      Object.keys(value).sort().join(',') !== 'model_name_display,show_only_sfw' ||
      typeof value.show_only_sfw !== 'boolean' ||
      !['model_name', 'file_name'].includes(value.model_name_display))
    throw new Error('Invalid preview preferences');
  return { ...value };
}
export function createPreviewPreferencesTransport(backend) {
  if (typeof backend?.ownFetch !== 'function') throw new Error('Pack-owned transport required');
  async function request(path, init) {
    const response = await backend.ownFetch(path, init);
    const text = await response.text();
    if (typeof text !== 'string' || text.length > limit || utf8.encode(text).length > limit)
      throw new Error('Preferences response exceeds bounds');
    const data = JSON.parse(text);
    if (!response.ok) throw new Error(typeof data?.error === 'string' ? data.error : 'Preferences request failed');
    return data;
  }
  return Object.freeze({
    async read() {
      const data = await request('preview-preferences', { method: 'GET' });
      if (!data || Object.keys(data).sort().join(',') !== 'preferences,revision' || !revision(data.revision))
        throw new Error('Invalid preferences response');
      return { revision: data.revision, preferences: values(data.preferences) };
    },
    async compareAndSet(record) {
      if (!record || !revision(record.revision)) throw new Error('Invalid preferences revision');
      const changes = values(record.preferences);
      const data = await request('preview-preferences-cas', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: record.revision, changes }) });
      if (!data || Object.keys(data).sort().join(',') !== 'revision,updated' ||
          !revision(data.revision) || typeof data.updated !== 'boolean') throw new Error('Invalid preferences acknowledgement');
      return data;
    },
  });
}

export function createPreviewPreferencesEditor(transport) {
  let alive = true, loaded = false, busy = false, generation = 0;
  let currentRevision = null, draft = null, error = null, conflict = false;
  const snapshot = () => ({ loaded, busy, revision: currentRevision,
    draft: draft && { ...draft }, error, conflict });
  return Object.freeze({
    snapshot,
    async load() {
      if (!alive || busy) return false;
      busy = true; error = null;
      try {
        const record = await transport.read();
        const next = values(record.preferences);
        if (!alive) return false;
        currentRevision = record.revision; draft = next; loaded = true; conflict = false; generation++;
        return true;
      } catch (failure) { if (alive) error = String(failure.message ?? failure); throw failure; }
      finally { if (alive) busy = false; }
    },
    edit(next) {
      if (!alive || !loaded) throw new Error('Preferences must be loaded before editing');
      draft = values(next); generation++; conflict = false;
    },
    async save() {
      if (!alive || !loaded || busy) return false;
      const submitted = { ...draft }, version = generation;
      busy = true; error = null; conflict = false;
      try {
        const result = await transport.compareAndSet({ revision: currentRevision, preferences: submitted });
        if (!alive) return false;
        if (!result.updated) { conflict = true; return false; }
        currentRevision = result.revision;
        // Edits while awaiting a successful commit remain unsaved draft.
        if (generation === version) draft = submitted;
        return true;
      } catch (failure) { if (alive) error = String(failure.message ?? failure); throw failure; }
      finally { if (alive) busy = false; }
    },
    dispose() { alive = false; draft = null; loaded = false; busy = false; error = null; conflict = false; },
  });
}
