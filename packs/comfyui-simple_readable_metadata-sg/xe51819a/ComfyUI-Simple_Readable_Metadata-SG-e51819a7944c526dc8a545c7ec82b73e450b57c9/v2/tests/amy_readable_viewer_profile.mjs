import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { ProfileError, LIMITS, parseData, prettyData, compileRegular, allMatches, filterLines, makeMeter, highlight } from '../web/viewer-profile.mjs';
import { initialState, viewData, togglePretty, positivePrompt, updateText, serializeState } from '../web/viewer-state.mjs';

let checks = 0, nativeComparisons = 0;
function same(actual, expected) { assert.deepEqual(actual, expected); checks++; }
function refuses(fn, reason) { assert.throws(fn, error => error instanceof ProfileError && error.message.includes(reason)); checks++; }
function native(pattern, text) {
  return [...text.matchAll(new RegExp(pattern, 'gi'))].map(m => ({ index: m.index, end: m.index + m[0].length, match: m[0] }));
}
const patterns = ['', 'a', 'a|ab', 'ab|a', '.', '[^]', '[ab]', '[^ab]', '\\d', '\\D', '\\s', '\\w', '\\b', '\\B', '^', '$', '^a$',
  'a*', 'a+', 'a?', 'a*?', 'a+?', 'a??', 'a{0,3}', 'a{1,3}?', '(ab|a)*b', '(a?)*', '(a?)+', '(?:)*', '(?:){2}',
  '(a|b)+', 'a.*b', 'a.*?b', '(ab)?b', '(a*)*', '[a-z]+', 'a\\d{1,2}', '(?:a|)b', '[\\s\\S]', '\\uD83D', '\\x61', 'x|$'];
const texts = ['', 'a', 'aa', 'ab', 'aab', 'aba', 'abbb', 'a\nb', 'a\r\nb', 'a\u2028b', 'a\u2029b', '\n', '\r\n', 'x\n', 'A1 a22', '😀a😀', '\ud83d', '\ude00', 'ſKAa', 'prompt\nSeed\nPROMPT'];
for (const pattern of patterns) for (const text of texts) {
  same(allMatches(pattern, text), native(pattern, text)); nativeComparisons++;
  same(filterLines(pattern, text), text.split('\n').filter(line => new RegExp(pattern, 'i').test(line)).join('\n'));
  nativeComparisons++;
}
// Deterministic expanded short cases: native checks remain deliberately tiny.
let randomState = 0x517ab;
const draw = max => { randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0; return randomState % max; };
const atoms = ['a', 'b', '.', '[ab]', '\\d', '\\s', '(?:a|b)', '(?:ab|a)', '(?:a?)'];
const quantifiers = ['', '*', '+', '?', '{0,2}', '{1,3}', '*?', '+?'];
for (let n = 0; n < 350; n++) {
  const pattern = atoms[draw(atoms.length)] + quantifiers[draw(quantifiers.length)] + atoms[draw(atoms.length)] + quantifiers[draw(quantifiers.length)];
  let text = ''; for (let j = 0, count = draw(8); j < count; j++) text += 'ab1 \n'[draw(5)];
  same(allMatches(pattern, text), native(pattern, text)); nativeComparisons++;
}

const inertData = [
  ['{"prompt":"cat","steps":20,"x":[true,false,null,-0,1.2e2]}', { prompt: 'cat', steps: 20, x: [true, false, null, -0, 120] }],
  ["{prompt:'cat', steps:20,}", { prompt: 'cat', steps: 20 }],
  ["/* data */ {prompt:'c\\x61t', arr:[1,2,], /* inert */ extra:'\\uD83D\\uDE00'} // end", { prompt: 'cat', arr: [1, 2], extra: '😀' }],
  ['{"dup":1,"dup":2,"__proto__":{"safe":true}}', JSON.parse('{"dup":2,"__proto__":{"safe":true}}')],
  ['[{},[],"<img>","\\n",3]', [{}, [], '<img>', '\n', 3]],
];
for (const [text, expected] of inertData) same(prettyData(text), JSON.stringify(expected, null, 2));
same(Object.getPrototypeOf(parseData('{x:1}')), null);
for (const text of ['{get x(){return 1}}', '{x:(globalThis.changed=1)}', '{["x"]:1}', '{x:()=>1}', '{x:undefined}', '{x:NaN}', '1+2', '[,]', 'new Object()', '{x:1};anything()'])
  refuses(() => parseData(text), 'Viewer profile');
refuses(() => parseData('['.repeat(34) + '0' + ']'.repeat(34)), 'depth');
refuses(() => parseData('[' + '0,'.repeat(4096) + '0]'), 'budget');
refuses(() => parseData('"' + 'x'.repeat(65536) + '"'), '64KiB');
refuses(() => parseData('1e999'), 'nonfinite');
refuses(() => parseData('"\\uZZZZ"'), 'hexadecimal');
for (const pattern of ['(a)\\1', '(?=a)', '(?!a)', '(?<=a)', '(?<name>a)', '\\k<name>', '\\p{L}', '\\01'])
  refuses(() => compileRegular(pattern), 'unsupported');
refuses(() => compileRegular('a'.repeat(257)), 'pattern budget');
refuses(() => compileRegular('(a{256}){256}'), 'compiled state budget');
refuses(() => allMatches('(a+)+b', 'a'.repeat(100), makeMeter(1000)), 'transition budget');
refuses(() => allMatches('', 'x'.repeat(LIMITS.results)), 'result budget');
refuses(() => filterLines('a', 'x'.repeat(65537)), '64KiB');
same(allMatches('', '😀').map(m => m.index), [0, 1, 2]);
same(allMatches('\\uD83D', '😀').map(m => [m.index, m.end]), [[0, 1]]);
const html = highlight('<img src=x>prompt&', allMatches('prompt', '<img src=x>prompt&'), 0);
same(html, '&lt;img src=x&gt;<span class="current-match" style="background-color:#ff6b6b;color:#000">prompt</span>&amp;');
same(highlight('a', allMatches('', 'a')), '<span class="match" style="background-color:#ffeb3b;color:#000"></span>a<span class="match" style="background-color:#ffeb3b;color:#000"></span>');
const meter = makeMeter(); allMatches('(a+)+b', 'a'.repeat(10) + 'b', meter);
same(meter.remaining >= 0, true);
const state = initialState({text:'\nmatch\n',line_filter:true,line_filter_text:'^$'});
same(viewData(state).lineCounter,'2 lines');same(viewData(state).text,'\n');
state.line_filter_text='no-match';same(viewData(state).lineCounter,'0 lines');
updateText(state,"{prompt:'cat',steps:20,}");state.line_filter=false;togglePretty(state);
same(viewData(state).text,JSON.stringify({prompt:'cat',steps:20},null,2));
same(viewData(initialState(serializeState(state))).text,viewData(state).text);
same(positivePrompt('Positive: cat\nsecond line\n\nNegative: dog'),'cat\nsecond line');
same(positivePrompt('cat\nNegative prompt: dog\nSteps: 20'),'cat');
same(positivePrompt('Positive: (empty)\nNegative: no'),'');
refuses(()=>initialState({text:'x'.repeat(65537)}),'64KiB');
refuses(()=>initialState({font_size:73}),'font size');

const run = process.env.AMY_PROFILE_RUN || 'initial';
const modulePath = new URL('../web/viewer-profile.mjs', import.meta.url);
const sourcePath = new URL('../../web/Simple_Readable_Metadata_Text_Viewer_SG.js', import.meta.url);
const ref = path => { const bytes = fs.readFileSync(path); return { path: path.pathname, sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length }; };
const packet = { format: 'amy-readable-viewer-profile-controls-v1', run, node: process.version, checks, nativeComparisons,
  module: ref(modulePath), test: ref(new URL(import.meta.url)), pinnedViewer: ref(sourcePath), budgets: LIMITS,
  unicode: 'Default non-Unicode gi/i UTF-16, lone/pair surrogates and terminal zero width explicitly compared',
  nativeOldExecLoop: 'Original unsafe and interrupted zero-width diagnostic retained in ef3e5ffe proposal',
  execution: 'No metadata eval/getter/expression executed; native tests only on bounded tiny fixed/seeded patterns',
  frontendGuestOrWholePack: false, countIncrement: 0 };
const target = new URL(`file:///Users/ben/popbot/raw-chats/outputs/amy-oct8-readable-owned-viewer-profile-${run}.json`);
fs.writeFileSync(target, JSON.stringify(packet, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ checks, nativeComparisons, packet: target.pathname, sha256: crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex') }));
