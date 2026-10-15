import { useRemoteWidget } from '/Users/ben/comfy/ComfyUI_frontend-secure-nodes/src/renderer/extensions/vueNodes/widgets/composables/useRemoteWidget.ts'
import schemas from '../source-schema.json'
const bundled = schemas.Wildcards.inputs.required.textfile[0]
const route = '/secure-nodes/text-files/input?prefix=chibi-wildcards/&suffix=.txt'
const make = (statics) => {
  const select = document.createElement('select')
  document.body.append(select)
  const widget = { name: 'textfile', type: 'combo', value: statics[0], options: {} }
  const node = { addWidget: (type, name, value, callback) => ({type, name, value, callback}), graph: {setDirtyCanvas(){}} }
  const hook = useRemoteWidget({remoteConfig: {route,static_options:statics,control_after_refresh:'last'},defaultValue:statics[0],node,widget})
  const paint = () => {
    select.replaceChildren(...hook.getCachedValue().map(value => {
      const option = document.createElement('option');option.textContent=value;option.value=value;return option
    }))
    select.value=widget.value
  }
  widget.callback=paint
  const resolve = async () => {
    await hook.getCacheEntry()?.fetchPromise
    await new Promise(done => hook.getValue(() => {paint();done()}))
  }
  return {hook,select,resolve}
}
window.catalogueProof=(async()=>{
  const a=make(bundled);await a.resolve()
  const capture=()=>({values:Array.from(a.select.options,x=>x.value),selected:a.select.value})
  const initial=capture()
  const b=make(['other.txt']);await b.resolve()
  const isolated=Array.from(b.select.options,x=>x.value)
  const raw=a.hook.getCacheEntry().data
  await fetch('/state',{method:'POST',body:JSON.stringify(['chibi-wildcards/current.txt'])})
  a.hook.refreshValue();await a.resolve();const refreshed=capture()
  await fetch('/state',{method:'POST',body:'[]'})
  a.hook.refreshValue();await a.resolve();const empty=capture()
  return {bundled,initial,isolated,raw,refreshed,empty}
})()
