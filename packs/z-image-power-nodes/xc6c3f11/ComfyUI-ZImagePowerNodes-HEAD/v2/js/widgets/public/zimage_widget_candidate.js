import { installUserInputComboWidgetTypes } from './combo_widget_types.js';
import { installSeparatorWidgetType } from './separator_widget_type.js';
import { installPredefinedGalleryWidgetTypes } from './predefined_gallery_widget_types.js';
import { installStyleGalleryButtonWidgetType } from './style_gallery_button_widget_type.js';

export const ZIMAGE_WIDGET_TYPES = Object.freeze([
    'ZIPN_STYLE','ZIPN_PALETTE','ZIPN_SEPARATOR',
    'ZIPN_PREDEFINED_STYLE','ZIPN_PREDEFINED_PALETTE','ZIPN_STYLE_GALLERY_BUTTON'
]);

/** Candidate entrypoint; original catalogue/modal dependencies are supplied by the pack. */
export function installZImageWidgetTypes(comfy,sources) {
    const components = [];
    try {
        components.push(installUserInputComboWidgetTypes(comfy));
        components.push(installSeparatorWidgetType(comfy));
        components.push(installPredefinedGalleryWidgetTypes(comfy,sources));
        components.push(installStyleGalleryButtonWidgetType(comfy,sources));
    } catch (error) {
        for (const component of components.reverse()) component.dispose();
        throw error;
    }
    let disposed = false;
    return {dispose() {
        if (disposed) return;
        disposed = true;
        for (const component of components.reverse()) component.dispose();
    }};
}
