import { app } from "../../../scripts/app.js";

// Adds context menu entries, code partly from pyssssscustom-scripts

function addMenuHandler(nodeType, cb) {
  // console.debug("SIE addMenuHandler nodeType:", nodeType);
  // console.debug("SIE addMenuHandler cb:", cb);
	const getOpts = nodeType.prototype.getExtraMenuOptions;
  
  // the below is never called, i suspect app.js has changed a lot
	nodeType.prototype.getExtraMenuOptions = function () {
		const r = getOpts.apply(this, arguments);
		cb.apply(this, arguments);
    // console.debug("SIE addMenuHandler arguments:", arguments);
		return r;
	};
}


function addNode(name, nextTo, options) {
	// console.debug("SIE addNode name:", name);
	// console.debug("SIE addNode nextTo:", nextTo);
	options = { select: true, shiftY: 0, before: false, ...(options || {}) };
	const node = LiteGraph.createNode(name);
	app.graph.add(node);
	node.pos = [
		options.before ? nextTo.pos[0] - node.size[0] - 30 : nextTo.pos[0] + nextTo.size[0] + 30,
		nextTo.pos[1] + options.shiftY,
	];
	if (options.select) {
		app.canvas.selectNode(node, false);
	}
	return node;
}

// https://docs.comfy.org/custom-nodes/js/javascript_overview
app.registerExtension({
  name: "SIE.QuickNodes",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (
      // this could go forever if we want to list all nodes that can output IMAGE
      // nodeData.name === "VAEDecode" ||
      // nodeData.name === "LoadImage" ||
      
      // fortunately, output is an array where "IMAGE" is always the first item.
      nodeData.output[0] == "IMAGE"
    ) {
      // console.debug("SIE.QuickNodes VAEDecode nodeType:", nodeType);
      // console.debug("SIE.QuickNodes VAEDecode nodeData:", nodeData);
      // console.debug("SIE.QuickNodes VAEDecode app:", app);
      
      // https://docs.comfy.org/custom-nodes/js/javascript_examples#node-menu
      // Code below adds SaveImageExtended option on right-click menu for VAEDecode
      addMenuHandler(nodeType, function (_, options) {
        options.unshift(
          {
            content: "💾 Add SaveImageExtended",
            callback: () => {
              // const saveNode = addNode("SaveImageExtended", this, { before: true });
              const saveNode = addNode("SaveImageExtended", this);
              this.connect(0, saveNode, 0);
            },
          },
        );
      });
    }
  },
},

// https://docs.comfy.org/custom-nodes/walkthrough#write-a-client-extension
// I forgot why I added this one, probably not needed after all
{
	name: "SIE.Contextmenu",
  async setup(app) {
	// console.debug("SIEContextmenu app:", app);
    app.ui.settings.addSetting({
      id: "SIE.helpPopup",
      name: "💾 SIE: Help popups",
      defaultValue: true,
      type: "boolean",
      options: (value) => [
        { value: true, text: "On", selected: value === true },
        { value: false, text: "Off", selected: value === false },
      ],
    });
    
    
  }
});




