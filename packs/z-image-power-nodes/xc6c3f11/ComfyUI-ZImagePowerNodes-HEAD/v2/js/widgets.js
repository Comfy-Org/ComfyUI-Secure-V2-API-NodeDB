/** ZImage public widgets and Top10 source candidate; runtime qualification pending. */
import {comfy} from '/comfy/api/v2.js';
import {installZImageGalleryFrontend} from './widgets/public/zimage_gallery_frontend.js';
import {installTopStylesFrontend} from './widgets/public/top_styles_frontend.js';
export const zImageGalleryFrontend = installZImageGalleryFrontend(comfy, {
    stylesheetURL:new URL('./widgets/public/gallery_dialog.css',import.meta.url).href,
});
let topStyles;
try { topStyles=installTopStylesFrontend(comfy); }
catch(error) { zImageGalleryFrontend.dispose();throw error; }
export function dispose() { topStyles.dispose();zImageGalleryFrontend.dispose(); }
