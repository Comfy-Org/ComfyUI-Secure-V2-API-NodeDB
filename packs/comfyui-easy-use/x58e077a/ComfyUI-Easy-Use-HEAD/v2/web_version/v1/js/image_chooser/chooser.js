import { comfy } from '/comfy/api/v2.js';

import { FlowState } from "./state.js";
import { begin_request, send_cancel, send_message, send_onstart } from "./messaging.js";
import { chooserState, createChooser, attachChooser, display_preview_images, resetSelections } from "./preview.js";
import {$t} from "../common/i18n.js";

// ./prompt.js is refused and no longer imported — see the note in it. The one
// consequence here is the "as restart" arm of the progress button.

const CHOOSER = 'easy imageChooser';

function showChooserDialog(node, images) {
    const state = chooserState(node.id);
    if (!state) return;

    const images_div = document.createElement('div');
    images_div.className = 'easyuse-chooser-dialog-images';
    images.forEach((img, index) => {
        const imgEl = document.createElement('img');
        imgEl.src = img.src;
        imgEl.addEventListener('click', () => {
            // One source of truth where the dialog used to keep its own
            // select_index alongside the node's set, and the two could drift.
            if (state.selected.has(index)) {
                state.selected.delete(index);
                imgEl.classList.remove('selected');
            } else {
                state.selected.add(index);
                imgEl.classList.add('selected');
            }
            update(node);
        });
        images_div.append(imgEl);
    });

    const title = document.createElement('h5');
    title.className = 'easyuse-chooser-dialog-title';
    title.textContent = $t('Choose images to continue');

    const choose = document.createElement('button');
    choose.textContent = $t('Choose Selected Images');
    const close = document.createElement('button');
    close.textContent = $t('Close');

    const dialog = comfy.ui.showDialog({
        key: 'easyuse.imageChooser',
        render: (container) => {
            container.classList.add('easyuse-chooser-dialog');
            container.append(title, images_div, choose, close);
        },
    });

    choose.addEventListener('click', () => {
        sendSelection(node);
        dialog.close();
    });
    close.addEventListener('click', () => {
        if (FlowState.running()) { send_cancel(); }
        dialog.close();
    });
}

function sendSelection(node) {
    const state = chooserState(node.id);
    if (!state) return;
    if (FlowState.paused()) {
        send_message(node.id, [...state.selected, -1, ...state.anti_selected]);
    }
}

function progressButtonPressed(node) {
    const state = chooserState(node.id);
    if (!state) return;
    const selected = [...state.selected]
    if(selected?.length>0){
        node.setProperty('values',selected)
    }
    sendSelection(node);
}

function cancelButtonPressed() {
    if (FlowState.running()) { send_cancel();}
}

function imageClicked(node, imageIndex) {
    const state = chooserState(node.id);
    if (!state) return;
    if (state.selected.has(imageIndex)) state.selected.delete(imageIndex);
    else state.selected.add(imageIndex);
    update(node);
}

function update(node) {
    const state = chooserState(node.id);
    if (!state) return;
    // A sampler node holds picks but has no buttons and no grid of ours.
    if (state.progress) {
        const selection = state.selected.size + state.anti_selected.size;
        const maxlength = state.imgs.length;
        // The "…as restart" arm is gone with restart_from_here: away from its own
        // pause the button had nothing left to do, and an enabled button that does
        // nothing is worse than a disabled one. enable_disabling's defineProperty
        // on `clicked` said the same thing through a litegraph internal.
        const canProgress = selection > 0 && FlowState.paused_here(node.id);
        const progressLabel = !canProgress ? ""
            : (selection>1) ? "Progress selected (" + selection + '/' + maxlength  +")"
            : "Progress selected image";
        state.progress.setLabel(progressLabel);
        state.progress.setDisabled(!progressLabel);

        const cancelLabel = FlowState.running() ? "Cancel current run" : "";
        state.cancel.setLabel(cancelLabel);
        state.cancel.setDisabled(!cancelLabel);
    }
    state.surface?.redraw();
}

function updateAll() {
    for (const node of comfy.graph.nodesOfType(CHOOSER)) update(node);
}

/*
If a run is interrupted, send a cancel message (unless we're doing the cancelling, to avoid infinite loop)
*/
comfy.queue.onInterrupted(() => {
    if (FlowState.cancelling) { FlowState.cancelling = false; return; }
    if (FlowState.paused()) send_cancel();
});

/*
At the start of execution
*/
comfy.backend.on("execution_start", () => {
    if (send_onstart()) {
        resetSelections();
        updateAll();
    }
});

comfy.backend.on("secure-node-interaction", (detail) => {
    if (detail?.kind !== "image-choice") return;
    begin_request(detail.node_id, detail.request_id);
    const shown = display_preview_images({
        id: detail.node_id,
        urls: detail.payload?.images ?? [],
    });
    if (shown?.isKSampler) {
        showChooserDialog(shown.node, shown.image);
    }
});

// Was the extension's init(): the module body runs at the same point.
window.addEventListener("beforeunload", send_cancel, true);

// Replaces the per-frame LGraphCanvas.draw override, whose whole job was to
// notice that the running node had changed and re-label every chooser.
comfy.onExecutingNodeChanged(() => { updateAll(); });

comfy.defs.extend(CHOOSER, (b) => {
    b.onCreated((node) => {
        node.setProperty('values',[])
        const state = createChooser(node.id);

        // Named where the originals were nameless: a widget id is
        // `graphId:nodeId:name`, so two widgets called "" cannot both exist. The
        // name never reaches the wire — widgets_values holds values only — but an
        // empty name was also what kept these two out of the API prompt, so
        // disable_serialize's options.serialize is now load-bearing rather than
        // belt-and-braces.
        state.progress = node.widgets.add({ type: "button", name: "chooser_progress", value: "" });
        state.progress.setOption('serialize', false);
        state.progress.on('activate', () => progressButtonPressed(node));

        state.cancel = node.widgets.add({ type: "button", name: "chooser_cancel", value: "" });
        state.cancel.setOption('serialize', false);
        state.cancel.on('activate', () => cancelButtonPressed());

        // Mounted after the buttons deliberately. A canvas widget is not
        // serialized, and serialize() writes each value at its own index — so
        // last is the one position where its empty slot cannot lengthen
        // widgets_values. The two buttons keep their "" entries and the saved
        // workflow is unchanged.
        attachChooser(node, state, (i) => imageClicked(node, i));

        update(node);
    });
});
