import { comfy } from "/comfy/api/v2.js";
export const NODE_ID = "jupo.AspectRatios.AspectRatios";
const views = new WeakMap();
function gcd(a,b) { while (b) [a,b]=[b,a%b]; return a; }
export function calculate(base, fixed, step, aw, ah) {
  for (const v of [base,step,aw,ah]) if (!Number.isSafeInteger(v) || v<=0 || v>8192) throw new Error("invalid geometry");
  let w,h;
  if (fixed === "none") { w=Math.sqrt(base**2*(aw/ah)); h=w/(aw/ah); }
  else if (((fixed === "short") && aw<=ah) || ((fixed !== "short") && aw>ah)) { w=base; h=base*ah/aw; }
  else { h=base; w=base*aw/ah; }
  const sw=fixed==="none"?step*aw/gcd(step,aw):step;
  const sh=fixed==="none"?step*ah/gcd(step,ah):step;
  return [Math.floor(w/sw)*sw,Math.floor(h/sh)*sh];
}
export function preset(value) {
  if (value==="none") return null;
  if (typeof value!=="string" || value.length>128) throw new Error("invalid preset");
  const text=value.split("]").at(-1).trim();
  if (!/^\d+:\d+$/.test(text)) throw new Error("invalid preset");
  const result=text.split(":").map(Number);
  if (result.some(v=>!Number.isSafeInteger(v)||v<1||v>4096)) throw new Error("invalid preset");
  return result;
}
function destroy(node) { views.get(node)?.destroy(); views.delete(node); }
comfy.defs.extend(NODE_ID, builder => {
  builder.onCreated(node => {
    if (node.widgets.get("switch ⇅")) node.widgets.remove("switch ⇅");
    const button=node.widgets.add({type:"button",name:"switch ⇅",serialize:false});
    const mounted=node.widgets.mount({name:"result",defaultValue:null,serialize:false,sendToPrompt:false,
      render(container) {
        destroy(node);
        const doc=container.ownerDocument;
        const output=doc.createElement("div");
        output.style.height="82px";
        output.style.whiteSpace="pre-line";
        output.setAttribute("aria-label","Aspect ratio resolution");
        container.replaceChildren(output);
        const widget=name=>node.widgets.get(name);
        let active=true,busy=false;
        const update=()=>{
          if (!active) return;
          try {
            const [w,h]=calculate(...["base","fixed_side","step","aspect_w","aspect_h"].map(name=>widget(name)?.getValue()));
            output.textContent=`width: ${w}\nheight: ${h}`;
          } catch { output.textContent="Invalid dimensions"; }
        };
        const changePreset=value=>{
          if (!active || busy) return;
          try {
            const pair=preset(value);
            if (pair) { busy=true;widget("aspect_w")?.setValue(pair[0]);widget("aspect_h")?.setValue(pair[1]);busy=false;update(); }
          } catch { busy=false;output.textContent="Invalid preset"; }
        };
        const stops=["base","fixed_side","step","aspect_w","aspect_h"].map(name=>widget(name)?.on("change",()=>{if(!busy)update();}));
        stops.push(widget("preset")?.on("change",changePreset));
        stops.push(button.on("activate",()=>{
          if(!active)return;
          const aw=widget("aspect_w"),ah=widget("aspect_h");
          const old=aw?.getValue();busy=true;aw?.setValue(ah?.getValue());ah?.setValue(old);busy=false;update();
        }));
        views.set(node,{update,destroy(){if(!active)return;active=false;for(const stop of stops)stop?.();container.replaceChildren();}});
        update();
      },destroy(){destroy(node);}});
    mounted.setHeight(82);
  });
  builder.onConfigured(node=>views.get(node)?.update());
  builder.onRemoved(node=>destroy(node));
});
