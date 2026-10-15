// Pack-owned editable-note state. Transport is explicitly injected; this is
// NOT a new SDK method or an authenticated Cloud library adapter.
import { logicalName } from './catalogue_selection.js';

const utf8 = new TextEncoder();
const MAX_BYTES = 4 * 1024 * 1024;
function documentCopy(value) {
  const pending = [[value,0]], seen = new Set();
  let count = 0, bytes = 0;
  while (pending.length) {
    const [item,depth] = pending.pop();
    if (++count > 65536 || depth > 32) throw new Error('Model record exceeds work bounds');
    if (item === null || typeof item === 'boolean') continue;
    if (typeof item === 'string') {
      if (item.length > MAX_BYTES) throw new Error('Model record exceeds byte bounds');
      bytes += utf8.encode(item).length;
      if (bytes > MAX_BYTES) throw new Error('Model record exceeds byte bounds');
    } else if (typeof item === 'number') {
      if (!Number.isFinite(item)) throw new Error('Model record must be finite');
    } else if (typeof item === 'object') {
      if (seen.has(item)) throw new Error('Model record must be an acyclic tree');
      seen.add(item);
      if (!Array.isArray(item) && Object.getPrototypeOf(item) !== Object.prototype)
        throw new Error('Model record must be plain JSON');
      const entries = Array.isArray(item) ? item : Object.entries(item).flat();
      if (entries.length + pending.length + count > 65536) throw new Error('Model record exceeds work bounds');
      for (const child of entries) pending.push([child,depth+1]);
    } else throw new Error('Model record must be closed JSON');
  }
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Model record must be an object');
  const text = JSON.stringify(value);
  if (utf8.encode(text).length > MAX_BYTES) throw new Error('Encoded model record exceeds bounds');
  return JSON.parse(text);
}

export function createInfoNotesEditor({ readRecord, compareAndSet }) {
  let alive=true, generation=0, saving=false;
  let name=null, digest=null, revision=null, metadata={}, notes='', originalNotes='', error=null;
  let activeTab='notes';
  const listeners=new Set();
  const assertAlive=()=>{ if (!alive) throw new Error('Info editor is disposed'); };
  const emit=()=>{ for (const listener of [...listeners]) listener(); };
  const validNotes=value=>{
    if (typeof value !== 'string' || value.length > MAX_BYTES || utf8.encode(value).length > MAX_BYTES)
      throw new Error('Notes exceed UTF-8 bounds');
    return value;
  };
  const api={
    snapshot() {
      assertAlive();
      return {name,notes,activeTab,saving,dirty:notes!==originalNotes,error};
    },
    async select(nextName) {
      assertAlive();
      if (nextName !== null) logicalName(nextName);
      const ticket=++generation;
      name=nextName; digest=null; revision=null; metadata={};
      notes=''; originalNotes=''; error=null; saving=false; emit();
      // Pinned deselection preserves tab preference. Selection ownership does
      // not become a filesystem path or provider URL.
      if (nextName === null) return true;
      try {
        const record=await readRecord(nextName);
        if (!alive || ticket!==generation) return false;
        if (!record || typeof record.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(record.sha256))
          throw new Error('Invalid record digest identity');
        const next=documentCopy(record.metadata ?? {});
        const text=validNotes(next.notes ?? '');
        metadata=next; digest=record.sha256; revision=record.revision;
        notes=text; originalNotes=text; emit(); return true;
      } catch (failure) {
        if (!alive || ticket!==generation) return false;
        error=failure instanceof Error ? failure.message : String(failure);
        notes='[Error loading notes]'; emit(); throw failure;
      }
    },
    edit(value) { assertAlive(); notes=validNotes(value); error=null; emit(); },
    tab(value) {
      assertAlive();
      if (!['notes','description'].includes(value)) throw new Error('Unknown info tab');
      activeTab=value; emit();
    },
    async save() {
      assertAlive();
      if (saving) throw new Error('Notes save is already in flight');
      if (name===null || digest===null) throw new Error('No loaded model record selected');
      if (notes===originalNotes) return false;
      const ticket=generation, chosen=name, sha256=digest, expectedRevision=revision, writtenNotes=notes;
      const next=documentCopy({...metadata,notes:writtenNotes});
      saving=true; error=null; emit();
      try {
        const result=await compareAndSet(chosen,{sha256,revision:expectedRevision,metadata:next});
        // A backend commit already issued may still commit the original model.
        // Never project its acknowledgement onto a successor selection.
        if (!alive || ticket!==generation) return false;
        if (!result || result.updated!==true) throw new Error('Model record update conflict');
        revision=result.revision; metadata=next; originalNotes=writtenNotes;
        // Preserve edits made while saving; they remain dirty, not auto-saved.
        emit(); return true;
      } catch (failure) {
        if (!alive || ticket!==generation) return false;
        error=failure instanceof Error ? failure.message : String(failure); emit(); throw failure;
      } finally {
        if (alive && ticket===generation) { saving=false; emit(); }
      }
    },
    onChange(listener) { assertAlive(); listeners.add(listener); return ()=>listeners.delete(listener); },
    dispose() { if (!alive) return; alive=false; ++generation; listeners.clear(); },
  };
  return Object.freeze(api);
}
