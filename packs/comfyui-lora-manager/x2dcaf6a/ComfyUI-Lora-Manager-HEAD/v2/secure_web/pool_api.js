// Pool-owned option/ordinary-preview transport, never a global service URL.
function closed(value) {
  let count = 0, textBytes = 0;
  const seen = new Set();
  function walk(row, depth) {
    if (++count > 16384 || depth > 16) throw new Error('Pool response exceeds tree bounds');
    if (row === null || typeof row === 'boolean') return;
    if (typeof row === 'number' && Number.isFinite(row)) return;
    if (typeof row === 'string') {
      textBytes += new TextEncoder().encode(row).length;
      if (textBytes > 1048576) throw new Error('Pool response exceeds text bounds');
      return;
    }
    if (!row || typeof row !== 'object' || seen.has(row)) throw new Error('Pool response must be closed data');
    seen.add(row);
    if (Array.isArray(row)) {
      if (row.length > 2048) throw new Error('Pool response exceeds row bounds');
      row.forEach(child => walk(child, depth + 1));
    } else {
      if (Object.getPrototypeOf(row) !== Object.prototype) throw new Error('Pool response must be plain data');
      for (const [key, child] of Object.entries(row)) { walk(key, depth + 1); walk(child, depth + 1); }
    }
    seen.delete(row);
  }
  walk(value, 0);
  return value;
}

export function transformFolderTree(tree, parent = '') {
  closed(tree);
  if (!tree || typeof tree !== 'object') return [];
  return Object.entries(tree).map(([name, children]) => {
    const key = parent ? `${parent}/${name}` : name;
    const nodes = transformFolderTree(children, key);
    return { key, label: name, children: nodes.length ? nodes : undefined };
  });
}

export function createPoolApi(backend, { preview = null, onError = () => {} } = {}) {
  if (!backend || typeof backend.ownFetch !== 'function') throw new Error('Pack-owned pool transport required');
  const request = async path => {
    const response = await backend.ownFetch(path, { method: 'GET' });
    const text = await response.text();
    if (text.length > 1048576 || new TextEncoder().encode(text).length > 1048576)
      throw new Error('Pool response exceeds byte bounds');
    const result = JSON.parse(text); closed(result);
    // Source option API reads JSON independent of response.ok; source bodies
    // containing an error and no option field become empty choices.
    return result;
  };
  const options = async (path, field) => {
    try { return (await request(path))[field] || []; }
    catch (error) { onError(error); return []; }
  };
  return Object.freeze({
    fetchBaseModels: (limit = 50) => options('pool-base-models?limit=' + encodeURIComponent(limit), 'base_models'),
    fetchTags: (limit = 0) => options('pool-top-tags?limit=' + encodeURIComponent(limit), 'tags'),
    async fetchFolderTree() {
      try { return transformFolderTree((await request('pool-folder-tree')).tree || {}); }
      catch (error) { onError(error); return []; }
    },
    async fetchLoras(params) {
      if (preview) return await preview(params);
      try {
        const body = JSON.stringify(params);
        closed(JSON.parse(body));
        if (new TextEncoder().encode(body).length > 1048576) throw new Error('Pool preview envelope exceeds bounds');
        const response = await backend.ownFetch('pool-preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
        });
        const text = await response.text();
        if (typeof text !== 'string' || text.length > 1048576 || new TextEncoder().encode(text).length > 1048576)
          throw new Error('Pool preview response exceeds bounds');
        const data = JSON.parse(text); closed(data);
        return { items: data.items || [], total: data.total || 0 };
      } catch (error) { onError(error); return { items: [], total: 0 }; }
    },
  });
}
