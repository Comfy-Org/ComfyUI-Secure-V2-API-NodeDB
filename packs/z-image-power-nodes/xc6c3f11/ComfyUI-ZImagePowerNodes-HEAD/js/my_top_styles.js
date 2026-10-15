/**
 * File    : my_top_styles.js
 * Purpose : Frontend implementation of "My Top-<N> Styles" node functionality.
 * Author  : Martin Rizzo | <martinrizzo@gmail.com>
 * Date    : Jan 31, 2026
 * Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
 * License : MIT
 *- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *                        ComfyUI-ZImagePowerNodes
 *       ComfyUI nodes designed specifically for the "Z-Image" model.
 *_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
*/
import { app } from "../../../scripts/app.js";
import { forceRenameWidget, getInputNode, getInputOriginID, getOutputNodes } from "./common.js";
import { scheduleIntervalCalls } from "./common_timer.js";
const ENABLED = true;
const DATA_INPUT       = 'input';      // name of the input socket
const DATA_OUTPUT      = 'output';     // name of the output socket
//const TOP_STYLES_INPUT = 'top_styles'; // name of the input socket that connects to the "Top-Styles" provider.

//- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Here I leave a safe way to get the node and widgets of the controller,
// it's been used for debugging but doesn't offer any advantage.
// const node            = self.node?.graph?.getNodeById?.(self.node.id);
// const allStyleWidgets = node.widgets.filter(w => w.name.startsWith("style_"));
//- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


//#======================= My Top Styles Controller ========================#
/**
 * Controller for any node that selects from a list of top styles. (e.g., "My Top-10 Styles")
 * @typedef {Object} MyTopStylesCtrl
 *   @property {Object}        node             - The node this controller is attached to.
 *   @property {Array<Object>} allStyleWidgets  - A list of all widgets whose name starts with "style_".
 *   @property {boolean}       eventEnabled     - Whether or not the controller generate 'onBooleanSwitchChanged' event.
 *                                                (used to prevent infinite recursion when updating the list)
 *   @property {number|null}  topStylesOriginID - The ID of the node connected to the 'top_styles" input.
 *   @property {number|null}  inputOriginID     - The ID of the node connected to the 'input' input.
 */


/**
 * Initializes the `MyTopStylesCtrl` controller.
 *
 * @param {MyTopStylesCtrl} self - The instance of the controller being initialized.
 * @param {Object}          node - The node to control.
 */
function init(self_, node) {
    const self = self_;

    // find all required widgets
    const allStyleWidgets = node.widgets.filter(w => w.name.startsWith("style_"));
    const channelWidgets  = node.widgets.filter(w => w.name === "output_to");
    const controlWidgets  = node.widgets.filter(w => w.name === "control_after_generate");
    const channelWidget   = channelWidgets.length > 0 ? channelWidgets[0] : null;
    const controlWidget   = controlWidgets.length > 0 ? controlWidgets[0] : null;
    if( !allStyleWidgets || allStyleWidgets.length == 0 || !channelWidget || !controlWidget ) {
        console.error("Missing required widgets!");
        return;
    }

    // iterate through all "style_" widgets
    for( let i=0 ; i<allStyleWidgets.length ; ++i ) {
        const widget = allStyleWidgets[i];

        // replacing the `callback` function in all widgets,
        // using the safest way to call original function
        const oldCallback = widget.callback;
        widget.callback = function(value, mode) {
            const eventEnabled = self.eventEnabled && mode !== "no-event";
            if( eventEnabled ) {
                self.eventEnabled = false;
                onBooleanSwitchChanged(self, widget, value);
                self.eventEnabled = true;
            }
            if( typeof oldCallback === 'function' ) { oldCallback.apply(this, arguments); }
        };
    }

    if( controlWidget ) {
        const oldAfterQueued = controlWidget.afterQueued;
        controlWidget.afterQueued = function() {
            onControlWidget(self, controlWidget, controlWidget.value);
            if( typeof oldAfterQueued === 'function' ) { oldAfterQueued.apply(this, arguments); }
        };
    }

    // set controller properties and public methods
    self.node                = node;
    self.allStyleWidgets     = allStyleWidgets;
    self.channelWidget       = channelWidget;
    self.controlWidget       = controlWidget;
    self.eventEnabled        = true;
    self.topStylesOriginID   = null;
    self.inputOriginID       = null;
    self.updateTopStyles     = function(topStyles) { updateTopStyles(self, topStyles); };
    self.processChainMessage = function(message) { processChainMessage(self, message); };
    self.onInterval          = function() { onInterval(self); };
    scheduleIntervalCalls(self);
}


/**
 * Processes a chain message by delegating the task to appropriate handlers.
 *
 * All messages should be launched with the prefix "launch:", this causes the
 * message to search left from the initial node of the chain. Once the initial
 * node is reached, the message loses its prefix "launch:" and moves to the
 * right reaching all nodes of the chain in order.
 *
 * @param {MyTopStylesCtrl} self    - The controller instance.
 * @param {Object}          message - The message object containing at least
 *                                    `type` and `sender_id`. properties.
 */
function processChainMessage(self, message) {
    let type      = message.type;
    let sender_id = message.sender_id;
    if( typeof type !== "string" || sender_id == null )
    { console.error("Invalid chain message!", message); return; }

    // <<< go left while `type` starts with "launch:"
    if( type.startsWith("launch:") ) {
        const inputNode = getInputNode(self.node, DATA_INPUT);
        if( inputNode?.id === sender_id )
        { console.error("Recursive chain detected!"); return; }

        if( inputNode?.zzController?.processChainMessage ) {
            inputNode.zzController.processChainMessage(message);
        } else {
            // if there's no left node, go right
            type = type.substring("launch:".length);
            message["type"] = type;
        }
    }

    // >>> go right when `type` doesn't start with "launch:"
    if( !type.startsWith("launch:") ) {
        onChainMessage(self, message);

        const outputNodes = getOutputNodes(self.node, DATA_OUTPUT);
        for( const outputNode of outputNodes ) {
            outputNode.zzController?.processChainMessage(message);
        }
    }
}


/**
 * Updates the top styles of a controller and refreshes their widgets accordingly.
 * @param {MyTopStylesCtrl} self        - The controller instance.
 * @param {Array<string>}   [topStyles] - The list of new top styles (optional).
 */
function updateTopStyles(self, topStyles) {

    const node            = self.node;
    const allStyleWidgets = self.allStyleWidgets;
    if( !topStyles ) { topStyles = []; }

    for( let i=0 ; i<allStyleWidgets.length ; i++ ) {
        const widget    = allStyleWidgets[i];
        const styleName = i<topStyles.length ? topStyles[i] : "";
        if( isValidStyleName(styleName) ) {
            const text = (i+1) + " - " + styleName;
            forceRenameWidget(widget, node, text);
        } else {
            forceRenameWidget(widget, node, "-");
        }
    }
}


/**
 * Returns the index of the first style widget with a valid style name.
 * @param {MyTopStylesCtrl} self - The controller instance.
 * @returns {number}
 *     The index of the first valid widget,
 *     or -1 if no widget has a valid style name.
 */
function getFirstValidWidgetIndex(self) {
    const allStyleWidgets = self.allStyleWidgets;
    for( let i=0 ; i<allStyleWidgets.length ; ++i ) {
        if( isValidStyleName(allStyleWidgets[i].label) ) { return i; }
    }
    return -1;
}


/**
 * Deselects all styles turning off all switch widgets.
 * @param {MyTopStylesCtrl} self - The controller instance.
 */
function deselectAllStyles(self) {
    for( const widget of self.allStyleWidgets ) {
        if( widget.value ) {
            widget.value = false;
            widget.callback(false, "no-event");
        }
    }
}


//#-------------------------------- EVENTS ---------------------------------#

/**
 * Called when the switch associated with a style changes its state.
 * @param {MyTopStylesCtrl} self   - The controller instance.
 * @param {Object}          widget - The widget whose value has changed.
 * @param {boolean}         value  - The new boolean value of the switch widget.
 */
function onBooleanSwitchChanged(self, widget, _value) {
    const allStyleWidgets = self.allStyleWidgets;

    // only one style can be selected, or none at all
    for( const styleWidget of allStyleWidgets ) {
        if( styleWidget !== widget ) {
            styleWidget.value = false;
            styleWidget.callback(false, "no-event");
        }
    }

    // send a message to all nodes in the chain to deselect styles linked to "channel"
    // (currently there are 4 channels "custom_1", "custom_2", "custom_3" and "custom_4")
    processChainMessage(self, { type     : "launch:deselectAllStyles",
                                channel  : self.channelWidget.value,
                                sender_id: self.node.id });
}


/**
 * Called when the control widget requests to perform an action, typically after the workflow is queued.
 * @param {MyTopStylesCtrl} self   - The controller instance.
 * @param {Object}          widget - The control widget that requested the action.
 * @param {string}          value  - The action to be performed, either "fixed", "next", or "randomize".
 */
function onControlWidget(self, widget, value) {
    const allStyleWidgets = self.allStyleWidgets;

    if( value === "next" ) {

        const firstValidIndex = getFirstValidWidgetIndex(self);
        if( firstValidIndex === -1 ) {
            deselectAllStyles(self); return; }

        // find the next widget after the one that is selected,
        // taking into account that it must have a valid style name
        let i = firstValidIndex;
        for( ; i<allStyleWidgets.length ; ++i ) {
            if( allStyleWidgets[i].value ) { ++i; break; } }
        for( ; i<allStyleWidgets.length ; ++i ) {
            if( isValidStyleName(allStyleWidgets[i].label) ) { break; } }

        // activate the 'i' widget, but verifying that
        // if it reached the end of the list it should return to the beginning
        if( i>=allStyleWidgets.length ) { i = firstValidIndex; }
        allStyleWidgets[i].value = true;
        allStyleWidgets[i].callback(true);
    }
    else if( value === "randomize" ) {
        // TODO: implement a random selector that doesn't repeat (something like a shuffle)
    }
}


/**
 * Called when the input slot 'top_styles' changes its connection to another node (or disconnects).
 * @param {MyTopStylesCtrl} self - The controller instance.
 * @param {Object|null}     node - The connected node or null if disconnected.
 */
function onTopStylesConnectionChanged(self, node) {
    // updates the top styles based on the new connected node's list.
    updateTopStyles( self, node?.zzController?.getTopStyles?.() );
}


/**
 * Called when the input slot 'input' changes its connection to another node (or disconnects).
 * @param {MyTopStylesCtrl} self - The controller instance.
 * @param {Object|null}     node - The connected node or null if disconnected.
 */
function onInputConnectionChanged(self, node) {

    if( node ) {
        // send a message to all nodes in the chain forcing no 2 styles selected on same channel
        // (currently there are 4 channels "custom_1", "custom_2", "custom_3" and "custom_4")
        processChainMessage(self, { type     : "launch:forceNoRepeatChannels",
                                    channels : new Set(),
                                    sender_id: self.node.id });
    }
    else {
        console.log("##>> DISCONNECTED from input connection");
    }
}


/**
 * Called when a message from another node in the chain is received.
 * @param {MyTopStylesCtrl} self    - The controller instance.
 * @param {Object}          message - The received message containing `type`,
 *                                    `sender_id`, and custom properties.
 */
function onChainMessage(self, message) {
    const type      = message.type;
    const sender_id = message.sender_id;

    // message that deselects all styles of a specific channel:
    //  - this message should not be processed by the same node that sent it.
    //  - don't process if channel is specified and it's different from the current one,
    if( type === 'deselectAllStyles' ) {
        if( self.node.id === sender_id ) { return; }
        if( message.channel && message.channel !== self.channelWidget.value ) { return; }
        deselectAllStyles(self);
        return;
    }

    // message that forces no 2 styles to be selected in the same channel
    if( type == 'forceNoRepeatChannels' ) {
        const channels = message.channels;
        const repeated = channels.has(self.channelWidget.value);
        if( repeated ) { deselectAllStyles(self); }
        else           { channels.add(self.channelWidget.value); }
    }
}


/**
 * Called periodically to verify node connections.
 * @param {MyTopStylesCtrl} self - The controller instance.
 */
function onInterval(self) {

    // verify the `top_styles` slot connection
    const topStylesOriginID = getInputOriginID(self.node, "top_styles");
    if( self.topStylesOriginID !== topStylesOriginID ) {
        self.topStylesOriginID = topStylesOriginID;
        const originNode = topStylesOriginID == null ? null : self.node?.graph?.getNodeById(topStylesOriginID);
        onTopStylesConnectionChanged(self, originNode);
    }

    // verify the `input` slot connection
    const inputOriginID = getInputOriginID(self.node, "input");
    if( self.inputOriginID !== inputOriginID ) {
        self.inputOriginID = inputOriginID;
        const originNode = inputOriginID == null ? null : self.node?.graph?.getNodeById(inputOriginID);
        onInputConnectionChanged(self, originNode);
    }
}


//#-------------------------------- HELPERS --------------------------------#

/**
 * Checks whether a given style name is valid.
 * @param {string} styleName - The name of the style to validate.
 * @returns {boolean} True if the style name is valid, false otherwise.
 */
function isValidStyleName(styleName) {

    // discard any name that is not a string
    if( typeof styleName  != 'string' ) { return false; }

    // discard any empty string, dash or  "none"
    const trimmedName = styleName.trim();
    if( trimmedName === "" || trimmedName === "-" || trimmedName === "none" ) { return false; }

    return true;
}




//#=========================================================================#
//#////////////////////////// REGISTER EXTENSION ///////////////////////////#
//#=========================================================================#

app.registerExtension({
    name: "ZImagePowerNodes.MyTopStyles",

    /** Called when the extension is loaded. */
    init() {
        if (!ENABLED) return;
        console.log(`[${this.name}]: Extension loaded.`);
    },

    /**
     * Called every time ComfyUI creates a new node.
     * @param {ComfyNode} node - The node that was created.
     */
    async nodeCreated(node) {
        if (!ENABLED) return;
        const comfyClass = node?.comfyClass ?? "";

        // inject controller only to nodes of type "My Top-X Styles Selector"
        if( comfyClass.startsWith("MyTop10Styles //ZImage" ) ) {
            node.zzController = {};
            init(node.zzController, node);
        }
    },

});
