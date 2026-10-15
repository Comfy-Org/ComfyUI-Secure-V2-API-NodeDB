// Pack-owned source pool filter state, without route/graph/global authority.
// A future owned mount supplies its explicit API and workflow write boundary.
function closed(value, optionalFolderChildren = false) {
  let items = 0, bytes = 0;
  const stack = new Set();
  function visit(row, depth, field = null) {
    if (++items > 16384 || depth > 16) throw new Error('Pool editor tree exceeds bounds');
    if (row === null || typeof row === 'boolean') return;
    // Native transformFolderTree creates an optional undefined children field.
    // This is render-local option data, never an admitted workflow value.
    if (optionalFolderChildren && row === undefined && field === 'children') return;
    if (typeof row === 'number' && Number.isFinite(row)) return;
    if (typeof row === 'string') {
      const length = new TextEncoder().encode(row).length;
      bytes += length;
      if (length > 262144 || bytes > 1048576) throw new Error('Pool editor text exceeds bounds');
      return;
    }
    if (!row || typeof row !== 'object' || stack.has(row)) throw new Error('Pool editor expects closed data');
    stack.add(row);
    if (Array.isArray(row)) {
      if (row.length > 2048) throw new Error('Pool editor list exceeds bounds');
      for (const child of row) visit(child, depth + 1);
    } else {
      if (Object.getPrototypeOf(row) !== Object.prototype) throw new Error('Pool editor expects plain data');
      for (const [key, child] of Object.entries(row)) { visit(key, depth + 1); visit(child, depth + 1, key); }
    }
    stack.delete(row);
  }
  visit(value, 0);
  return value;
}

export function createPoolEditorState({ api, write, now = Date.now }) {
  let alive = true, restoring = false;
  let filters = { baseModels: [], tags: { include: [], exclude: [] },
    folders: { include: [], exclude: [] },
    license: { noCreditRequired: false, allowSelling: false },
    namePatterns: { include: [], exclude: [], useRegex: false } };
  let items = [], matchCount = 0, baseModels = [], tags = [], folders = [];
  const check = () => { if (!alive) throw new Error('Pool editor is disposed'); };
  const snapshot = () => structuredClone({ filters, items, matchCount, baseModels, tags, folders });
  const build = () => {
    check();
    const config = { version: 2, filters: structuredClone(filters),
      preview: { matchCount, lastUpdated: now() } };
    closed(config);
    if (!restoring) write(config);
    return config;
  };
  const restore = value => {
    check(); closed(value); restoring = true;
    try {
      if (!value?.filters) return snapshot();
      const { filters: selected, preview } = value;
      const next = { baseModels: selected.baseModels || [],
        tags: { include: selected.tags?.include || [], exclude: selected.tags?.exclude || [] },
        folders: { include: selected.folders?.include || [], exclude: selected.folders?.exclude || [] },
        license: { noCreditRequired: selected.license?.noCreditRequired ?? false,
          allowSelling: selected.license?.allowSelling ?? false },
        namePatterns: { include: selected.namePatterns?.include || [],
          exclude: selected.namePatterns?.exclude || [], useRegex: selected.namePatterns?.useRegex ?? false } };
      closed(next); filters = structuredClone(next);
      matchCount = preview?.matchCount || 0;
      return snapshot();
    } finally { restoring = false; }
  };
  return Object.freeze({
    build, restore, snapshot,
    async fetchOptions() {
      check();
      const results = await Promise.all([api.fetchBaseModels(), api.fetchTags(), api.fetchFolderTree()]);
      check(); closed(results.slice(0, 2)); closed(results[2], true);
      [baseModels, tags, folders] = structuredClone(results);
      return snapshot();
    },
    async refresh() {
      check();
      const result = await api.fetchLoras({ baseModels: filters.baseModels,
        tagsInclude: filters.tags.include, tagsExclude: filters.tags.exclude,
        foldersInclude: filters.folders.include, foldersExclude: filters.folders.exclude,
        noCreditRequired: filters.license.noCreditRequired || undefined,
        allowSelling: filters.license.allowSelling || undefined,
        namePatternsInclude: filters.namePatterns.include, namePatternsExclude: filters.namePatterns.exclude,
        namePatternsUseRegex: filters.namePatterns.useRegex, pageSize: 6 });
      // Render disposal must never let a late response write a removed widget.
      // While alive, source arrival order remains unchanged; no latest-only cache.
      check(); closed(result);
      items = structuredClone(result.items); matchCount = result.total;
      return build();
    },
    dispose() { alive = false; items = []; baseModels = []; tags = []; folders = []; },
  });
}
