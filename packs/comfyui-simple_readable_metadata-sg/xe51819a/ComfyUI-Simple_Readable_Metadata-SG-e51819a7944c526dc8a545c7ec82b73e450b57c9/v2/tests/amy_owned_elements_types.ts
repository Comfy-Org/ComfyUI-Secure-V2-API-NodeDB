import type {Comfy, OwnedElementScope} from '../comfy-api';
declare const comfy: Comfy;
const scope: OwnedElementScope = {nodeId:'1',widget:'textDisplay'};
const handle = comfy.element('ordinary-name',scope);
const selected: Promise<number> = handle.get('selectionStart');
const natural: Promise<number> = comfy.element('image',{nodeId:'2',widget:'metadata_preview'}).get('naturalWidth');
const off = handle.listen('input', detail => { const value: string|undefined = detail.value; void value; });
void selected; void natural; void off;
// @ts-expect-error Scope requires canonical string ID.
comfy.element('x',{nodeId:1,widget:'textDisplay'});
// @ts-expect-error Mount owner is mandatory when specifying a scope.
comfy.element('x',{nodeId:'1'});
// @ts-expect-error No arbitrary DOM method.
handle.invoke('querySelector','body');
// @ts-expect-error No private host property.
handle.get('ownerDocument');
// @ts-expect-error Closed event set.
handle.listen('arbitrary-event',()=>{});
