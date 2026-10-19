import { comfy } from '/comfy/api/v2.js';
const IDS={"ttN tinyLoader": "ttN_tinyLoader_c80deffd6042c4a897866d79", "ttN conditioning": "ttN_conditioning_00ee7fb58d6217b61d28ffda", "ttN KSampler_v2": "ttN_KSampler_v2_b96111c6c532990ae4d2a22d", "ttN pipeLoader_v2": "ttN_pipeLoader_v2_58246dfb20bdc0271e2f0da1", "ttN pipeKSampler_v2": "ttN_pipeKSampler_v2_384e6bf1e6bdf16dab3403be", "ttN pipeKSamplerAdvanced_v2": "ttN_pipeKSamplerAdvanced_v2_0bde6a2fc6fd2b1f3148c941", "ttN pipeLoaderSDXL_v2": "ttN_pipeLoaderSDXL_v2_2315fee49000ac73ed2b4205", "ttN pipeKSamplerSDXL_v2": "ttN_pipeKSamplerSDXL_v2_d7a835b65f8b639485e83a20", "ttN advanced xyPlot": "ttN_advanced_xyPlot_5660b5693fff3e6a7b6ac6be", "ttN advPlot images": "ttN_advPlot_images_9464f7f009faedbbe64f8aee", "ttN advPlot range": "ttN_advPlot_range_ae4d61a6cbdb5c6824e46a98", "ttN advPlot string": "ttN_advPlot_string_abb8997c9782d24ce63175fb", "ttN advPlot combo": "ttN_advPlot_combo_2175b2f2a4848cce66909124", "ttN advPlot merge": "ttN_advPlot_merge_174e015dbe69c2712c571e31", "ttN pipeEDIT": "ttN_pipeEDIT_aa5a200004e9fb4314a1b528", "ttN pipe2BASIC": "ttN_pipe2BASIC_748c46ff86c489ba345bbb37", "ttN pipe2DETAILER": "ttN_pipe2DETAILER_fb799f9f4e6a3a0b893bacef", "ttN pipeEncodeConcat": "ttN_pipeEncodeConcat_7974130fa1ef7a3d6966bb0a", "ttN pipeLoraStack": "ttN_pipeLoraStack_2ec4cdc8dd3715945346a19e", "ttN multiModelMerge": "ttN_multiModelMerge_9930284c5606dcc14e190be2", "ttN debugInput": "ttN_debugInput_b1bdfd3890f7007c8f93b9a5", "ttN text": "ttN_text_17f67ffa52c37f580bb94011", "ttN textDebug": "ttN_textDebug_0be2c3c83aa3a0e9be121654", "ttN concat": "ttN_concat_98a12dae0cccc980d9c7b338", "ttN text3BOX_3WAYconcat": "ttN_text3BOX_3WAYconcat_d6bfacdd1e94a341253109a6", "ttN text7BOX_concat": "ttN_text7BOX_concat_e768585a58ce525b0095c15f", "ttN textCycleLine": "ttN_textCycleLine_07efecfd0109e56a0112fcc3", "ttN textOutput": "ttN_textOutput_561c7568d7a8609efb4c9c40", "ttN imageOutput": "ttN_imageOutput_9d7e52569d2d64b9e9e58352", "ttN imageREMBG": "ttN_imageREMBG_d75ef8a3e919f3bfc66f9795", "ttN hiresfixScale": "ttN_hiresfixScale_30b24f506f9af9321f1ae901", "ttN int": "ttN_int_3b12e0212a0b8b0be03416b7", "ttN float": "ttN_float_135744bce0eed7150cbe9f22", "ttN seed": "ttN_seed_0fffce90a3d1a81a1e11489e", "ttN xyPlot": "ttN_xyPlot_544de9d62d33978b709f2eee", "ttN pipeIN": "ttN_pipeIN_0f4a584cca428eb3e2db18ec", "ttN pipeOUT": "ttN_pipeOUT_ddb0379afad4f093ff872f5d", "ttN pipeLoader": "ttN_pipeLoader_b6c51abd124a0a79c7ba8c93", "ttN pipeKSampler": "ttN_pipeKSampler_aab002d291a2f516b9550bf3", "ttN pipeKSamplerAdvanced": "ttN_pipeKSamplerAdvanced_ba5a6ba9874ab2faac51c05a", "ttN pipeLoaderSDXL": "ttN_pipeLoaderSDXL_48a01436a42cd167b68fb47f", "ttN pipeKSamplerSDXL": "ttN_pipeKSamplerSDXL_a19bff1409f78f89af7781cd", "ttN compareInput": "ttN_compareInput_0cbbb1699b9e429b0a797dde"};
const textNodes=['ttN textDebug','ttN advPlot range','ttN advPlot string','ttN advPlot combo','ttN debugInput','ttN textOutput','ttN advPlot merge'];
for (const original of textNodes) comfy.defs.extend(IDS[original],b=>{
  b.addWidget({type:'textarea',name:'display',value:'',disabled:true,serialize:false});
  b.onExecuted((node,result)=>{
    const text=result.raw?.text ?? result.text ?? '';
    node.widgets.get('display')?.setValue(Array.isArray(text)?text.join(''):String(text));
  });
});
const seeded=['ttN pipeLoader_v2','ttN pipeKSampler_v2','ttN pipeKSamplerAdvanced_v2','ttN pipeLoaderSDXL_v2','ttN pipeKSamplerSDXL_v2','ttN KSampler_v2'];
for (const original of seeded) comfy.defs.extend(IDS[original],b=>{
  b.addWidget({type:'button',name:'🎲 New Fixed Random',serialize:false});
  b.onCreated(node=>{
    const seed=node.widgets.get('seed') ?? node.widgets.get('noise_seed');
    if (!seed) return;
    const control=node.widgets.get('control_after_generate') ?? node.widgets.get('control_before_generate');
    node.widgets.get('🎲 New Fixed Random')?.on('activate',()=>{
      const options=seed.getOptions() ?? {};
      const max=Math.min(1125899906842624, options.max ?? 1125899906842624);
      const min=Math.max(0,options.min ?? 0);
      const step=(options.step ?? 10)/10;
      const range=(max-min)/step;
      seed.setValue(Math.floor(Math.random()*range)*step+min);
      control?.setValue('fixed');
    });
    seed.setLinked(['🎲 New Fixed Random',...(control?[control.name]:[])]);
  });
});
// Match source beforeQueued: first serialization keeps the selected index.
const cycles=new Map();
comfy.defs.extend(IDS['ttN textCycleLine'],b=>{
  b.onCreated(node=>cycles.set(node.id,node));
  b.onConfigured(node=>cycles.set(node.id,node));
  b.onRemoved(node=>{ cycles.delete(node.id); queued.delete(node.id); });
});
const queued=new Set();
comfy.queue.onBeforeRun(()=>{
  for (const node of cycles.values()) {
    if (!queued.has(node.id)) { queued.add(node.id); continue; }
    const index=node.widgets.get('index'),control=node.widgets.get('index_control'),text=node.widgets.get('text');
    if (!index || !control || !text) continue;
    const mode=control.getValue(),min=Math.max(-1125899906842624,index.getOptions()?.min ?? 0);
    const max=Math.min(1125899906842624,String(text.getValue()).split('\n').length-1);
    let value=Number(index.getValue());
    if (mode==='increment') value+=1;
    if (mode==='decrement') value-=1;
    if (mode==='randomize') value=Math.floor(Math.random()*(max-min+1))+min;
    if (value<min)value=max;
    if (value>max)value=min;
    index.setValue(value);
  }
});
