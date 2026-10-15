/**
 * File    : common.js
 * Purpose : Common script file with helper functions.
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
export {
    loadCSS,
    isNodeFromMyProject,
    getOutputNodes,
    getInputOriginID,
    getInputNode,
    renameWidget,
    forceRenameWidget
};

/**
 * This constant represents the project ID used to identify nodes in the ComfyUI node registry.
 * IMPORTANT: It must match the value defined in `__init__.py` !!.
 * @type {string}
 */
const __PROJECT_ID = "//ZImagePowerNodes";


function loadCSS(fileName) {
    const fullPath = import.meta.resolve(`./${fileName}`);
    const link     = document.createElement("link");
    link.rel  = "stylesheet";
    link.href = fullPath;
    document.head.appendChild(link);
}


/**
 * Checks if a given node belongs to the current project.
 *
 * @param {Object} node - The node object to check.
 * @returns {boolean} True if the node belongs to the current project, false otherwise.
 */
function isNodeFromMyProject(node) {
    return (node?.comfyClass ?? "").includes(__PROJECT_ID);
}


/**
 * Get all nodes connected to a given node's outputs.
 *
 * @param {Object} node         - The input node from which to retrieve outputs.
 * @param {string} [outputName] - Optional. The name of the output connection to search.
 *                                If not provided, nodes connected to any output will be returned.
 * @returns {Array} An array of nodes connected to the specified output
 */
function getOutputNodes(node, outputName) {
    let outputNodes = [];

    // get the graph safely
    const graph = (node?.graph || app.graph);
    if( !graph ) { return outputNodes; }

    const outputs = node?.outputs || [];
    for( let i=0 ; i<outputs.length ; ++i ) {
        const output = outputs[i];

        // if outputName is provided, compare it with the current name
        if( outputName && outputName !== output?.name ) { continue; }

        const links = output?.links || [];
        for( let j=0 ; j<links.length ; ++j )
        {
            const link       = graph.links[ links[j] || "" ];
            const outputNode = graph.getNodeById( link?.target_id || "" );
            if( outputNode ) {
                outputNodes.push( outputNode );
            }
        }
    }
    return outputNodes;
}


/**
 * Get the ID of the node connected to a given node's input.
 *
 * @param {Object} node        - The node whose input will be analyzed.
 * @param {string} [inputName] - Optional. The name of the input connection to search.
 *                               If not provided, it searches only the first input connection.
 * @returns {(string|null)} The ID of the node connected as input or `null` if nothing is connected.
 */
function getInputOriginID(node, inputName) {

    // get the graph safely
    const graph = (node?.graph || app.graph);
    if( !graph ) { return null; }

    const inputs = node?.inputs || [];
    for( let i=0 ; i<inputs.length ; ++i ) {
        const input = inputs[i];

        // if outputName is provided, compare it with the current name
        if( inputName && inputName !== input?.name ) { continue; }

        return graph.links[ input?.link || 0 ]?.origin_id;
    }
    return null;
}


/**
 * Get the node that is connected to a given node's input.
 *
 * @param {Object} node        - The node whose input will be analyzed.
 * @param {string} [inputName] - Optional. The name of the input connection to search.
 *                               If not provided, it searches only the first input connection.
 * @returns {(Object|null)} The node that is connected as input or `null` if nothing is connected.
 */
function getInputNode(node, inputName) {
    const graph    = (node?.graph || app.graph);
    const originID = getInputOriginID(node, inputName);
    return originID != null ? graph.getNodeById(originID) : null;
}


/**
 * Checks if a given widget is a proxy widget.
 *
 * This code is not fully tested but the concept comes from the ComfyUI Frontend:
 *  - https://github.com/Comfy-Org/ComfyUI_frontend/blob/v1.39.4/src/core/graph/subgraph/proxyWidget.ts#L51
 *
 * @param {IBaseWidget} widget - The widget object to check.
 * @returns {boolean} Returns true if the widget has an overlay that is a proxy widget, otherwise false.
 */
function isProxyWidget(widget) {
  return !!(widget?._overlay?.isProxyWidget);
}


/**
 * Renames a widget and its corresponding input.
 *
 * Handles both regular widgets and proxy widgets in subgraphs.
 * This code is not fully tested but it comes from the ComfyUI Frontend:
 *  - https://github.com/Comfy-Org/ComfyUI_frontend/blob/v1.39.4/src/utils/widgetUtil.ts#L16
 *
 * @param {IBaseWidget}    widget    - The widget to rename
 * @param {LGraphNode}     node      - The node containing the widget
 * @param {string}         newLabel  - The new label for the widget (empty string or undefined to clear)
 * @param {SubgraphNode[]} [parents] - Optional array of parent SubgraphNodes (for proxy widgets)
 * @returns {boolean} true if the rename was successful, false otherwise
 */
function renameWidget(widget, node, newLabel, parents)
{
    // for proxy widgets in subgraphs, we need to rename the original interior widget
    if (isProxyWidget(widget) && parents?.length) {
        const subgraph = parents[0].subgraph;
        if (!subgraph) {
            console.error('Could not find subgraph for proxy widget');
            return false;
        }
        const interiorNode = subgraph.getNodeById(widget._overlay.nodeId);

        if (!interiorNode) {
            console.error('Could not find interior node for proxy widget');
            return false;
        }

        const originalWidget = interiorNode.widgets?.find(
            (w) => w.name === widget._overlay.widgetName
        );

        if (!originalWidget) {
            console.error('Could not find original widget for proxy widget');
            return false;
        }

        // rename the original widget
        originalWidget.label = newLabel || undefined;

        // also rename the corresponding input on the interior node
        const interiorInput = interiorNode.inputs?.find(
            (inp) => inp.widget?.name === widget._overlay.widgetName
        );
        if (interiorInput) {
            interiorInput.label = newLabel || undefined;
        }
    }

    // always rename the widget on the current node (either regular widget or proxy widget)
    const input = node.inputs?.find((inp) => inp.widget?.name === widget.name);

    // intentionally mutate the widget object here as it's a reference
    // to the actual widget in the graph
    widget.label = newLabel || undefined;
    if (input) { input.label = newLabel || undefined; }
    return true;
}


/**
 * Updates the label of a given widget and forces a redraw.
 *
 * This is an attempt to make `renameWidget` work with Nodes 2.0 of ComfyUI.
 *
 * @param {Object} widget   - The widget whose label is to be updated.
 * @param {Object} node     - The node associated with the widget.
 * @param {string} newLabel - The new label for the widget.
 */
function forceRenameWidget(widget, node, newLabel, parents) {
    renameWidget(widget, node, newLabel, parents);

    // force LiteGraph to mark the node as needing a redraw
    node.setDirtyCanvas(true, true);

    // if the Vue component is listening for changes in the 'options' object,
    // update a fictitious property to trigger Vue's observer.
    if (widget.options) {
        widget.options._force_update = Date.now();
    }

    // Nodes 2.0 could require the node to "blink" to redraw the DOM of Vue (??)
    const originalSize = [...node.size];
    node.size[0] += 0.001; 
    node.setSize(node.size);
    node.size[0] = originalSize[0];
    node.setSize(originalSize);
}
