/** ZImage public widgets and Top10 source candidate; runtime qualification pending. */
import {comfy} from '/comfy/api/v2.js';
import {installZImageGalleryFrontend} from './widgets/public/zimage_gallery_frontend.js';
import {installTopStylesFrontend} from './widgets/public/top_styles_frontend.js';
// The two parts install independently: a failure in one is logged and never
// disposes the other (rev 1 tore the galleries down when Top-10 failed).
function install(name,start) {
    try { return start(); }
    catch(error) { console.error(`[ZImagePowerNodes] ${name} unavailable:`,error);return null; }
}
export const zImageGalleryFrontend = install('style gallery widgets',() => installZImageGalleryFrontend(comfy, {
    stylesheetURL:new URL('./widgets/public/gallery_dialog.css',import.meta.url).href,
}));
export const topStylesFrontend = install('My Top-10 Styles controller',() => installTopStylesFrontend(comfy));
export function dispose() {
    for (const part of [topStylesFrontend,zImageGalleryFrontend]) {
        try { part?.dispose(); }
        catch(error) { console.error('[ZImagePowerNodes] dispose failed:',error); }
    }
}
