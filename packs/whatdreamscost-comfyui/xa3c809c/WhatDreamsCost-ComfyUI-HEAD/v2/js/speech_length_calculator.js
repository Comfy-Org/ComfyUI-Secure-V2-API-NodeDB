import { comfy } from '/comfy/api/v2.js';

const TARGET = 'SpeechLengthCalculator';
const states = new Map();
const keyFor = (node) => `${String(node.graphId ?? '')}:${String(node.id)}`;

function calculate(text, fps, additionalTime) {
  const regex = /"([^"]*)"|'([^']*)'|“([^”]*)”|‘([^’]*)’/g;
  let match;
  let spoken = '';
  while ((match = regex.exec(String(text ?? ''))) !== null) {
    spoken += `${match[1] || match[2] || match[3] || match[4] || ''} `;
  }
  const wordCount = spoken.trim().split(/\s+/).filter(Boolean).length;
  const item = (wpm) => {
    const seconds = wordCount / wpm * 60 + additionalTime;
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.ceil((seconds % 60) * 10) / 10;
    return {
      time: minutes > 0 ? `${minutes}m ${remainder.toFixed(1)}s` : `${remainder.toFixed(1)}s`,
      frames: Math.ceil(seconds * fps),
    };
  };
  return { empty: wordCount === 0 && additionalTime === 0, wordCount, additionalTime, slow: item(100), average: item(130), fast: item(160) };
}

function element(doc, tag, className, text = '') {
  const value = doc.createElement(tag);
  value.className = className;
  if (text) value.textContent = text;
  return value;
}

function render(state) {
  if (!state.container) return;
  const doc = state.container.ownerDocument;
  const text = String(state.executedText ?? state.text.getValue() ?? '');
  const fps = Number(state.fps.getValue()) || 24;
  const additional = Number(state.additional.getValue()) || 0;
  const data = calculate(text, fps, additional);
  const root = element(doc, 'section', 'slc-ui-container');
  Object.assign(root.style, {
    minHeight: '260px', background: 'rgba(15,15,19,.7)', border: '1px solid rgba(255,255,255,.1)',
    borderRadius: '8px', padding: '12px', boxSizing: 'border-box', display: 'flex',
    flexDirection: 'column', gap: '8px', fontFamily: 'sans-serif', color: '#fff', overflow: 'hidden',
  });
  if (data.empty) {
    const empty = element(doc, 'div', 'slc-empty');
    Object.assign(empty.style, { flex: '1', display: 'grid', placeContent: 'center', textAlign: 'center', color: '#aaa' });
    empty.append(element(doc, 'div', '', 'Awaiting Script'), element(doc, 'small', '', 'Wrap spoken text inside "quotes"'));
    root.appendChild(empty);
  } else {
    const header = element(doc, 'div', 'slc-headers');
    Object.assign(header.style, { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' });
    for (const [title, value] of [['SPOKEN WORDS', data.wordCount], ['ADDED TIME', `${data.additionalTime}s`]]) {
      const block = element(doc, 'div', 'slc-header-block');
      Object.assign(block.style, { background: 'rgba(0,0,0,.4)', borderRadius: '6px', padding: '8px', textAlign: 'center' });
      block.append(element(doc, 'small', '', title), element(doc, 'div', '', String(value)));
      header.appendChild(block);
    }
    root.appendChild(header);
    for (const [label, wpm, value, color] of [
      ['SLOW', 100, data.slow, '#93c5fd'], ['AVG', 130, data.average, '#86efac'], ['FAST', 160, data.fast, '#fca5a5'],
    ]) {
      const card = element(doc, 'div', 'slc-card');
      Object.assign(card.style, { display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderLeft: `4px solid ${color}`, background: 'rgba(0,0,0,.25)', borderRadius: '4px' });
      const left = element(doc, 'div', '');
      left.append(element(doc, 'strong', '', label), element(doc, 'div', '', `${wpm} WPM`));
      const right = element(doc, 'div', '');
      Object.assign(right.style, { textAlign: 'right' });
      right.append(element(doc, 'strong', '', value.time), element(doc, 'div', '', `${value.frames} frames`));
      card.append(left, right);
      root.appendChild(card);
    }
    root.appendChild(element(doc, 'small', '', 'WPM = Words Per Minute'));
  }
  state.container.replaceChildren(root);
}

comfy.defs.extend(TARGET, (builder) => {
  builder.onCreated((node) => {
    const state = {
      node,
      text: node.widgets.get('text'),
      fps: node.widgets.get('fps'),
      additional: node.widgets.get('additional_time'),
      executedText: undefined,
      container: null,
      unsubscribers: [],
    };
    states.set(keyFor(node), state);
    for (const widget of [state.text, state.fps, state.additional]) {
      if (widget) state.unsubscribers.push(widget.on('change', () => { state.executedText = undefined; render(state); }));
    }
    node.widgets.mount({
      name: 'speech_length_stats', height: 280, hideOnZoom: false, serialize: false, sendToPrompt: false,
      render(container) { state.container = container; render(state); },
      destroy() { state.container?.replaceChildren(); state.container = null; },
    });
    node.setSizeConstraints({ minWidth: 340, minHeight: 500, autoHeight: true });
    const size = node.getSize();
    node.setSize({ width: Math.max(340, size.width), height: Math.max(500, size.height) });
  });

  builder.onExecuted((node, result) => {
    const state = states.get(keyFor(node));
    const payload = result.raw?.speech_length?.[0];
    if (!state || !payload) return;
    state.executedText = String(payload.text ?? '');
    render(state);
  });

  builder.onConfigured((node) => render(states.get(keyFor(node))));
  builder.onRemoved((node) => {
    const key = keyFor(node);
    const state = states.get(key);
    if (!state) return;
    for (const unsubscribe of state.unsubscribers) unsubscribe();
    state.container?.replaceChildren();
    states.delete(key);
  });
});
