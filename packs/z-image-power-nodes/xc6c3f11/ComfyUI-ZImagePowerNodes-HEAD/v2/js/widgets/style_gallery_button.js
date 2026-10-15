/**
 * File    : style_gallery_button.js
 * Purpose : Custom button widget for launching the style gallery. [DEPRECATED]
 * Author  : Martin Rizzo | <martinrizzo@gmail.com>
 * Date    : Feb 3, 2026
 * Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
 * License : MIT
 *- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *                        ComfyUI-ZImagePowerNodes
 *       ComfyUI nodes designed specifically for the "Z-Image" model.
 *_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
 */
export { addStyleGalleryButton };
import { requireVisualStyleGalleryDialog } from "./ui_styles.js";


/**
 * Adds a button to the node that opens the style gallery dialog.
 * @param {LGraphNode} node  - ComfyUI node where the widget will be added.
 * @param {string}     name  - The name of the value attached to the widget.
 * @param {Array}      data  - An array with the following format: [type, options]
 * @returns {{widget: object}}
 *     An object containing the created widget.
 */
function addStyleGalleryButton(node, name, data) {
    //const type    = data[0];
    const options = data[1] || {};


    // split the inputName to extract any title variant
    // (title variant is the part of the input-name after the last underscore)
    const parts   = name.split('_');
    let   variant = parts.length>1 ? parts[ parts.length - 1 ] : "";

    // ensure the variant is a number
    if( variant.match(/^[0-9]+$/) === null ) { variant = ""; }
    const buttonTitle = `Select Style${variant ? ' ' + variant : ""}`;
    const dialogTitle = buttonTitle;

    // find the previous widget,
    // which should be a combo widget to receive the style selection
    const prevIndex  = node.widgets.length - 1;
    const prevWidget = prevIndex>=0 ? node.widgets[prevIndex] : null;
    if( !prevWidget || prevWidget.type !== "combo" ) {
        console.error("Style Gallery Button must follow a Combo Widget!");
        return;
    }

    // add a custom button widget to the node
    const button = node.addCustomWidget({
            type     : "button",
            name     : name,
            label    : `🖼️  ${buttonTitle} ...`,
            serialize: true,
            options  : {
                dialog_title: dialogTitle,
                prev_index  : prevIndex,
                ...options
            }
    });

    // the serialized value is always null, as it doesn't store a value itself.
    // (disable serialization may cause problems when saving and retrieving nodes)
    button.serializeValue = () => null;

    // when the button is pressed, launch the dialog
    button.callback = () =>
    {
        // const shiftGlobal = window.event?.shiftKey;
        // if (shiftGlobal) {
        //     console.log("Alternative action with shift key pressed");
        //     return;
        // }
        const options       = button.options;
        const prevWidget    = button.node.widgets[options.prev_index];
        const endpoint      = options.endpoint   || "";
        const imagesURL     = options.images_url || "";
        const dialogOptions = options.dialog || {};

        const styleDialog  = requireVisualStyleGalleryDialog(endpoint, imagesURL);
        const currentStyle = prevWidget.value?.replace(/^"|"$/g, '');
        styleDialog.launch( dialogOptions, currentStyle, (selectedStyle) =>
        {
            // ensure the selected style name is properly quoted
            if( selectedStyle!="" && selectedStyle!="-" && selectedStyle!="none" ) {
                if( !selectedStyle.startsWith('"') ) { selectedStyle = `"${selectedStyle}"`; }
            }
            // apply the new style name on the previous widget
            prevWidget.value = selectedStyle;
            prevWidget.callback(selectedStyle);
            node?.setDirtyCanvas?.(true);
        });
    };
    return { widget: button };
}

