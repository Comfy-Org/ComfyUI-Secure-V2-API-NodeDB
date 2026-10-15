import {createGalleryCatalogue} from './gallery_catalogue.js';
import {createPublicGalleryDialogs} from './public_gallery_dialog.js';
import {createGalleryDialogDelegates} from './gallery_dialog_delegates.js';
import {styleSamplePath} from './style_sample_path.js';

export function createZImageGallerySources(comfy,{fetchEndpoint,stylesheetURL}={}) {
    // In the secure guest this is the actual pack-owned route capability.
    // The direct public API test passes its actual BackendHandle.fetch caller.
    const fetchOwned=fetchEndpoint ?? (endpoint=>comfy.backend.ownFetch(endpoint));
    function resolveImageURL(endpoint) {
        const url=new URL(endpoint,'https://pack.invalid/');
        if (url.pathname !== '/zi_power/styles/samples') return endpoint;
        const path=styleSamplePath(url.searchParams.get('file'));
        url.searchParams.delete('file');
        const query=url.searchParams.toString();
        return comfy.backend.assetUrl(path)+(query?'?'+query:'');
    }
    const catalogue=createGalleryCatalogue(fetchOwned,resolveImageURL);
    const dialogs=createPublicGalleryDialogs(comfy,{stylesheetURL});
    const delegates=createGalleryDialogDelegates(catalogue,dialogs,resolveImageURL);
    let disposed=false;
    function thumbnail(delegate,htmlDelegate) {
        const markupByContainer=new WeakMap();
        delegate.mountThumbnail=(container,item,value,options)=>{
            const markup=htmlDelegate.htmlItemImage(item,value,options,'zipn-widget-thumb');
            if (markupByContainer.get(container)!==markup) {
                container.innerHTML=markup;markupByContainer.set(container,markup);
            }
            container.style.cssText=markup?'display:block;width:32px;height:32px;flex:none':'';
            const image=container.querySelector('img');
            const preview=container.firstElementChild;
            if (preview) {preview.style.width='32px';preview.style.height='32px';}
            if (image) {
                // Native StyleWidgetDelegate paints this exact pending square.
                image.style.backgroundColor='#2a2a2a';
            }
            return ()=>{};
        };
        return delegate;
    }
    return {
        catalogue,dialogs,delegates,resolveImageURL,
        styleDelegate(endpoint,imagesURL) {
            return thumbnail(new catalogue.StyleWidgetDelegate(endpoint,imagesURL),
                new delegates.StyleDialogDelegate(endpoint,imagesURL));
        },
        paletteDelegate(endpoint) {
            return thumbnail(new catalogue.PaletteWidgetDelegate(endpoint),
                new delegates.PaletteGalleryDialogDelegate(endpoint));
        },
        launchDialog(kind,config,value,onSelect) {
            if (disposed) return;
            const dialog=kind==='style'
                ? delegates.requireVisualStyleGalleryDialog(config.endpoint,config.images_url ?? '')
                : delegates.requireColorPaletteGalleryDialog(config.endpoint);
            dialog.launch(config,value,onSelect);
        },
        launchStyleDialog(endpoint,imagesURL,config,value,onSelect) {
            if (!disposed) delegates.requireVisualStyleGalleryDialog(endpoint,imagesURL).launch(config,value,onSelect);
        },
        dispose() {if(!disposed){disposed=true;dialogs.dispose();}}
    };
}
