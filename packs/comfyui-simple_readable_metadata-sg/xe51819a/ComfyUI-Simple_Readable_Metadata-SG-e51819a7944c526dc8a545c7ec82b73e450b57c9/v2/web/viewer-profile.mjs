// Pack-owned bounded data and regular-syntax profile. No authored code evaluation.
export class ProfileError extends Error {
  constructor(message) { super(`Viewer profile: ${message}`); this.name = 'ProfileError'; }
}
export const LIMITS = Object.freeze({ textBytes: 65536, patternUnits: 256, states: 512,
  transitions: 262144, results: 4096, dataNodes: 4096, dataDepth: 32, prettyBytes: 262144 });
const utf8 = value => new TextEncoder().encode(value).length;
function boundedText(text) {
  if (typeof text !== 'string' || text.length > LIMITS.textBytes || utf8(text) > LIMITS.textBytes)
    throw new ProfileError('input exceeds 64KiB text profile');
}

export function parseData(text) {
  boundedText(text);
  let i = 0, nodes = 0, work = 0;
  const tick = () => { if (++work > LIMITS.transitions) throw new ProfileError('data work budget'); };
  const fail = message => { throw new ProfileError(`${message} at ${i}`); };
  function space() {
    while (i < text.length) {
      tick();
      if (/\s/.test(text[i])) { i++; continue; }
      if (text.slice(i, i + 2) === '//') {
        i += 2; while (i < text.length && !/[\r\n]/.test(text[i])) { tick(); i++; } continue;
      }
      if (text.slice(i, i + 2) === '/*') {
        i += 2;
        while (i < text.length && text.slice(i, i + 2) !== '*/') { tick(); i++; }
        if (i >= text.length) fail('unterminated comment');
        i += 2; continue;
      }
      break;
    }
  }
  function string() {
    const quote = text[i++]; let out = '';
    while (i < text.length) {
      tick(); const c = text[i++];
      if (c === quote) return out;
      if (c < ' ') fail('control character in string');
      if (c !== '\\') { out += c; continue; }
      const e = text[i++];
      const simple = { '"': '"', "'": "'", '\\': '\\', '/': '/', b: '\b', f: '\f', n: '\n', r: '\r', t: '\t' };
      if (Object.hasOwn(simple, e)) { out += simple[e]; continue; }
      if (e === 'u' || e === 'x') {
        const count = e === 'u' ? 4 : 2, hex = text.slice(i, i + count);
        if (hex.length !== count || !/^[0-9a-f]+$/i.test(hex)) fail('invalid hexadecimal escape');
        out += String.fromCharCode(parseInt(hex, 16)); i += count; continue;
      }
      fail('unsupported string escape');
    }
    fail('unterminated string');
  }
  function value(depth = 0) {
    tick(); space();
    if (depth > LIMITS.dataDepth || ++nodes > LIMITS.dataNodes) fail('data depth/item budget');
    const c = text[i];
    if (c === '"' || c === "'") return string();
    if (c === '{') {
      i++; const result = Object.create(null); space();
      if (text[i] === '}') { i++; return result; }
      while (i < text.length) {
        space(); let key;
        if (text[i] === '"' || text[i] === "'") key = string();
        else {
          const identifier = /^[A-Za-z_$][A-Za-z0-9_$]*/.exec(text.slice(i));
          if (!identifier) fail('expected inert object key');
          key = identifier[0]; i += key.length;
        }
        if (++nodes > LIMITS.dataNodes) fail('data key budget');
        space(); if (text[i++] !== ':') fail('expected colon, not getter/expression');
        result[key] = value(depth + 1); space();
        if (text[i] === '}') { i++; return result; }
        if (text[i++] !== ',') fail('expected object comma');
        space(); if (text[i] === '}') { i++; return result; }
      }
      fail('unterminated object');
    }
    if (c === '[') {
      i++; const result = []; space();
      if (text[i] === ']') { i++; return result; }
      while (i < text.length) {
        result.push(value(depth + 1)); space();
        if (text[i] === ']') { i++; return result; }
        if (text[i++] !== ',') fail('expected array comma; holes unsupported');
        space(); if (text[i] === ']') { i++; return result; }
      }
      fail('unterminated array');
    }
    for (const [word, literal] of [['true', true], ['false', false], ['null', null]]) {
      if (text.slice(i, i + word.length) === word) { i += word.length; return literal; }
    }
    const number = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(i));
    if (number) {
      i += number[0].length; const result = Number(number[0]);
      if (!Number.isFinite(result)) fail('nonfinite data number'); return result;
    }
    fail('unsupported value/executable expression');
  }
  const result = value(); space(); if (i !== text.length) fail('trailing expression');
  return result;
}
export function prettyData(text) {
  const result = JSON.stringify(parseData(text), null, 2);
  if (utf8(result) > LIMITS.prettyBytes) throw new ProfileError('pretty output budget');
  return result;
}

function parsePattern(pattern) {
  if (typeof pattern !== 'string' || pattern.length > LIMITS.patternUnits) throw new ProfileError('pattern budget');
  let i = 0, nodes = 0;
  const node = value => { if (++nodes > LIMITS.states) throw new ProfileError('pattern state budget'); return value; };
  const fail = message => { throw new ProfileError(`${message} at pattern ${i}`); };
  function escape() {
    const begin = i++;
    if (i >= pattern.length) fail('trailing escape');
    const c = pattern[i++];
    if (/[1-9]/.test(c) || c === 'k' && pattern[i] === '<') fail('backreferences unsupported');
    if (c === '0' && /[0-9]/.test(pattern[i] ?? '')) fail('legacy octal unsupported');
    if (c === 'u' || c === 'x') {
      const count = c === 'u' ? 4 : 2, hex = pattern.slice(i, i + count);
      if (hex.length !== count || !/^[0-9a-f]+$/i.test(hex)) fail('unsupported hexadecimal escape');
      i += count;
    } else if (c === 'c') {
      if (!/[A-Za-z]/.test(pattern[i] ?? '')) fail('unsupported control escape'); i++;
    } else if (c === 'p' || c === 'P') fail('Unicode properties unsupported in non-Unicode profile');
    return pattern.slice(begin, i);
  }
  function atom(depth) {
    if (depth > 32) fail('pattern depth');
    const c = pattern[i]; let result;
    if (c === '(') {
      i++;
      if (pattern[i] === '?') {
        if (pattern.slice(i, i + 2) !== '?:') fail('lookaround/named groups unsupported'); i += 2;
      }
      result = alternation(depth + 1);
      if (pattern[i++] !== ')') fail('unterminated group');
    } else {
      let raw;
      if (c === '[') {
        const begin = i++;
        if (pattern[i] === '^') i++;
        while (i < pattern.length && pattern[i] !== ']') {
          if (pattern[i] === '\\') escape(); else i++;
        }
        if (pattern[i++] !== ']') fail('unterminated character class');
        raw = pattern.slice(begin, i);
      } else if (c === '\\') raw = escape();
      else {
        if (c === undefined || '*+?{}]'.includes(c)) fail('unsupported atom'); raw = pattern[i++];
      }
      // Closed one-atom native matcher only: never authored groups/repetition.
      let test;
      try { test = new RegExp(raw, 'iy'); } catch { fail('invalid atom'); }
      result = node({ op: 'atom', test, raw });
    }
    let min, max;
    if (pattern[i] === '*') { min = 0; max = Infinity; i++; }
    else if (pattern[i] === '+') { min = 1; max = Infinity; i++; }
    else if (pattern[i] === '?') { min = 0; max = 1; i++; }
    else if (pattern[i] === '{') {
      const quantifier = /^\{([0-9]+)(?:,([0-9]*))?\}/.exec(pattern.slice(i));
      if (!quantifier) fail('unsupported brace syntax');
      i += quantifier[0].length; min = Number(quantifier[1]);
      max = quantifier[2] === undefined ? min : quantifier[2] === '' ? Infinity : Number(quantifier[2]);
      if (min > 256 || max !== Infinity && max > 256 || max < min) fail('quantifier bounds');
    }
    if (min !== undefined) {
      if (result.op === 'atom' && ['^', '$', '\\b', '\\B'].includes(result.raw)) fail('quantified assertion unsupported');
      let lazy = false; if (pattern[i] === '?') { i++; lazy = true; }
      result = node({ op: 'repeat', child: result, min, max, lazy });
    }
    return result;
  }
  function sequence(depth) {
    const items = [];
    while (i < pattern.length && pattern[i] !== '|' && pattern[i] !== ')') items.push(atom(depth));
    return node({ op: 'sequence', items });
  }
  function alternation(depth) {
    const choices = [sequence(depth)];
    while (pattern[i] === '|') { i++; choices.push(sequence(depth)); }
    return choices.length === 1 ? choices[0] : node({ op: 'alternate', choices });
  }
  const result = alternation(0); if (i !== pattern.length) fail('unexpected closing group');
  return result;
}

export function compileRegular(pattern) {
  const tree = parsePattern(pattern), code = [];
  const emit = instruction => {
    if (code.length >= LIMITS.states) throw new ProfileError('compiled state budget');
    code.push(instruction); return code.length - 1;
  };
  const accept = emit({ op: 'accept' });
  function compile(item, next) {
    if (item.op === 'atom') return emit({ op: 'atom', test: item.test, next });
    if (item.op === 'sequence') {
      for (let n = item.items.length - 1; n >= 0; n--) next = compile(item.items[n], next);
      return next;
    }
    if (item.op === 'alternate') {
      let branch = compile(item.choices.at(-1), next);
      for (let n = item.choices.length - 2; n >= 0; n--)
        branch = emit({ op: 'split', first: compile(item.choices[n], next), second: branch });
      return branch;
    }
    if (item.max === Infinity) {
      const split = emit({ op: 'split' }); const child = compile(item.child, split);
      Object.assign(code[split], item.lazy ? { first: next, second: child } : { first: child, second: next });
      next = split;
    } else {
      for (let n = item.min; n < item.max; n++) {
        const child = compile(item.child, next);
        next = emit(item.lazy ? { op: 'split', first: next, second: child } : { op: 'split', first: child, second: next });
      }
    }
    for (let n = 0; n < item.min; n++) next = compile(item.child, next);
    return next;
  }
  const entry = compile(tree, accept);
  return Object.freeze({ pattern, code: Object.freeze(code), entry, states: code.length });
}
export function makeMeter(limit = LIMITS.transitions) {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > LIMITS.transitions) throw new ProfileError('invalid work limit');
  return { remaining: limit, transitions: 0, results: 0 };
}
function tick(meter) {
  if (--meter.remaining < 0) throw new ProfileError('regex transition budget'); meter.transitions++;
}
export function firstMatch(compiled, text, from = 0, meter = makeMeter()) {
  boundedText(text);
  return firstMatchValidated(compiled, text, from, meter);
}
function firstMatchValidated(compiled, text, from, meter) {
  if (!Number.isSafeInteger(from) || from < 0 || from > text.length + 1) throw new ProfileError('invalid start');
  for (let start = from; start <= text.length; start++) {
    tick(meter);
    const stack = [[compiled.entry, start]], seen = new Set();
    while (stack.length) {
      tick(meter); const [pc, pos] = stack.pop(), key = `${pc}:${pos}`;
      if (seen.has(key)) continue; seen.add(key);
      const instruction = compiled.code[pc];
      if (instruction.op === 'accept') {
        if (++meter.results > LIMITS.results) throw new ProfileError('regex result budget');
        return { index: start, end: pos, match: text.slice(start, pos) };
      }
      if (instruction.op === 'split') {
        stack.push([instruction.second, pos], [instruction.first, pos]);
      } else {
        instruction.test.lastIndex = pos;
        const found = instruction.test.exec(text);
        if (found && found.index === pos) stack.push([instruction.next, pos + found[0].length]);
      }
      if (stack.length > LIMITS.transitions) throw new ProfileError('regex pending-state budget');
    }
  }
  return null;
}
export function allMatches(pattern, text, meter = makeMeter()) {
  boundedText(text);
  const compiled = compileRegular(pattern), results = []; let from = 0;
  while (from <= text.length) {
    const result = firstMatchValidated(compiled, text, from, meter);
    if (!result) break; results.push(result);
    from = result.end + (result.end === result.index ? 1 : 0);
  }
  return results;
}
export function filterLines(pattern, text, meter = makeMeter()) {
  return filterLineRows(pattern, text, meter).join('\n');
}
export function filterLineRows(pattern, text, meter = makeMeter()) {
  boundedText(text); const compiled = compileRegular(pattern);
  return text.split('\n').filter(line => firstMatchValidated(compiled, line, 0, meter) !== null);
}
export const escapeText = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function highlight(text, matches, current = -1) {
  boundedText(text); let previous = 0, result = '';
  for (let n = 0; n < matches.length; n++) {
    const match = matches[n];
    result += escapeText(text.slice(previous, match.index)) + `<span class="${n === current ? 'current-match' : 'match'}" style="background-color:${n === current ? '#ff6b6b' : '#ffeb3b'};color:#000">${escapeText(match.match)}</span>`;
    previous = match.end;
  }
  result += escapeText(text.slice(previous));
  if (utf8(result) > LIMITS.prettyBytes) throw new ProfileError('highlight output budget');
  return result;
}
