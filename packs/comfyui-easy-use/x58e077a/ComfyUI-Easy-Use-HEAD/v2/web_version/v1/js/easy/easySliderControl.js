import { comfy } from '/comfy/api/v2.js';
import { $el, sleep } from "../common/utils.js";


const calculatePercent = (value, min, max) => ((value-min)/(max-min)*100)

const getLayerDefaultValue = (index) => {
    switch (index){
        case 3:
            return 2.5
        case 6:
            return 1
        default:
            return 0
    }
}

// properties.values stays the source of truth, exactly as before; these two
// keep the mounted widget's value cell — which is what reaches widgets_values
// and the prompt — in step with it.
const writeValues = (_this) => {
    const widget = _this.widgets.get('values')
    if (widget) widget.setValue((_this.getProperties()['values'] || []).join(','))
}
const setLayerValue = (_this, i, value) => {
    const values = [...(_this.getProperties()['values'] || [])]
    values[i] = i+':'+value
    _this.setProperty('values', values)
    writeValues(_this)
}

const addLayer = (_this, layer_total, arrays, sliders, i) => {
    let scroll = $el('div.easyuse-slider-item-scroll')
    let value = $el('div.easyuse-slider-item-input', {textContent: arrays[i]['value']})
    let label = $el('div.easyuse-slider-item-label', {textContent: 'L'+i})
    let girdTotal = (arrays[i]['max'] - arrays[i]['min']) / arrays[i]['step']
    let area = $el('div.easyuse-slider-item-area', {style:{ height: calculatePercent(arrays[i]['default'],arrays[i]['min'],arrays[i]['max']) + '%'}})
    let bar = $el('div.easyuse-slider-item-bar', {
        style:{ top: (100-calculatePercent(arrays[i]['default'],arrays[i]['min'],arrays[i]['max'])) + '%'},
        onmousedown: (e) => {
            let event = e || window.event;
            var y = event.clientY - bar.offsetTop;
            document.onmousemove = (e) => {
                let event = e || window.event;
                let top = event.clientY - y;
                if(top < 0){
                    top = 0;
                }
                else if(top > scroll.offsetHeight - bar.offsetHeight){
                    top = scroll.offsetHeight - bar.offsetHeight;
                }
                // top到最近的girdHeight值
                let girlHeight = (scroll.offsetHeight - bar.offsetHeight)/ girdTotal
                top = Math.round(top / girlHeight) * girlHeight;
                bar.style.top = Math.floor(top/(scroll.offsetHeight - bar.offsetHeight)* 100) + '%';
                area.style.height = Math.floor((scroll.offsetHeight - bar.offsetHeight - top)/(scroll.offsetHeight - bar.offsetHeight)* 100) + '%';
                value.innerText = parseFloat(parseFloat(arrays[i]['max'] - (arrays[i]['max']-arrays[i]['min']) * (top/(scroll.offsetHeight - bar.offsetHeight))).toFixed(2))
                arrays[i]['value'] = value.innerText
                setLayerValue(_this, i, value.innerText)
                window.getSelection ? window.getSelection().removeAllRanges() : document.selection.empty();
            }
        },
        ondblclick:_=>{
            bar.style.top = (100-calculatePercent(arrays[i]['default'],arrays[i]['min'],arrays[i]['max'])) + '%'
            area.style.height = calculatePercent(arrays[i]['default'],arrays[i]['min'],arrays[i]['max']) + '%'
            value.innerText = arrays[i]['default']
            arrays[i]['value'] = arrays[i]['default']
            setLayerValue(_this, i, value.innerText)
        }
    })
    document.onmouseup = _=> document.onmousemove = null;

    scroll.replaceChildren(bar,area)
    let item_div = $el('div.easyuse-slider-item',[
        value,
        scroll,
        label
    ])
    if(i == 3 ) layer_total == 12 ? item_div.classList.add('negative') : item_div.classList.remove('negative')
    else if(i == 6) layer_total == 12 ?  item_div.classList.add('positive') : item_div.classList.remove('positive')
    sliders.push(item_div)
    return item_div
}

const setSliderValue = (_this, type, refresh=false, values_div, sliders_value) => {
    let layer_total = type == 'sdxl' ? 12 : 16
    let sliders = []
    let arrays = Array.from({length: layer_total}, (v, i) => ({default: layer_total == 12 ? getLayerDefaultValue(i) : 0, min: -1, max: 3, step: 0.05, value:layer_total == 12 ? getLayerDefaultValue(i) : 0}))
    _this.setProperty("values", Array.from({length: layer_total}, (v, i) => i+':'+arrays[i]['value']))
    for (let i = 0; i < layer_total; i++) {
        addLayer(_this, layer_total, arrays, sliders, i)
    }
    if(refresh) values_div.replaceChildren(...sliders)
    else{
        values_div = $el('div.easyuse-slider', sliders)
        // The old widget had a value getter that recomputed the string from
        // properties.values on every read. A mounted widget owns a real value
        // cell, so it is written whenever a bar moves instead.
        sliders_value = _this.widgets.mount({
            name: 'values',
            defaultValue: '',
            render(container) {
                container.append(values_div)
            }
        })
    }
    writeValues(_this)
    return {sliders, arrays, values_div, sliders_value}
}


comfy.defs.extend('easy sliderControl', (b) => {

    // 创建时
    b.onCreated((node) => {
        const mode =  node.widgets.at(0);
        const model_type = node.widgets.at(1);
        let _this = node
        let values_div = null
        let sliders_value = null
        mode.on('change', () => {
            switch (mode.getValue()) {
                case 'ipadapter layer weights':
                    _this.outputs.at(0).modify({ name: 'layer_weights', label: 'layer_weights' })
                    break
            }
        })

        model_type.on('change', () => {
            if(values_div) {
                let r2 = setSliderValue(_this, model_type.getValue(), true, values_div, sliders_value)
                values_div = r2.values_div
                sliders_value = r2.sliders_value
            }
            _this.setSize(model_type.getValue() == 'sdxl' ? {width:375, height:320} : {width:455, height:320})
        })

        let r1 =  setSliderValue(_this, model_type.getValue(), false, values_div, sliders_value)
        let sliders = r1.sliders
        let arrays = r1.arrays
        values_div = r1.values_div
        sliders_value = r1.sliders_value
        setTimeout(_=>{
            let old_values_widget = node.widgets.get('values');
            if(old_values_widget){
                let old_value = String(old_values_widget.getValue() || '').split(',')
                let layer_total = _this.widgets.at(1).getValue() == 'sdxl' ? 12 : 16
                for (let i = 0; i < layer_total; i++) {
                    if(!old_value[i]) continue
                    let value = parseFloat(parseFloat(old_value[i].split(':')[1]).toFixed(2))
                    let item_div = sliders[i] || null
                     // 存在层即修改
                    if(arrays[i]){
                       arrays[i]['value'] = value
                        setLayerValue(_this, i, value)
                    }else{
                        arrays.push({default: layer_total == 12 ? getLayerDefaultValue(i) : 0, min: -1, max: 3, step: 0.05, value:layer_total == 12 ? getLayerDefaultValue(i) : 0})
                        setLayerValue(_this, i, arrays[i]['value'])
                        // 添加缺失层
                        item_div = addLayer(_this, layer_total, arrays, sliders, i)
                        values_div.appendChild(item_div)
                    }
                    // todo: 修改bar位置等
                    let input = item_div.getElementsByClassName('easyuse-slider-item-input')[0]
                    let bar = item_div.getElementsByClassName('easyuse-slider-item-bar')[0]
                    let area = item_div.getElementsByClassName('easyuse-slider-item-area')[0]
                    if(i == 3 ) layer_total == 12 ? item_div.classList.add('negative') : item_div.classList.remove('negative')
                    else if(i == 6) layer_total == 12 ?  item_div.classList.add('positive') : item_div.classList.remove('positive')
                    input.textContent = value
                    bar.style.top = (100-calculatePercent(value,arrays[i]['min'],arrays[i]['max'])) + '%'
                    area.style.height = calculatePercent(value,arrays[i]['min'],arrays[i]['max']) + '%'
                }
            }
            _this.setSize(model_type.getValue() == 'sdxl' ? {width:375, height:320} : {width:455, height:320})
        },1)
    })
})
