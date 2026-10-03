import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';


function assert(value, message) {
  if (!value) throw new Error(`ASSERT: ${message}`);
}


const here = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(here, '../js/video_preview.js');
const registrations = [];
const comfy = {
  backend: { url: (value) => `secure:${value}` },
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({ onExecuted: (handler) => { hooks.onExecuted = handler; } });
      registrations.push({ type, hooks });
    },
  },
};
const created = [];
const document = {
  createElement(tag) {
    const listeners = {};
    const element = {
      tagName: String(tag).toUpperCase(),
      style: {},
      addEventListener(name, handler) { listeners[name] = handler; },
      play() { element.played = true; return Promise.resolve(); },
      pause() { element.paused = true; },
      listeners,
    };
    created.push(element);
    return element;
  },
};
const context = vm.createContext({ console, document, URL, URLSearchParams });
const module = new vm.SourceTextModule(readFileSync(sourcePath, 'utf8'), {
  context,
  identifier: sourcePath,
});
await module.link((specifier) => {
  assert(specifier === '/comfy/api/v2.js', `unexpected import ${specifier}`);
  return new vm.SyntheticModule(['comfy'], function () {
    this.setExport('comfy', comfy);
  }, { context, identifier: specifier });
});
await module.evaluate();

assert(registrations.length === 2, 'expected both overlay definitions');
assert(registrations[0].type === 'VideoOverlayNode', 'base node missing');
assert(registrations[1].type === 'VideoOverlayWithSubtitlesNode', 'subtitle node missing');

for (const registration of registrations) {
  let mounted;
  let constraints;
  const node = {
    widgets: {
      remove() {},
      mount(spec) { mounted = spec; },
    },
    setSizeConstraints(value) { constraints = value; },
  };
  registration.hooks.onExecuted(node, {
    raw: {
      gifs: [{ filename: 'clip.mp4', type: 'output', subfolder: 'video' }],
    },
  });
  assert(mounted?.name === 'video_overlay_preview', 'preview was not mounted');
  assert(mounted.serialize === false, 'preview must not serialize');
  assert(constraints?.autoHeight === true, 'preview did not request auto height');
  const children = [];
  mounted.render({ style: {}, append(child) { children.push(child); } });
  assert(children.length === 1 && children[0].tagName === 'VIDEO', 'video element missing');
  assert(children[0].src.includes('filename=clip.mp4'), 'managed media URL missing');
  assert(typeof children[0].listeners.mouseenter === 'function', 'hover play missing');
  assert(typeof children[0].listeners.mouseleave === 'function', 'hover pause missing');
}

assert(created.length === 2, 'unexpected DOM ownership');
console.log('VideoOverlayFFmpeg preview harness: PASS');
