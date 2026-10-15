/**
 * File    : ui_palettes.js
 * Purpose : Implements Dialog, Widget, and DataProvider for color palettes,
 *           ensuring compatibility with previous Power Nodes versions.
 *
 * Author  : Martin Rizzo | <martinrizzo@gmail.com>
 * Date    : May 21, 2026
 * Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
 * License : MIT
 *- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *                        ComfyUI-ZImagePowerNodes
 *       ComfyUI nodes designed specifically for the "Z-Image" model.
 *_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
 */
export {
    PaletteWidgetDelegate,
    requireColorPaletteGalleryDialog,
    fetchColorPaletteArray,
};
import { api } from "../../../scripts/api.js";
import { GalleryWidgetDelegate }                from "./gallery_widget.js";
import { GalleryDialog, GalleryDialogDelegate } from "./gallery_dialog.js";

// Cache of promises to avoid duplicate requests for the same endpoint.
const _fetchesByEndpoint = new Map();

// Registry of dialogs for each color-palete database endpoint.
const _dialogsByEndpoint = new Map();


//#==========================================================================#
//#                           FETCH COLOR PALETTES                           #
//# The FIRST generation of UI fetched items directly using this function    #
//# and loaded them into a native ComfyUI combobox. Currently, this function #
//# is internally invoked from GALLERY DIALOG and the GALLERY WIDGET.        #

/**
 * Fetches an array with data about each color palette from the server.
 *
 * Note: The implementation looks a bit complex because of the caching system.
 * It uses an immediately-invoked function (IIFE) to cache the ongoing promise
 * right away, ensuring we don't trigger duplicate network requests for the
 * same endpoint URL.
 *
 * @param {string} endpoint - The full endpoint URL to fetch the palettes from.
 * @returns {Promise<Array<Object>>}
 *     Resolves to the array of formatted color palettes.
 *     Each element in the array is an object with the following properties:
 *       - idx        : Unique identifier for the palette (the index in the list)
 *       - name       : The name of the color palette (string)
 *       - description: Description of the color palette (string)
 *       - tags       : An string of comma-separated tags associated with the palette (string)
 *       - colors     : Array of color objects, each containing a name and a hex code (Array<{name: string, hex: string}>)
 * @example
 *   // Using async/await
 *   const palettes = await fetchColorPaletteArray('/zi_power/palettes/by_version?v=1.0');
 *   console.log(`Loaded ${palettes.length} palettes.`);
 * @example
 *   // Using promises (.then)
 *   fetchColorPaletteArray('/zi_power/styles/by_version?v=1.0').then(palettes => {
 *       console.log(`Loaded ${palettes.length} palettes.`);
 *   });
 */
async function fetchColorPaletteArray(endpoint)
{
    if( typeof endpoint !== 'string' || !endpoint.trim() ) {
        console.error(`Invalid endpoint parameter: "${endpoint}". Expected a non-empty string.`);
        return [];
    }

    // if the endpoint already exists in the "fetch cache"
    // (either the ongoing promise or resolved result),
    // RETURN IT!
    if( _fetchesByEndpoint.has(endpoint) ) {
        return _fetchesByEndpoint.get(endpoint);
    }
    // encapsulate the fetch process in a promise
    const fetchPromise = (async () => {
        try {
            // fetch the palettes for the given endpoint
            const response = await api.fetchApi(endpoint);
            if( !response.ok ) { throw new Error(`HTTP ${response.status}`); }

            // validate that the response is an actual array
            const palettes = await response.json();
            if( !Array.isArray(palettes) ) { throw new Error(`Expected an array but received ${typeof palettes}`); }

            return palettes.map((paldata, index) =>
            {
                const name        = paldata[0] || "Unknown";
                const description = paldata[1] || "";
                const tags        = paldata[2] || "";
                // build the colors array from the data received from the API
                const colors = [];
                for( let i=3; (i+1) < paldata.length; i+=2 ) {
                    colors.push({ hex: paldata[i], color: paldata[i+1] });
                }
                return {
                    idx        : index,
                    name       : name,
                    category   : "",
                    description: description,
                    tags       : tags,
                    colors     : colors
                };
            });

        } catch (error) {
            // if failed, delete the cache for this endpoint to allow future retries
            console.error(`Failed to fetch palettes from "${endpoint}": ${error.message}`);
            _fetchesByEndpoint.delete(endpoint);
            return [];
        }
    })();

    // store the promise in cache for future use
    _fetchesByEndpoint.set(endpoint, fetchPromise);
    return fetchPromise;
}


//#=========================================================================#
//#                         PALETTE GALLERY DIALOG                          #
//# The SECOND generation of UI added a node button that launched a         #
//# GALLERY DIALOG, which in turn modified a native combo-box in ComfyUI.   #
//#                                                                         #

class PaletteGalleryDialogDelegate extends GalleryDialogDelegate {

    constructor(endpoint) {
        super();
        this.endpoint = endpoint;
    }

    /**
     * Fetches an array with data about each item to be displayed in the gallery.
     * @returns {Promise<Array<Object>>}
     *   A promise that resolves to an array of objects with the following properties:
     *       - idx        : Unique identifier for the item (the index in the list)
     *       - name       : The display name of the item (string)
     *       - category   : The category the item belongs to (string)
     *       - description: A detailed description of the item (string)
     *       - tags       : An string of comma-separated tags associated with the palette (string)
     *       - thumbnail  : URL for the item's thumbnail image (string)
     */
    async fetchItemArray() {
        return fetchColorPaletteArray(this.endpoint);
    }

    /**
     * Renders the image HTML element for the specified item.
     *
     * @param {Object|null} item      - The data object containing item information, or null if no item is selected.
     * @param {string}      value     - The display value/name of the item.
     * @param {Object}      options   - Configuration options for the gallery dialog.
     * @param {string}      htmlClass - The CSS class string to be applied to the resulting html tag.
     * @returns {string}
     *    The HTML string rendered for the provided item,
     *    or an empty string if the item or thumbnail is missing.
     */
    htmlItemImage(item, _value, _options, htmlClass) {

        // the thumbnail version is rendered with the `htmlColorPaletteThumb` method
        if( htmlClass.includes('thumb') ) {
            return this.htmlColorPaletteThumb(item, htmlClass);
        }

        const leftPercentage = 72;
        const rightPercentage = 25;

        if (!item || !item.colors || item.colors.length === 0) {
            return "";
        }

        const gapPercentage = 100 - leftPercentage - rightPercentage;
        const numOfColors   = item.colors.length;
        const colors4 = item.colors.slice(0, 4);

        const verticalBars = colors4.map(color => `
            <div style="background-color: ${color.hex}; flex: 1; height: 100%;"></div>
        `).join('');

        let horizontalBars = colors4.map(color => `
            <div style="background-color: ${color.hex}; flex: 1; width: 100%;"></div>
        `).join('');

        let rightPanel = horizontalBars;
        if (numOfColors >= 5) {
            // Reconstruct rightPanel to hold the original 4 bars, a spacer, and the 5th color as a circle
            rightPanel = `
                <div style="display: flex; flex-direction: column; height: ${leftPercentage}%; width: 100%;">
                    ${horizontalBars}
                </div>
                <div style="height: ${gapPercentage}%;"></div>
                <div style="display: flex; align-items: center; justify-content: center; height: ${rightPercentage}%; width: 100%;">
                    <div style="background-color: ${item.colors[4].hex}; aspect-ratio: 1 / 1; height: 100%; border-radius: 50%;"></div>
                </div>
            `;
        }
        return `
            <div class="${htmlClass}" style="
                             display   : flex;
                             overflow  : hidden;
                             border    : 1px solid rgba(0,0,0,0.15);
                             box-sizing: border-box;">

                <!-- Left Side -->
                <div style="display: flex; flex: ${leftPercentage}; height: 100%;">
                    ${verticalBars}
                </div>

                <!-- Gap -->
                <div style="flex: ${gapPercentage};"></div>

                <!-- Right Side -->
                <div style="display: flex; flex-direction: column; flex: ${rightPercentage}; height: 100%;">
                    ${rightPanel}
                </div>
            </div>
        `;
    }

    /**
     * Generates an HTML representation of a color palette in small thumbnail size.
     *
     * @param {Object|null} item        - The data object containing item information, or null if no item is selected.
     * @param {Array}       item.colors - Array of objects with a hex property.
     * @param {string}      htmlClass   - CSS class for the container.
     * @returns {string}
     *     An string containing the HTML representation of the color palette.
     */
    htmlColorPaletteThumb(item, htmlClass) {
        if( !item?.colors || !Array.isArray(item.colors) || item.colors.length === 0 ) {
            return "";
        }
        const colors = item.colors;
        const lastColorIndex = Math.min(colors.length-1, 3);

        // split the colors
        const mainColors     = colors.slice(0, lastColorIndex);       //< all colors except the last one
        const lastColor      = colors[lastColorIndex];                //< the last color
        const highlightColor = colors.length >= 5 ? colors[4] : null; //< the highlight color (fifth optional color)

        // create vertical bars using the main colors
        let verticalBars = mainColors
            .map(color => `<div style="flex: 1; height: 100%; background-color: ${color.hex};"></div>`)
            .join('');

        // add a vertical bar with the last color
        // (including an extra circle at the bottom representing the highlight if it exists)
        if (highlightColor) {
            const barPercentSize = 100 / (mainColors.length + 1);
            verticalBars += `
            <div style="flex: 1; height: 100%; display: flex; flex-direction: column;">
                <div style="height: ${100 - barPercentSize}%; width: 100%; background-color: ${lastColor.hex};"></div>
                <div style="display: flex; align-items: center; justify-content: center; height: ${barPercentSize}%; width: 100%; box-sizing: border-box;">
                    <div style="background-color: ${highlightColor.hex}; width: 100%; max-width: 100%; aspect-ratio: 1 / 1; border-radius: 50%;"></div>
                </div>
            </div>
            `;
        } else {
            verticalBars += `<div style="flex: 1; height: 100%; background-color: ${lastColor.hex};"></div>`;
        }
        return `
            <div class="${htmlClass}" style="display: flex; overflow: hidden; box-sizing: border-box;">
                ${verticalBars}
            </div>
        `;
    }

}

/**
 * Returns a palette selection dialog containing the palettes loaded from the specified endpoint.
 * @param {string} endpoint - The full endpoint URL to fetch the palettes from.
 * @returns {GalleryDialog}
 *   The gallery dialog instance for the specified endpoint
 * @example
 *   const paletteDialog  = requireColorPaletteGalleryDialog("/api/palettes/v1/list");
 *   const currentPalette = "Volcano";
 *   paletteDialog.launch({}, currentPalette, (selectedPalette) => {
 *       console.log("Selected Palette: " + selectedPalette);
 *   });
 */
function requireColorPaletteGalleryDialog(endpoint) {

    // check if a dialog is already registered for the specified endpoint
    const dialog = _dialogsByEndpoint.get(endpoint);
    if( dialog ) { return dialog; }

    // if no dialog exists for this endpoint, create a new one
    const newDelegate = new PaletteGalleryDialogDelegate(endpoint);
    const newDialog   = new GalleryDialog(newDelegate);
    _dialogsByEndpoint.set(endpoint, newDialog);
    return newDialog;
}


//#=========================================================================#
//#                         PALETTE GALLERY WIDGET                          #
//#   The THIRD generation of UI uses a "GALLERY WIDGET" to launch a        #
//#   "GALLERY DIALOG", both of them customized by 'delegate' objects.      #
//#                                                                         #

class PaletteWidgetDelegate extends GalleryWidgetDelegate {

    constructor(endpoint) {
        super();
        this.endpoint = endpoint;
    }

    /**
     * Fetches an array with data about each item to be displayed in the gallery.
     * @returns {Promise<Array<Object>>}
     *   A promise that resolves to an array of objects with the following properties:
     *       - idx        : Unique identifier for the item (the index in the list)
     *       - name       : The display name of the item (string)
     *       - category   : The category the item belongs to (string)
     *       - description: A detailed description of the item (string)
     *       - tags       : An string of comma-separated tags associated with the palette (string)
     *       - thumbnail  : URL for the item's thumbnail image (string)
     */
    async fetchItemArray() {
        return fetchColorPaletteArray(this.endpoint);
    }

    getItemText(item) {
        if( !item ) { return "Undefined"; }
        return `${item.name}\n${item.category}`;
    }

    /**
     * Called when a thumbnail needs to be drawn for a specific item.
     *
     * This implementation draws a thumbnail showing the color palette. It
     * is rendered with a fixed size of 32x32 pixels, aligned to the right
     * side of the supplied bounding box.
     *
     * @param {CanvasRenderingContext2D} ctx         - The canvas 2D rendering context.
     * @param {Object}                   rect        - The bounding box for the drawing operation.
     * @param {number}                   rect.left   - The left coordinate of the drawing area.
     * @param {number}                   rect.top    - The top coordinate of the drawing area.
     * @param {number}                   rect.width  - The total width of the available area.
     * @param {number}                   rect.height - The total height of the available area.
     * @param {Object|null}              item        - The data object containing the color palette.
     * @param {Array}                    item.colors - Array of color objects with a 'hex' property.
     * @param {string}                   _value      - The display value/name of the item.
     * @param {Object}                   _options    - The configuration options with which the widget was initialized.
     * @returns {number}
     *     The horizontal space occupied by the thumbnail.
     */
    drawItemThumbnail(ctx, rect, item, _value, _options) {
        if( !item?.colors || !Array.isArray(item.colors) || item.colors.length === 0 ) {
            return 0;
        }
        const THUMB_SIZE = 32;
        const colors = item.colors;
        const lastColorIndex = Math.min(colors.length-1, 3);
        const totalColumns   = lastColorIndex + 1;
        const colWidth       = THUMB_SIZE / totalColumns;

        // split the colors
        const mainColors     = colors.slice(0, lastColorIndex);       //< all colors except the last one
        const lastColor      = colors[lastColorIndex];                //< the last color
        const highlightColor = colors.length >= 5 ? colors[4] : null; //< the highlight color (fifth optional color)

        // position to the right of the rectangle, vertically centered
        const originX = rect.left + (rect.width  - THUMB_SIZE);
        const originY = rect.top  + (rect.height - THUMB_SIZE) / 2;

        // draw main bars
        mainColors.forEach((color, index) => {
            ctx.fillStyle = color.hex;
            ctx.fillRect(originX + (index * colWidth), originY, colWidth, THUMB_SIZE);
        });

        // draw last bar, which may or may not contain the highlight circle
        const lastColX = (lastColorIndex * colWidth);
        // if NO highlight color,
        // draw the bar all the way to the bottom
        if( !highlightColor ) {
            ctx.fillStyle = lastColor.hex;
            ctx.fillRect(originX + lastColX, originY, colWidth, THUMB_SIZE);
        }
        // if there is a highlight color,
        // draw the bar leaving space at the bottom
        else {
            ctx.fillStyle = lastColor.hex;
            ctx.fillRect(originX + lastColX, originY, colWidth, THUMB_SIZE-colWidth);
            // draw the circle with the highlight color at the bottom
            const radius = colWidth * 0.5;
            const cx = lastColX  + radius;
            const cy = THUMB_SIZE - radius;
            ctx.beginPath();
            ctx.arc(originX + cx, originY + cy, radius, 0, Math.PI * 2);
            ctx.fillStyle = highlightColor.hex;
            ctx.fill();
        }
        return THUMB_SIZE;
    }

    // Using the default implementation of drawItemText()
    // drawItemText(ctx, rect, line1, line2, item, value) { }
}
