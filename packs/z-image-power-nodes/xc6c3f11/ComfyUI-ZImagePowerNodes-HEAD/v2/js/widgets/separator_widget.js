export { SeparatorWidget };
import { LiteGraph } from "../comfyui_bridge.js";
const DEFAULT_WIDGET_HEIGHT = 20;


class SeparatorWidget {

    /**
     * Creates a new StyleSelectorWidget instance
     * @param {Object} node - The node to attach the widget to
     * @param {string} inputName - The name of the input
     * @param {Array} inputData - The input data array [type, options]
     */
    constructor(type, name, options) {
        this.type      = type;
        this.name      = name;
        this.serialize = true,
        this.options   = {
            socketless: true,
            mode      : "spacer",
            color     : null,
            height    : DEFAULT_WIDGET_HEIGHT,
            thickness : null,
            ...options
        };

        // bind methods to ensure correct 'this' context
        this.draw        = this.draw.bind(this);
        this.computeSize = this.computeSize.bind(this);
    }

   /**
     * Draws the widget elements: thumbnail, arrows and text
     * @param {CanvasRenderingContext2D} ctx - The canvas context
     * @param {Object} node - The node object
     * @param {number} widgetWidth - The widget width
     * @param {number} y - The y position
     * @param {number} widgetHeight - The widget height
     */
    draw(ctx, node, widgetWidth, y, _widgetHeight) {
        const mode      = this?.options?.mode   || "spacer";
        const color     = this?.options?.color  || LiteGraph.NODE_DEFAULT_BOXCOLOR; //WIDGET_BGCOLOR; //WIDGET_OUTLINE_COLOR;
        const height    = this?.options?.height || DEFAULT_WIDGET_HEIGHT;
        const thickness = this?.options?.thickness;

        // the "spacer" mode renders nothing, providing only vertical padding
        if( mode === "spacer") { return; }

        // center the separator vertically
        const left    = Math.trunc(10);
        const right   = Math.trunc(widgetWidth - 10);
        const centerY = Math.trunc(y + height/2 + 0.5);

        // draw the separator
        ctx.save();
        ctx.strokeStyle = color;
        ctx.beginPath();
        switch( mode )
        {
            // standard thin horizontal line
            case "divider":
            default:
                ctx.lineWidth = thickness || 1;
                ctx.setLineDash([]);
                break;

            // dashed line for visual grouping
            case "dotted":
                ctx.lineWidth = thickness || 2;
                ctx.setLineDash([2, 2]);
                break;

            // thick line for strong section separation
            case "bold":
                ctx.lineWidth = thickness || 6;
                ctx.setLineDash([]);
                break;
        }
        ctx.moveTo(left, centerY);
        ctx.lineTo(right, centerY);
        ctx.stroke();
        ctx.restore();
    }

    /**
     * Computes the widget size
     * @param {number} widgetWidth - The widget width
     * @returns {Array} The computed size [width, height]
     */
    computeSize(widgetWidth) {
        const widgetHeight = this?.options?.height || 20;
        return [widgetWidth, widgetHeight];
    }

    serializeValue() {
        return null;
    }
}
