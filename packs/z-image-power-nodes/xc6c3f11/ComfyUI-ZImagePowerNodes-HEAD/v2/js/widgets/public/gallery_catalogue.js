/** Catalogue functions and delegate methods from Martin Rizzo, MIT, ZImage Power Nodes 2.1.1. */
export function createGalleryCatalogue(fetchEndpoint,resolveImageURL=(url)=>url) {
const style=(()=>{
const _fetchesByEndpoint=new Map();
async function fetchVisualStyleArray(endpoint)
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
            // fetch the styles from the given endpoint
            const response = await fetchEndpoint(endpoint);
            if( !response.ok ) { throw new Error(`HTTP ${response.status}`); }

            // validate that the response is an actual array
            const styles = await response.json();
            if( !Array.isArray(styles) ) { throw new Error(`Expected an array but received ${typeof palettes}`); }

            return styles.map((style, index) => {
                return {
                    idx        : index,
                    name       : style[0] || "Unknown",
                    category   : style[1] || "Uncategorized",
                    description: style[2] || "",
                    tags       : style[3] || "",
                    slug       : style[4] || style[0] || "" // url-friendly slug (used for thumbnail filenames)
                };
            });

        } catch (error) {
            // if failed, delete the cache for this endpoint to allow future retries
            console.error(`Failed to fetch styles from "${endpoint}": ${error.message}`);
            _fetchesByEndpoint.delete(endpoint);
            return [];
        }
    })();

    // store the promise in cache for future use
    _fetchesByEndpoint.set(endpoint, fetchPromise);
    return fetchPromise;
}
class StyleWidgetDelegate {

    constructor(endpoint, imagesURLTemplate) {
        this.endpoint = endpoint;
        this.imagesURLTemplate = imagesURLTemplate;
    }

    async fetchItemArray() {
        return fetchVisualStyleArray(this.endpoint);
    }

    getItemText(item, value, options) {
        if( !item ) { return "Undefined"; }
        if( options.allow_variants ) {
            const parts = item.name.split("//");
            const name      = parts[0]?.trim() || "";
            const variation = parts[1]?.trim() || "";
            return `${name}\n${variation}`;
        }
        return item.name;
    }

    /**
     * Draws the image/thumbnail for a specific item.
     *
     * @param {CanvasRenderingContext2D} ctx - The canvas 2D rendering context
     * @param {Object}   rect    - The rectangle object defining the drawing area (left, top, width, height)
     * @param {Object}   item    - The data of the item to be drawn
     * @param {string}   value   - The current value of the widget as reported to the backend
     * @param {Object}   options - An object containing the options with which the widget was configured
     * @param {Function} requestImage - A function to request an image from a URL
     * @returns {number}
     *     The width (in pixels) occupied by the thumbnail, representing the
     *     space used on the right side of the drawing area.
     */
    drawItemThumbnail(ctx, rect, item, value, options, requestImage) {
        if( !item?.slug ) { return 0; }

        const data       = {
            slug       : item.slug,
            file       : `${item.slug}.jpg`,
            size       : "small",
            cachebuster: options.cache_buster
        };
        const thumbSize  = 32;
        const rect_right = rect.left + rect.width;
        const imageURL   = resolveImageURL(this.imagesURLTemplate.replace(/{(\w+)}/g, (match, key) => data[key] ?? match));
        const image      = requestImage(imageURL);

        // if the image is fully loaded, draw it!!
        if( image.complete && image.naturalWidth > 0 ) {
            const x = rect_right - thumbSize;
            const y = rect.top + (rect.height - thumbSize) / 2;
            ctx.drawImage(image, x, y, thumbSize, thumbSize);
        }
        // draw a temporary placeholder (e.g., a subtle gray square)
        // while the image is being downloaded in the background
        else {
            ctx.fillStyle = "#2a2a2a";
            const x = rect_right - thumbSize;
            const y = rect.top + (rect.height - thumbSize) / 2;
            ctx.fillRect(x, y, thumbSize, thumbSize);
        }
        return thumbSize;
    }
}
return {fetchVisualStyleArray,StyleWidgetDelegate};
})();
const palette=(()=>{
const _fetchesByEndpoint=new Map();
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
            const response = await fetchEndpoint(endpoint);
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
class PaletteWidgetDelegate {

    constructor(endpoint) {
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
return {fetchColorPaletteArray,PaletteWidgetDelegate};
})();
return {...style,...palette};
}
