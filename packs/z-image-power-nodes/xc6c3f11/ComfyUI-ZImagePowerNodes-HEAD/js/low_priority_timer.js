/**
 * File    : low_priority_timer.js
 * Purpose : A timer for low priority tasks.
 * Author  : Martin Rizzo | <martinrizzo@gmail.com>
 * Date    : Feb 1, 2026
 * Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
 * License : MIT
 *- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
 *                        ComfyUI-ZImagePowerNodes
 *       ComfyUI nodes designed specifically for the "Z-Image" model.
 *_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
*/
import { app } from "../../../scripts/app.js";
import { executeLowPriorityTasks } from "./common_timer.js";
const ENABLED = true;


//#=========================================================================#
//#////////////////////////// REGISTER EXTENSION ///////////////////////////#
//#=========================================================================#

app.registerExtension({
    name: "ZImagePowerNodes.LowPriorityTimer",

    /** Called when the extension is loaded. */
    init() {
        if (!ENABLED) return;
        console.log(`[${this.name}]: Extension loaded.`);
    },


    async setup() {
        const restartTimer = () => {
            setTimeout(() => {
                // eslint-disable-next-line
                (window.requestIdleCallback || window.setTimeout)(() => {

                    // execute the low priority tasks and restart the timer
                    executeLowPriorityTasks();
                    restartTimer();

                }, { timeout: 10000 });
            }, 1000);
        };

        // start the timer
        restartTimer();
    },

});
