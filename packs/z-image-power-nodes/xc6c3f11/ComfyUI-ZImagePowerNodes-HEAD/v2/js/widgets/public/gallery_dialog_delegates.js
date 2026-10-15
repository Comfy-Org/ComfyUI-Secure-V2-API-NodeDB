/** Original gallery delegates and per-endpoint dialog registries; Martin Rizzo, MIT. */
export function createGalleryDialogDelegates(catalogue,dialogs,resolveImageURL) {
const {GalleryDialog,GalleryDialogDelegate}=dialogs;
const style=(()=>{
const _dialogsByEndpoint=new Map();
const fetchVisualStyleArray=catalogue.fetchVisualStyleArray;
class StyleDialogDelegate extends GalleryDialogDelegate {

    constructor(endpoint, imagesURLTemplate) {
        super();
        this.endpoint          = endpoint;
        this.imagesURLTemplate = imagesURLTemplate;
    }

    /**
     * Fetches an array with data about each item to be displayed in the gallery.
     * @returns {Promise<Array<Object>>}
     *   A promise that resolves to an array of objects with the following properties:
     *       - idx        : Unique identifier for the item (the index in the list)
     *       - name       : The display name of the item (string)
     *       - category   : The category the item belongs to (string)
     *       - description: A detailed description of the item (string)
     *       - tags       : An string of comma-separated tags associated with the style (string)
     *       - slug       : url-friendly slug (used for building thumbnail filenames)
     */
    async fetchItemArray() {
        return fetchVisualStyleArray(this.endpoint);
    }

    /**
     * Returns an array of category definitions used for filtering the gallery items.
     * @returns {Array<Array<string>>}
     *   An array of category definitions where each item contains:
     *     - category    (string): The value used for matching gallery items (must match the "category" property in items)
     *     - displayName (string): The visible name shown in the UI
     *     - description (string): Tooltip description for screen readers/accessibility
     */
    getCategories() {
        return [
        /*   CATEGORY        DISPLAY_NAME    DESCRIPTION                      */
            [""            , "All"         , "Search all styles"               ],
            ["photo"       , "Photo"       , "Search only photographic styles" ],
            ["illustration", "Illustration", "Search only illustration styles" ],
            ["wild"        , "Wild"        , "Search only wild styles"         ],
            ["custom"      , "Custom"      , "Search only custom styles"       ]
        ];
    }

    /**
     * Renders the main image HTML element for the selected item.
     *
     * This implementation renders a lazy-loaded image using the item's
     * properties and the template stored in `this.imagesURLTemplate`,
     * or returns an empty string if the item is `null` or invalid.
     *
     * @param {Object|null} item      - The data object representing the item, or `null` if no item is selected.
     * @param {string}      value     - The value of the item, as reported to the backend.
     * @param {Object}      options   - An object containing the options with which the dialog was configured.
     * @param {string}      htmlClass - CSS class to be applied to the img tag
     * @returns {string}
     *    The HTML string representing the image element
     *    or an empty string if the item is `null` or invalid.
     */
    htmlItemImage(item, value, options, htmlClass) {
        if( !item?.slug ) { return ""; }
        const data = {
            slug       : item.slug,
            file       : `${item.slug}.jpg`,
            size       : htmlClass.includes('thumb') ? "small" : "big",
            cachebuster: options.cache_buster
        };
        const imageURL = resolveImageURL(this.imagesURLTemplate.replace(/{(\w+)}/g, (match, key) => data[key] ?? match));
        return `<img class="${htmlClass}" src="${imageURL}" loading="lazy" alt="${value | ""}"/>`;
    }

}
function requireVisualStyleGalleryDialog(endpoint, imagesURLTemplate) {

    // check if a dialog is already registered for the specified endpoint
    const dialog = _dialogsByEndpoint.get(endpoint);
    if( dialog ) { return dialog; }

    // If no dialog exists for this endpoint, create a new one
    const newDelegate = new StyleDialogDelegate(endpoint, imagesURLTemplate);
    const newDialog   = new GalleryDialog(newDelegate);
    _dialogsByEndpoint.set(endpoint, newDialog);
    return newDialog;
}
return {StyleDialogDelegate,requireVisualStyleGalleryDialog};
})();
const palette=(()=>{
const _dialogsByEndpoint=new Map();
const fetchColorPaletteArray=catalogue.fetchColorPaletteArray;
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
return {PaletteGalleryDialogDelegate,requireColorPaletteGalleryDialog};
})();
return {...style,...palette};
}
