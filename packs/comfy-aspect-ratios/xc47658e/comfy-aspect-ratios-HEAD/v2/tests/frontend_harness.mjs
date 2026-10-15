import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const [file,matrixFile]=process.argv.slice(2);
const source=fs.readFileSync(file,"utf8");
for (const pattern of [/fetch\s*\(/,/window\./,/\bdocument\./,/innerHTML/,/app\./,/prototype/,/localStorage/,/addEventListener/]) assert.doesNotMatch(source,pattern);
let hooks={},registrations=0;
const comfy={defs:{extend(id,configure){assert.equal(id,"jupo.AspectRatios.AspectRatios");registrations++;configure({onCreated:f=>hooks.created=f,onConfigured:f=>hooks.configured=f,onRemoved:f=>hooks.removed=f});}}};
const context=vm.createContext({});
const module=new vm.SourceTextModule(source,{context});
await module.link(async id=>{assert.equal(id,"/comfy/api/v2.js");const m=new vm.SyntheticModule(["comfy"],function(){this.setExport("comfy",comfy);},{context});await m.link(()=>{});return m;});
await module.evaluate();
assert.equal(registrations,1);
for (const [args,expected] of JSON.parse(fs.readFileSync(matrixFile,"utf8"))) assert.deepEqual(Array.from(module.namespace.calculate(...args)),expected);
assert.equal(module.namespace.preset("none"),null);
assert.deepEqual(Array.from(module.namespace.preset("[portrait] 7:9")),[7,9]);
for (const [w,h] of [[3,1],[7,4],[19,13],[3,2],[7,5],[9,7],[4,3],[1,1],[3,4],[7,9],[5,7],[2,3],[13,19],[4,7],[1,3]]) assert.deepEqual(Array.from(module.namespace.preset(`[any] ${w}:${h}`)),[w,h]);
assert.throws(()=>module.namespace.preset("<script>"));
class Widget {
 constructor(value){this.value=value;this.events=new Map();}
 getValue(){return this.value;}
 setValue(value){this.value=value;this.emit("change",value);}
 emit(event,value){for(const f of this.events.get(event)||[])f(value);}
 on(event,f){if(!this.events.has(event))this.events.set(event,new Set());this.events.get(event).add(f);return()=>this.events.get(event).delete(f);}
}
const doc={createElement(){return {style:{},textContent:"",setAttribute(){}};}};
function makeNode(values={}) {
 const map=new Map(Object.entries({base:1024,fixed_side:"none",step:8,aspect_w:1,aspect_h:1,preset:"none",...values}).map(([n,v])=>[n,new Widget(v)]));
 const node={widgets:{get:n=>map.get(n),remove:n=>map.delete(n),add(def){const widget=new Widget(null);map.set(def.name,widget);return widget;},mount(def){node.mount=def;node.container={ownerDocument:doc,children:[],replaceChildren(...values){this.children=values;}};def.render(node.container);return {setHeight(){}};}}};
 hooks.created(node);return node;
}
function text(n){return n.container.children[0].textContent;}
function active(n){return [...n.widgets.get("base").events.values()].reduce((n,s)=>n+s.size,0);}
const a=makeNode(),b=makeNode({base:512});
assert.equal(text(a),"width: 1024\nheight: 1024");assert.equal(text(b),"width: 512\nheight: 512");
a.widgets.get("preset").setValue("[portrait] 7:9");
assert.equal(a.widgets.get("aspect_w").getValue(),7);assert.equal(a.widgets.get("aspect_h").getValue(),9);
const old=text(a);a.widgets.get("switch ⇅").emit("activate");assert.equal(a.widgets.get("aspect_w").getValue(),9);assert.equal(a.widgets.get("aspect_h").getValue(),7);assert.notEqual(text(a),old);
assert.equal(text(b),"width: 512\nheight: 512");
a.widgets.get("preset").setValue("none");assert.equal(a.widgets.get("aspect_w").getValue(),9);
a.widgets.get("base").setValue(NaN);assert.equal(text(a),"Invalid dimensions");
a.widgets.get("base").setValue(256);hooks.configured(a);assert.match(text(a),/^width:/);
const container=a.container;a.mount.render(container);assert.equal(active(a),1);
hooks.removed(a);hooks.removed(a);a.mount.destroy();assert.equal(active(a),0);assert.equal(container.children.length,0);
a.widgets.get("base").setValue(1024);assert.equal(container.children.length,0);
hooks.created(a);assert.equal(active(a),1);assert.equal([...a.widgets.get("switch ⇅").events.get("activate")].length,1);
hooks.removed(a);hooks.removed(b);
const restored=makeNode({base:768,aspect_w:3,aspect_h:4,preset:"none"});hooks.configured(restored);assert.notEqual(text(restored),text(makeNode()));hooks.removed(restored);
console.log("frontend differential/lifecycle PASS");
