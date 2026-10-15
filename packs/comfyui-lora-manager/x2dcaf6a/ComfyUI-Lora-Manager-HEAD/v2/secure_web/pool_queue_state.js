// Render-local source state machines. No graph, account, route or registration
// authority lives here; the owned mount/queue consumer supplies those boundaries.
const clone = value => structuredClone(value);
const MAX_QUEUE = 2048;

function closed(value) {
  let count = 0, bytes = 0;
  const seen = new Set();
  const visit = (row, depth) => {
    if (++count > 32768 || depth > 16) throw new Error('Pool state exceeds tree bounds');
    if (row === null || typeof row === 'boolean') return;
    if (typeof row === 'number' && Number.isFinite(row)) return;
    if (typeof row === 'string') {
      bytes += new TextEncoder().encode(row).length;
      if (bytes > 1048576) throw new Error('Pool state exceeds text bounds');
      return;
    }
    if (!row || typeof row !== 'object' || seen.has(row)) throw new Error('Pool state must be closed data');
    seen.add(row);
    if (Array.isArray(row)) {
      if (row.length > MAX_QUEUE) throw new Error('Pool state exceeds entry bounds');
      row.forEach(item => visit(item, depth + 1));
    } else {
      if (Object.getPrototypeOf(row) !== Object.prototype) throw new Error('Pool state must be plain data');
      for (const [key, item] of Object.entries(row)) { visit(key, depth + 1); visit(item, depth + 1); }
    }
    seen.delete(row);
  };
  visit(value, 0);
  return value;
}

export function createRandomizerQueueState({ draw = Math.random } = {}) {
  let alive = true, hasExecuted = false, pending = [], loras = [];
  let executionSeed = null, nextSeed = null;
  let config;
  const assertAlive = () => { if (!alive) throw new Error('Randomizer is disposed'); };
  const snapshot = () => clone({ config: { ...config, execution_seed: executionSeed, next_seed: nextSeed },
    loras, hasExecuted, pendingCount: pending.length });
  const restore = value => {
    assertAlive(); closed(value);
    const raw = value.roll_mode;
    config = {
      count_mode: value.count_mode || 'range', count_fixed: value.count_fixed || 3,
      count_min: value.count_min || 2, count_max: value.count_max || 5,
      model_strength_min: value.model_strength_min ?? 0, model_strength_max: value.model_strength_max ?? 1,
      use_same_clip_strength: value.use_same_clip_strength ?? true,
      clip_strength_min: value.clip_strength_min ?? 0, clip_strength_max: value.clip_strength_max ?? 1,
      roll_mode: raw === 'frontend' ? 'fixed' : raw === 'backend' ? 'always' :
        ['fixed', 'always'].includes(raw) ? raw : 'fixed',
      last_used: value.last_used || null, use_recommended_strength: value.use_recommended_strength ?? false,
      recommended_strength_scale_min: value.recommended_strength_scale_min ?? .5,
      recommended_strength_scale_max: value.recommended_strength_scale_max ?? 1,
    };
    // Source restoreFromConfig intentionally does not restore transient seeds
    // or HAS_EXECUTED. Fresh mounts start null/false; ordinary external restores
    // on the same mount retain its existing transient execution state.
    return snapshot();
  };
  restore({});
  const seed = () => {
    const value = draw();
    if (!Number.isFinite(value) || value < 0 || value >= 1) throw new Error('Invalid random draw');
    return Math.floor(value * 2147483647);
  };
  return Object.freeze({
    restore, snapshot,
    setLoras(value) { assertAlive(); closed(value); if (!Array.isArray(value)) throw new Error('LoRAs must be a list'); loras = clone(value); },
    beforeQueue() {
      assertAlive();
      if (config.roll_mode === 'always') {
        if (hasExecuted) { executionSeed = nextSeed; nextSeed = seed(); }
        else { if (nextSeed === null) nextSeed = seed(); hasExecuted = true; }
      }
      return snapshot().config;
    },
    executed(output) {
      assertAlive(); closed(output);
      const row = {};
      if (output.last_used !== undefined) row.lastUsed = clone(output.last_used);
      if (output.loras && Array.isArray(output.loras)) row.loras = clone(output.loras);
      if (row.lastUsed !== undefined || row.loras !== undefined) {
        if (pending.length >= MAX_QUEUE) throw new Error('Randomizer pending queue exceeds bounds');
        pending.push(row);
      }
    },
    complete() {
      assertAlive();
      const row = pending.shift();
      if (row) {
        if (row.lastUsed !== undefined) config.last_used = row.lastUsed;
        if (row.loras !== undefined) loras = row.loras;
      }
      return snapshot();
    },
    reuseLast() {
      assertAlive();
      if (!config.last_used || config.last_used.length === 0) return null;
      loras = clone(config.last_used); config.roll_mode = 'fixed';
      return clone(loras);
    },
    dispose() { alive = false; pending = []; loras = []; config = null; },
  });
}

export function createCyclerQueueState() {
  let alive = true, hasExecuted = false, executionQueue = [], pending = [];
  let executionIndex = null, nextIndex = null, displayRepeatUsed = 0;
  let executingRepeatStep = 0, isWorkflowExecuting = false;
  let config;
  const assertAlive = () => { if (!alive) throw new Error('Cycler is disposed'); };
  const snapshot = () => clone({ config: { ...config, execution_index: executionIndex, next_index: nextIndex },
    hasExecuted, queuedCount: executionQueue.length, pendingCount: pending.length,
    displayRepeatUsed, executingRepeatStep, isWorkflowExecuting });
  const restore = value => {
    assertAlive(); closed(value);
    config = {
      current_index: value.current_index || 1, total_count: value.total_count || 0,
      pool_config_hash: value.pool_config_hash || '', model_strength: value.model_strength ?? 1,
      clip_strength: value.clip_strength ?? 1, use_same_clip_strength: value.use_same_clip_strength ?? true,
      use_preset_strength: value.use_preset_strength ?? false,
      preset_strength_scale: value.preset_strength_scale ?? 1, sort_by: value.sort_by || 'filename',
      current_lora_name: value.current_lora_name || '', current_lora_filename: value.current_lora_filename || '',
      repeat_count: value.repeat_count ?? 1, repeat_used: value.repeat_used ?? 0,
      is_paused: value.is_paused ?? false, include_no_lora: value.include_no_lora ?? false,
    };
    return snapshot();
  };
  restore({});
  const advance = current => {
    let next = current + 1;
    const total = config.total_count + (config.include_no_lora ? 1 : 0);
    if (total > 0 && next > total) next = 1;
    return next;
  };
  const first = value => Array.isArray(value) ? value[0] : value;
  return Object.freeze({
    restore, snapshot,
    beforeQueue() {
      assertAlive();
      if (executionQueue.length >= MAX_QUEUE) throw new Error('Cycler execution queue exceeds bounds');
      if (config.is_paused) {
        executionQueue.push({ isPaused: true, repeatUsed: config.repeat_used, repeatCount: config.repeat_count,
          shouldAdvanceDisplay: false, displayRepeatUsed });
        return { ...snapshot().config, execution_index: null };
      }
      if (hasExecuted) {
        if (config.repeat_used < config.repeat_count) config.repeat_used++;
        else {
          config.repeat_used = 1;
          executionIndex = nextIndex;
          nextIndex = advance(executionIndex ?? config.current_index);
        }
      } else {
        config.repeat_used = 1;
        if (nextIndex === null) nextIndex = advance(config.current_index);
        hasExecuted = true;
      }
      const shouldAdvanceDisplay = config.repeat_used >= config.repeat_count;
      executionQueue.push({ isPaused: false, repeatUsed: config.repeat_used, repeatCount: config.repeat_count,
        shouldAdvanceDisplay, displayRepeatUsed: shouldAdvanceDisplay ? 0 : config.repeat_used });
      return snapshot().config;
    },
    executed(output) {
      assertAlive(); closed(output);
      const context = executionQueue[0];
      if (context && pending.length >= MAX_QUEUE) throw new Error('Cycler pending queue exceeds bounds');
      executionQueue.shift();
      if (output.total_count !== undefined) config.total_count = first(output.total_count);
      if (context) {
        pending.push({ ...context, output: {
          nextIndex: output.next_index !== undefined ? first(output.next_index) : config.current_index,
          nextLoraName: output.next_lora_name !== undefined ? first(output.next_lora_name) : '',
          nextLoraFilename: output.next_lora_filename !== undefined ? first(output.next_lora_filename) : '',
          currentLoraName: output.current_lora_name !== undefined ? first(output.current_lora_name) : '',
          currentLoraFilename: output.current_lora_filename !== undefined ? first(output.current_lora_filename) : '',
        }});
        executingRepeatStep = context.repeatUsed; isWorkflowExecuting = true;
      }
    },
    complete() {
      assertAlive();
      const row = pending.shift();
      if (row) {
        displayRepeatUsed = row.displayRepeatUsed;
        if (row.shouldAdvanceDisplay) {
          config.current_index = row.output.nextIndex;
          config.current_lora_name = row.output.nextLoraName;
          config.current_lora_filename = row.output.nextLoraFilename;
        } else {
          config.current_lora_name = row.output.currentLoraName;
          config.current_lora_filename = row.output.currentLoraFilename;
        }
        if (pending.length === 0) { isWorkflowExecuting = false; executingRepeatStep = 0; }
      }
      return snapshot();
    },
    resetIndex() {
      assertAlive(); config.current_index = 1; config.repeat_used = 0; displayRepeatUsed = 0;
      // The source reset handler also clears transient queue state before its
      // async list refresh; the composable alone intentionally keeps paused.
      hasExecuted = false; executionIndex = null; nextIndex = null;
      executionQueue = [];
      return snapshot();
    },
    dispose() { alive = false; config = null; executionQueue = []; pending = []; },
  });
}
