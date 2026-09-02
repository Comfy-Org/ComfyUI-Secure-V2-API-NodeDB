import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend(["INTConstant", "FloatConstant", "ConditioningMultiCombine"], (b) => {
        b.onCreated((node) => {
            switch (node.comfyClass) {
                case "INTConstant":
                    node.setSize({ width: 200, height: 58 });
                    node.setColor("#1b4669");
                    node.setBgColor("#29699c");
                    break;
                case "FloatConstant":
                    node.setSize({ width: 200, height: 58 });
                    node.setColor("#232");
                    node.setBgColor("#353");
                    break;
                case "ConditioningMultiCombine":
                    node.setColor("#332922");
                    node.setBgColor("#593930");
                    break;
            }
        });
});
