import {installZImageWidgetTypes} from './zimage_widget_candidate.js';
import {createZImageGallerySources} from './zimage_gallery_sources.js';

/** The six registered widget types, actual catalogue delegates and public modal. */
export function installZImageGalleryFrontend(comfy,options={}) {
    const sources=createZImageGallerySources(comfy,options);
    let widgets;
    try {widgets=installZImageWidgetTypes(comfy,sources);}
    catch(error) {sources.dispose();throw error;}
    let disposed=false;
    return {sources,dispose() {
        if (disposed) return;
        disposed=true;
        widgets.dispose();sources.dispose();
    }};
}
