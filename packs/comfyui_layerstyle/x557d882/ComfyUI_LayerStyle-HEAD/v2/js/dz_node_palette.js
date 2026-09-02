import { comfy } from '/comfy/api/v2.js';


comfy.defs.extend(/^Layer/, (b) => {
    b.onCreated((node) => {
		if(node.comfyClass.startsWith("LayerStyle:")) {
            node.setColor("rgba(20, 95, 121, 0.7)");
//            node.bgcolor = "rgba(50, 241, 255, 0.15)";
		}

		if(node.comfyClass.startsWith("LayerColor:")) {
            node.setColor("rgba(27, 89, 123, 0.7)");
//            node.bgcolor = "rgba(43, 209, 255, 0.15)";
		}

		if(node.comfyClass.startsWith("LayerMask:")) {
            node.setColor("rgba(27, 80, 119, 0.7)");
//            node.bgcolor = "rgba(4, 174, 255, 0.15)";
		}

		if(node.comfyClass.startsWith("LayerUtility:")) {
            node.setColor("rgba(38, 73, 116, 0.7)");
//            node.bgcolor = "rgba(23, 113, 255, 0.15)";
		}

		if(node.comfyClass.startsWith("LayerFilter:")) {
            node.setColor("rgba(34, 67, 111, 0.7)");
//            node.bgcolor = "rgba(19, 85, 255, 0.15)";
		}

        
//        if(node.comfyClass === "LayerStyle: ColorOverlay"){
//            node.setSize([600, 120]);
//        }
    });
});