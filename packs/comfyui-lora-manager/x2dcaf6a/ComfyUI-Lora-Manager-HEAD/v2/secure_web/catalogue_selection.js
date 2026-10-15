// Workflow-owned LoRA rows over the public logical catalogue. No editable
// library storage, sidecars, credentials, ambient DOM or backend route access.
const MAX_ROWS = 64;
const MAX_CATALOGUE = 2048;
/** @typedef {{[key:string]:unknown,name:string,strength:number|string,clipStrength:number|string,active?:boolean,expanded?:unknown,locked?:unknown,selected?:boolean}} LoraRow */
const encoder = new TextEncoder();
/** @param {unknown} value */
const copy = value => JSON.parse(JSON.stringify(value));

/** @param {unknown} value */
export function logicalName(value) {
  if (typeof value !== 'string' || !value || encoder.encode(value).length > 4096 ||
      value.startsWith('/') || value.includes('\\') || value.includes(':') ||
      value.split('/').some(part => !part || part === '.' || part === '..'))
    throw new Error('LoRA must be a bounded logical catalogue name');
  return value;
}

/** @param {string} name */
const stem = name => name.replace(/\.(safetensors|ckpt|pt|bin)$/i, '');
/** @param {unknown} value */
function closedJson(value) {
  /** @type {Array<[unknown,number]>} */
  const pending = [[value,0]];
  const seen = new Set();
  let count = 0, bytes = 0;
  while (pending.length) {
    const entry = pending.pop();
    if (!entry) break;
    const [item,depth] = entry;
    if (++count > 16384 || depth > 16) throw new Error('LoRA rows exceed work bounds');
    if (item === null || typeof item === 'boolean') continue;
    if (typeof item === 'number') {
      if (!Number.isFinite(item)) throw new Error('LoRA rows must contain finite JSON');
    } else if (typeof item === 'string') {
      bytes += encoder.encode(item).length;
      if (bytes > 262144) throw new Error('LoRA rows exceed byte bounds');
    } else if (typeof item === 'object') {
      if (seen.has(item)) throw new Error('LoRA rows must be an acyclic JSON tree');
      seen.add(item);
      if (Object.getPrototypeOf(item) !== Object.prototype && !Array.isArray(item))
        throw new Error('LoRA rows must be plain JSON');
      const values = Array.isArray(item) ? item : Object.entries(item).flat();
      if (values.length + pending.length + count > 16384) throw new Error('LoRA rows exceed work bounds');
      for (const child of values) pending.push([child,depth+1]);
    } else throw new Error('LoRA rows must contain closed JSON');
  }
}
/** @param {unknown} value */
function finiteStrength(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || !Number.isFinite(Number(value)) ||
      Math.abs(Number(value)) > 100) throw new Error('LoRA strength exceeds bounds');
  return value;
}

/** @param {unknown} value @returns {LoraRow[]} */
export function normalizeRows(value) {
  // Pinned widget setter treats non-arrays as empty and keeps LAST duplicate.
  const input = Array.isArray(value) ? value : [];
  if (input.length > MAX_ROWS) throw new Error('LoRA row count exceeds bounds');
  closedJson(input);
  /** @type {Map<string,LoraRow>} */
  const rows = new Map();
  for (const row of input) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) throw new Error('Invalid LoRA row');
    const data = /** @type {Record<string,unknown>} */ (row);
    const name = logicalName(data.name), strength = finiteStrength(data.strength);
    // Retain pinned truthy fallback, including clipStrength=0 -> strength.
    const clipStrength = finiteStrength(data.clipStrength || strength);
    const text = JSON.stringify(row);
    if (text.length > 262144 || encoder.encode(text).length > 262144)
      throw new Error('LoRA row payload exceeds bounds');
    const next = { ...copy(row), name,strength,clipStrength,
      expanded: Object.hasOwn(row, 'expanded') ? data.expanded : Number(clipStrength) !== Number(strength),
      locked: Object.hasOwn(row, 'locked') ? data.locked : false };
    rows.delete(next.name); rows.set(next.name, next);
  }
  const result = [...rows.values()];
  if (encoder.encode(JSON.stringify(result)).length > 262144) throw new Error('LoRA rows exceed bounds');
  return result;
}

/**
 * @param {import('../comfy-api.d.ts').Comfy} comfy
 * @param {{read:()=>unknown,write:(rows:LoraRow[])=>void,onSelection?:(name:string|null)=>void}} options
 */
export function createCatalogueSelection(comfy, { read, write, onSelection = () => {} }) {
  /** @type {string[]} */
  let names = [];
  /** @type {string|null} */
  let selected = null;
  let alive = true;
  let generation = 0;
  /** @type {Set<()=>void>} */
  const listeners = new Set();
  const current = () => normalizeRows(read());
  const assertAlive = () => { if (!alive) throw new Error('LoRA selection is disposed'); };
  const changed = () => { for (const fn of [...listeners]) fn(); };
  const restore = () => {
    const rows = current();
    if (!rows.some(row => row.name === selected)) selected = rows.find(row => row.selected)?.name ?? null;
    return rows;
  };
  const snapshot = () => { assertAlive(); return restore().map(row => ({ ...row, selected: row.name === selected })); };
  /** @param {LoraRow[]} rows */
  const commit = rows => {
    assertAlive();
    const next = normalizeRows(rows);
    // Store commit first: a failed setter must leave selection unchanged.
    write(next);
    if (!next.some(row => row.name === selected)) selected = null;
    changed();
  };
  const api = {
    snapshot,
    async refresh() {
      assertAlive();
      const ticket = ++generation;
      const fetched = await comfy.models.list('loras');
      if (!alive || ticket !== generation) return false;
      if (!Array.isArray(fetched) || fetched.length > MAX_CATALOGUE) throw new Error('Catalogue count exceeds bounds');
      const next = fetched.map(logicalName);
      if (new Set(next).size !== next.length) throw new Error('Catalogue identities must be unique');
      names = next.slice(); changed(); return true;
    },
    search(text = '') {
      assertAlive();
      if (typeof text !== 'string' || encoder.encode(text).length > 4096) throw new Error('Search exceeds bounds');
      const needle = text.toLocaleLowerCase();
      return names.filter(name => name.toLocaleLowerCase().includes(needle));
    },
    /** @param {string} name */
    add(name) {
      assertAlive(); logicalName(name);
      if (!names.includes(name)) throw new Error('LoRA is not registered');
      const rowName = stem(name);
      commit([...current(), { name: rowName, strength: 1, clipStrength: 1, active: true, expanded: false, locked: false }]);
      api.select(rowName);
    },
    /** @param {number} index @param {Partial<LoraRow>} patch */
    update(index, patch) {
      assertAlive();
      const rows = current();
      if (!Number.isInteger(index) || index < 0 || index >= rows.length) throw new Error('Invalid row index');
      if (!patch || Object.keys(patch).some(key => !['strength','clipStrength','active','expanded','locked'].includes(key)))
        throw new Error('Invalid row edit');
      const next = { ...rows[index], ...patch };
      if (Object.hasOwn(next, 'expanded') && !next.expanded) next.clipStrength = next.strength;
      rows[index] = next; commit(rows);
    },
    /** @param {number} index */
    remove(index) {
      assertAlive();
      const rows = current();
      if (!Number.isInteger(index) || index < 0 || index >= rows.length) throw new Error('Invalid row index');
      rows.splice(index, 1); commit(rows);
    },
    /** @param {number} from @param {number} to */
    move(from, to) {
      assertAlive();
      const rows = current();
      if (![from,to].every(index => Number.isInteger(index) && index >= 0 && index < rows.length))
        throw new Error('Invalid row index');
      rows.splice(to, 0, rows.splice(from, 1)[0]); commit(rows);
    },
    /** @param {string|null} name */
    select(name) {
      assertAlive();
      if (name !== null && !current().some(row => row.name === name)) throw new Error('Unknown selected row');
      // Persist selection as the pinned widget getValue does, without a store.
      const next = current().map(row => ({ ...row, selected: row.name === name }));
      write(next); selected = name; onSelection(name); changed();
    },
    /** @param {()=>void} fn */
    onChange(fn) { assertAlive(); listeners.add(fn); return () => { listeners.delete(fn); }; },
    dispose() { if (!alive) return; alive = false; ++generation; listeners.clear(); names = []; },
  };
  restore();
  return Object.freeze(api);
}

// Partial mounted consumer, explicitly not the whole Vue widget/manager UI.
/** @param {import('../comfy-api.d.ts').Comfy} comfy */
export function registerCataloguePicker(comfy) {
  /** @type {Map<string,{node:import('../comfy-api.d.ts').NodeHandle,dispose:()=>void}>} */
  const instances = new Map();
  let disposed = false;
  const off = comfy.defs.extend('Lora Loader (LoraManager)', builder => {
    builder.onRemoved(node => {
      const entry = instances.get(JSON.stringify([node.graphId,node.id]));
      // A queued removal for a replaced handle must not destroy its successor.
      if (entry && (entry.node === node || entry.node.isDeleted)) entry.dispose();
    });
    builder.onCreated(node => {
      if (disposed || node.isDeleted) return;
      const key = JSON.stringify([node.graphId,node.id]);
      instances.get(key)?.dispose();
      const previous = node.widgets.get('loras');
      const initial = normalizeRows(previous?.getValue());
      if (previous) node.widgets.remove('loras');
      /** @type {HTMLElement|null} */
      let root = null;
      /** @type {import('../comfy-api.d.ts').MountedValue|null} */
      let cell = null;
      /** @type {ReturnType<typeof createCatalogueSelection>|null} */
      let controller = null;
      let alive = true;
      let clearListeners = () => {};
      /** @type {Array<()=>void>} */
      const subscriptions = [];
      const dispose = () => {
        if (!alive) return; alive = false;
        controller?.dispose(); clearListeners();
        subscriptions.splice(0).forEach(fn => fn());
        root?.replaceChildren(); root = null; cell = null;
        if (instances.get(key)?.dispose === dispose) instances.delete(key);
      };
      node.widgets.mount({ name:'loras',height:200,defaultValue:initial,serialize:true,sendToPrompt:true,
        render(container, value) {
          if (!alive || node.isDeleted) return;
          root = container; cell = value;
          if (!controller) {
            controller = createCatalogueSelection(comfy, {
              read:() => cell?.get(), write:next => { if (!cell) throw new Error('LoRA selection is disposed'); cell.set(next); },
            });
            subscriptions.push(controller.onChange(renderRows), cell.onChange(renderRows));
          }
          renderRows();
        }, destroy:dispose,
      });
      function renderRows() {
        if (!alive || !root || !controller) return;
        clearListeners(); root.replaceChildren();
        const doc = root.ownerDocument;
        /** @type {Array<()=>void>} */
        const listeners = [];
        /** @param {HTMLElement} element @param {string} type @param {()=>void} fn */
        const listen = (element, type, fn) => {
          element.addEventListener(type, fn);
          listeners.push(() => element.removeEventListener(type,fn));
        };
        const input = doc.createElement('input'); input.type = 'search';
        input.placeholder = 'Search registered LoRAs'; root.appendChild(input);
        const available = doc.createElement('div'); root.appendChild(available);
        /** @type {Array<()=>void>} */
        let searchListeners = [];
        function search() {
          searchListeners.splice(0).forEach(fn => fn());
          available.replaceChildren();
          for (const name of controller?.search(input.value ?? '').slice(0,128) ?? []) {
            const button = doc.createElement('button'); button.type = 'button'; button.textContent = name;
            const fn = () => controller?.add(name);
            button.addEventListener('click',fn);
            searchListeners.push(() => button.removeEventListener('click',fn));
            available.appendChild(button);
          }
        }
        listen(input,'input',search);
        const refresh = doc.createElement('button'); refresh.type='button'; refresh.textContent='Refresh catalogue';
        listen(refresh,'click',() => { controller?.refresh().catch(showError); }); root.appendChild(refresh);
        for (const [index,row] of controller.snapshot().entries()) {
          const line = doc.createElement('div');
          const choose = doc.createElement('button'); choose.type='button'; choose.textContent=row.name;
          choose.setAttribute('aria-pressed',String(Boolean(row.selected)));
          listen(choose,'click',() => controller?.select(row.name)); line.appendChild(choose);
          const active = doc.createElement('input'); active.type='checkbox'; active.checked=Boolean(row.active);
          listen(active,'change',() => controller?.update(index,{active:active.checked})); line.appendChild(active);
          const strength = doc.createElement('input'); strength.type='number'; strength.value=String(row.strength);
          strength.min='-100'; strength.max='100'; strength.step='0.01';
          listen(strength,'change',() => controller?.update(index,{strength:Number(strength.value)})); line.appendChild(strength);
          const remove = doc.createElement('button'); remove.type='button'; remove.textContent='Remove';
          listen(remove,'click',() => controller?.remove(index)); line.appendChild(remove);
          root.appendChild(line);
        }
        search();
        clearListeners = () => {
          searchListeners.splice(0).forEach(fn => fn());
          listeners.splice(0).forEach(fn => fn());
        };
      }
      /** @param {unknown} error */
      function showError(error) {
        if (!alive || !root || node.isDeleted) return;
        const text = root.ownerDocument.createElement('p'); text.textContent=error instanceof Error ? error.message : String(error);
        root.appendChild(text);
      }
      instances.set(key,{node,dispose});
    });
  });
  return () => { if (disposed) return; disposed=true; off(); [...instances.values()].forEach(entry => entry.dispose()); };
}
