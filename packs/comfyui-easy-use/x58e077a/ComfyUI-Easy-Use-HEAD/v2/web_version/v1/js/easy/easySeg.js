import { comfy } from '/comfy/api/v2.js';
import {$t} from "../common/i18n.js";
import {findWidgetByName, toggleWidget} from "../common/utils.js";


const tags = {
    "selfie_multiclass_256x256": ["Background", "Hair", "Body", "Face", "Clothes", "Others",],
    "human_parsing_lip":["Background","Hat","Hair","Glove","Sunglasses","Upper-clothes","Dress","Coat","Socks","Pants","Jumpsuits","Scarf","Skirt","Face","Left-arm","Right-arm","Left-leg","Right-leg","Left-shoe","Right-shoe"],
    "segformer_b3_clothes": ["Background", "Hat", "Hair", "Sunglasses", "Upper-clothes", "Skirt", "Pants", "Dress", "Belt", "Left-shoe", "Right-shoe", "Face", "Left-leg", "Right-leg", "Left-arm", "Right-arm", "Bag", "Scarf"],
    "segformer_b3_fashion": ["Unlabelled", "shirt, blouse", "top, t-shirt, sweatshirt", "sweater", "cardigan", "jacket", "vest", "pants", "shorts", "skirt", "coat", "dress", "jumpsuit", "cape", "glasses", "hat", "headband, head covering, hair accessory", "tie", "glove", "watch", "belt", "leg warmer", "tights, stockings", "sock", "shoe", "bag, wallet", "scarf", "umbrella", "hood", "collar", "lapel", "epaulette", "sleeve", "pocket", "neckline", "buckle", "zipper", "applique", "bead", "bow", "flower", "fringe", "ribbon", "rivet", "ruffle", "sequin", "tassel"],
    "face_parsing": ["background", "skin", "nose", "eyeglasses", "left_eye", "right_eye", "left_eyebrow", "right_eyebrow", "left_ear", "right_ear", "mouth", "upper_lip", "lower_lip", "hair", "hat", "earring", "necklace", "neck", "clothing"],
}
function getTagList(tags) {
    let rlist=[]
    tags.forEach((k,i) => {
        const label = document.createElement("label")
        label.className = "easyuse-prompt-styles-tag"
        label.dataset.tag = i
        label.dataset.name = $t(k)
        label.dataset.index = i

        const checkbox = document.createElement("input")
        checkbox.type = 'checkbox'
        checkbox.name = i
        checkbox.onclick = () => {
            label.classList.toggle("easyuse-prompt-styles-tag-selected");
        };

        const text = document.createElement("span")
        text.textContent = $t(k)

        label.append(checkbox, text)
        rlist.push(label)
    });
    return rlist
}


comfy.defs.extend('easy humanSegmentation', (b) => {

    // 创建时
    b.onCreated((node) => {
        const method = node.widgets.get('method');
        const list = document.createElement("ul");
        list.className = "easyuse-prompt-styles-list no-top";
        node.setProperty("values", [])

        const root = document.createElement("div");
        root.className = "easyuse-prompt-styles";
        root.append(list);

        // The old code read the selection back through a `value` getter that
        // rebuilt it from the DOM on every read, and wrote it into
        // properties.values on the way past. A mounted widget owns a real value
        // cell, so the selection is written when it changes instead.
        const readSelection = () => {
            const values = [];
            list.querySelectorAll(".easyuse-prompt-styles-tag").forEach(el => {
                if (el.classList.contains("easyuse-prompt-styles-tag-selected")) {
                    values.push(el.dataset.tag);
                }
            });
            node.setProperty("values", values);
            return values.join(',');
        }

        const applySelection = (value) => {
            const arr = String(value ?? '').split(',');
            list.querySelectorAll(".easyuse-prompt-styles-tag").forEach(el => {
                const on = arr.includes(el.dataset.tag);
                el.classList.toggle("easyuse-prompt-styles-tag-selected", on);
                el.children[0].checked = on;
            });
        }

        const selector = node.widgets.mount({
            name: 'mask_components',
            defaultValue: '',
            render(container, value) {
                container.append(root);
                list.addEventListener('click', () => value.set(readSelection()));
                value.onChange((v) => applySelection(v));
            }
        });

        const showTags = (method_values) => {
            if(!method_values) return
            list.innerHTML = ''
            if(method_values == 'selfie_multiclass_256x256'){
                toggleWidget(node, findWidgetByName(node, 'confidence'), true)
                node.setSize({width: 300, height: 260});
            }else{
                toggleWidget(node, findWidgetByName(node, 'confidence'))
                node.setSize({width: 300, height: 500});
            }
            list.append(...getTagList(tags[method_values]))
        }

        method.on('change', (value) => showTags(value))

        // 初始化
        setTimeout(_=>{
            // A workflow load assigns the widget value directly, which raises no
            // change event, so the tag list is built here from whatever the method
            // widget ended up holding and the saved selection re-applied on top.
            showTags(method.getValue() || 'selfie_multiclass_256x256')
            applySelection(selector.getValue())
        },1)
    })
})
