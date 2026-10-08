import { comfy } from '/comfy/api/v2.js';
import { ProfileError } from './viewer-profile.mjs';
import { initialState, serializeState, updateText, viewData, togglePretty, admittedText, positivePrompt, exportName } from './viewer-state.mjs';
const states = new Map();
async function selection(state) {
  const element = comfy.element(state.elementName, {nodeId: state.ownerNodeId, widget: 'textDisplay'});
  const start = await element.get('selectionStart'), end = await element.get('selectionEnd');
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end < start || end > state.visibleText.length)
    throw new ProfileError('invalid owned textarea selection');
  return { start, end };
}
async function selectRange(state, start, end) {
  if (state.closed) return;
  const element = comfy.element(state.elementName, {nodeId: state.ownerNodeId, widget: 'textDisplay'});
  await element.invoke('focus');
  if (!state.closed) await element.invoke('setSelectionRange', start, end);
}
comfy.defs.extend('Simple Readable Metadata Text Viewer-SG', builder => {
  builder.onCreated(node => {
    const state = initialState(node.getProperties()); state.ownerNodeId = node.id; state.elementName = `srm-viewer-${node.id}`; states.set(node.id,state);
    const disposers = []; state.disposers = disposers;
    node.setSizeConstraints({ minWidth: 200, minHeight: 100, maxHeight: 2000 });
    const save = () => { if (!state.closed) for (const [key,value] of Object.entries(serializeState(state))) node.setProperty(key,value); };
    let box, marks, counter, status, matchCounter, lineCounter, toolbar, search, lineFilter, font, confirm;
    const render = () => {
      if (state.closed || !box) return;
      try {
        const data = viewData(state);
        // Native textarea .value normalizes CR/CRLF to LF. Selection and copy
        // indices must refer to that displayed UTF-16 value, not markup bytes.
        state.visibleText = data.text.replaceAll('\r\n','\n').replaceAll('\r','\n'); state.matches = data.matches;
        // A textarea's declared markup value is its text child, not a value
        // attribute. Keep both the guest event snapshot and host markup exact.
        // HTML parsing strips exactly one initial LF in textarea markup.
        // Compensate only in the serialized child; the event value stays exact.
        box.textContent = /^[\r\n]/.test(data.text) ? '\n' + data.text : data.text;
        box.value = data.text; marks.innerHTML = data.marked; counter.textContent = data.counter;
        matchCounter.textContent = data.matchCounter; lineCounter.textContent = data.lineCounter;
        state.status = '';
      } catch (error) {
        state.status = String(error.message); marks.innerHTML = ''; state.matches = [];
        matchCounter.textContent = '0 / 0';
      }
      const bg = state.theme === 'Light' ? '#ffffff' : '#1e1e1e', fg = state.theme === 'Light' ? '#000000' : '#d4d4d4';
      box.style.cssText = `width:100%;height:240px;padding:0;border:0;box-sizing:border-box;background:${bg};color:${fg};font:${state.font_size}px monospace;line-height:1.5;white-space:${state.word_wrap ? 'pre-wrap' : 'pre'};overflow-wrap:${state.word_wrap ? 'break-word' : 'normal'}`;
      marks.style.cssText = `font:${state.font_size}px monospace;white-space:${state.word_wrap ? 'pre-wrap' : 'pre'};background:${bg};color:${fg};max-height:240px;overflow:auto;display:${state.text_filter ? 'block' : 'none'}`;
      search.value = state.filter_text; lineFilter.value = state.line_filter_text; font.value = String(state.font_size);
      confirm.style.display = state.confirmDelete ? 'block' : 'none'; status.textContent = state.status; save();
    };
    state.render = render;
    node.widgets.mount({ name:'textDisplay', serialize:false, sendToPrompt:false,
      render(container) {
        const doc = container.ownerDocument;
        const element = (tag, text) => { const el = doc.createElement(tag); if (text !== undefined) el.textContent = text; return el; };
        const listen = (el, event, fn) => { el.addEventListener(event,fn); disposers.push(() => el.removeEventListener(event,fn)); };
        counter = element('div'); toolbar = element('div'); toolbar.style.cssText='display:flex;gap:3px;flex-wrap:wrap';
        status = element('div'); status.setAttribute('data-testid','viewer-status');
        box = element('textarea'); box.setAttribute('readonly',''); box.setAttribute('data-name',state.elementName); box.placeholder='No text connected...';
        state.box = box;
        marks = element('pre'); marks.setAttribute('data-testid','viewer-highlights');
        matchCounter = element('span','0 / 0'); lineCounter = element('span','0 lines');
        search=element('input'); search.type='text'; search.placeholder='Regex highlight'; search.setAttribute('data-testid','viewer-search-input');
        lineFilter=element('input'); lineFilter.type='text'; lineFilter.placeholder='Regex line filter'; lineFilter.setAttribute('data-testid','viewer-line-filter');
        font=element('input'); font.type='number'; font.min='6'; font.max='72'; font.setAttribute('data-testid','viewer-font');
        confirm=element('div','Delete all text? This cannot be undone.');
        const action = (name, fn, parent = toolbar) => {
          const button=element('button',name); button.setAttribute('data-testid',`viewer-${name.toLowerCase().replaceAll(' ','-')}`);
          listen(button,'click',async()=>{
            if(state.closed)return;
            try { await fn(); if(!state.closed)render(); }
            catch(error){if(!state.closed){state.status=String(error.message);status.textContent=state.status;}}
          }); parent.append(button); return button;
        };
        action('Theme',()=>{state.theme=state.theme==='Dark'?'Light':'Dark';});
        action('Copy',async()=>{const revision=state.revision,range=await selection(state);if(state.closed||revision!==state.revision)return;
          const text=state.visibleText;await comfy.clipboard.writeText(range.start!==range.end?text.substring(range.start,range.end):text);});
        action('Wrap',()=>{state.word_wrap=!state.word_wrap;});
        action('Search',()=>{state.text_filter=!state.text_filter;if(!state.text_filter){state.filter_text='';state.current=-1;}});
        action('Filter',()=>{state.line_filter=!state.line_filter;if(!state.line_filter)state.line_filter_text='';});
        action('Export',async()=>{const data=new TextEncoder().encode(admittedText(state.visibleText));await comfy.files.download({name:exportName(),mimeType:'text/plain',bytes:data});});
        action('Pretty',()=>togglePretty(state));
        action('Select All',async()=>selectRange(state,0,state.visibleText.length));
        action('Paste',async()=>{
          const revision=state.revision,range=await selection(state),text=await comfy.clipboard.readText();
          if(state.closed||state.revision!==revision)return;
          const next=admittedText(state.visibleText.substring(0,range.start)+text+state.visibleText.substring(range.end));
          updateText(state,next);node.widgets.get('text')?.setValue(next);render();await selectRange(state,range.start+text.length,range.start+text.length);
        });
        action('Delete',()=>{state.confirmDelete=!state.confirmDelete;});
        action('Confirm Delete',()=>{updateText(state,'');node.widgets.get('text')?.setValue('');state.filter_text='';state.line_filter_text='';state.confirmDelete=false;},confirm);
        action('Cancel',()=>{state.confirmDelete=false;},confirm);
        action('Copy Positive',async()=>{const text=positivePrompt(state.visibleText);if(text)await comfy.clipboard.writeText(text);});
        const navigate=async delta=>{
          if(!state.matches?.length)return;
          state.current=(state.current+delta+state.matches.length)%state.matches.length;
          const line=state.visibleText.substring(0,state.matches[state.current].index).split('\n').length-1;
          // This owned mounted viewport is exactly 240px, with no padding/border.
          await comfy.element(state.elementName, {nodeId: state.ownerNodeId, widget: 'textDisplay'}).set('scrollTop',line*state.font_size*1.5-120);
        };
        action('Previous',()=>navigate(-1));action('Next',()=>navigate(1));
        listen(search,'input',()=>{state.filter_text=admittedText(search.value);state.current=-1;render();if(state.matches?.length){state.current=0;render();}});
        listen(lineFilter,'input',()=>{state.line_filter_text=admittedText(lineFilter.value);render();});
        listen(font,'change',()=>{const size=parseInt(font.value);if(Number.isInteger(size)&&size>=6&&size<=72){state.font_size=size;render();}else{state.status='Font size must be 6..72';status.textContent=state.status;}});
        listen(search,'keydown',async event=>{if(event.key==='Enter'){event.preventDefault();try{await navigate(event.shiftKey?-1:1);render();}catch(error){state.status=String(error.message);status.textContent=state.status;}}});
        container.append(counter,toolbar,search,matchCounter,lineFilter,lineCounter,font,confirm,box,marks,status);render();
      },
      destroy(){if(state.closed)return;state.closed=true;state.revision++;for(const off of disposers.splice(0))off();state.box=undefined;},
    });
  });
  builder.onExecuted((node,result)=>{const state=states.get(node.id);if(!state)return;const raw=result?.raw?.text??result?.text;
    if(Array.isArray(raw)&&raw.length){updateText(state,typeof raw[0]==='string'?raw[0]:Array.isArray(raw[0])?raw[0].join('\n'):'');state.render();}});
  builder.onConfigured((node,info)=>{const state=states.get(node.id);if(!state)return;const revision=state.revision+1;Object.assign(state,initialState(info.properties??node.getProperties()));state.revision=revision;state.render();});
  builder.onSerialize(node=>{const state=states.get(node.id);return state?{properties:serializeState(state)}:{};});
  builder.onRemoved(node=>{const state=states.get(node.id);if(state){state.closed=true;state.revision++;for(const off of state.disposers.splice(0))off();}states.delete(node.id);});
});
