/**
 * File    : comfyui_bridge.js
 * Purpose : Provides a safe bridge to the LiteGraph environment within ComfyUI.
 * Author  : Martin Rizzo | <martinrizzo@gmail.com>
 * Date    : May 12, 2026
 * Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
 * License : MIT
 *- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *                        ComfyUI-ZImagePowerNodes
 *       ComfyUI nodes designed specifically for the "Z-Image" model.
 *_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
*/
import { app }             from "../../../scripts/app.js";

/**
 * Reference to the global LiteGraph instance.
 * @type {Object}
 */
export const LiteGraph = globalThis.LiteGraph;


/**
 * Reference to the base LGraphNode class.
 * @type {Function}
 */
export const LGraphNode = globalThis.LGraphNode;


/**
 * Module-level cache storage used by `getWidgetBgColor20()`
 * to avoid unnecessary DOM lookups.
 * @type {{ colorPalette: string | undefined, widgetBgColor: string | null }}
 */
const _cache = {
    colorPalette: undefined,
    widgetBgColor: null,
};


/**
 * Checks if ComfyUI has Nodes 2.0 enabled in the application settings.
 * @returns {boolean}
 *   True if the VueNodes feature is enabled, false otherwise.
 * @example
 *   if( isNodes20() ) { console.log("Nodes 2.0 interface is active."); }
 */
export function isNodes20() {
    return !!app.ui?.settings?.settingsValues?.["Comfy.VueNodes.Enabled"];
}


/**
 * Retrieves the widget background color using the internal cache.
 * Note: This function should only be called when `isNodes20()` returns true.
 * It recalculates the color only when the UI theme palette changes.
 * @returns {string}
 *   The computed widget background color.
 * @example
 *   if( isNodes20() ) {
 *       const bgColor = getWidgetBgColor20();
 *       console.log("Current widget background color:", bgColor);
 *   }
 */
export function getWidgetBgColor20() {
    // if the ComfyUI color palette hasn't changed, return the cached color
    const colorPalette = app.ui?.settings?.settingsValues?.["Comfy.ColorPalette"];
    if( colorPalette === _cache.colorPalette && _cache.widgetBgColor ) {
        return _cache.widgetBgColor;
    }
    // try to get an element within the DOM to compute the style
    const targetElement = app.ui?.element || document?.body;
    if( !targetElement || typeof getComputedStyle !== "function" ) {
        return _cache.widgetBgColor || "";
    }
    // calculate the new color from CSS variables and update the cache
    _cache.colorPalette  = colorPalette;
    _cache.widgetBgColor = getComputedStyle(targetElement)
        .getPropertyValue('--component-node-widget-background')
        .trim();
    return _cache.widgetBgColor;
}


/**
 * Validates the presence of LiteGraph dependencies.
 *
 * Logs specific warnings if the environment is not ready,
 * helping in debugging initialization order issues.
 */
export function validateBridge()
{
    if( !LiteGraph ) {
        console.warn(
            "[Z-ImagePowerNodes ComfyUI-Bridge] LiteGraph module not found in global scope. " +
            "This may indicate that Z-Image Power Nodes are out of date due to recent internal changes in ComfyUI."
        );
    }

    if( !LGraphNode ) {
        console.error(
            "[Z-ImagePowerNodes ComfyUI-Bridge] LGraphNode prototype missing. " +
            "The LiteGraph engine might not have initialized properly or is inaccessible for Z-Image Power Nodes. " +
            "Please ensure your environment meets the latest requirements and try updating Z-Image Power Nodes."
        );
    }
}


// Run validation upon module import!
validateBridge();
