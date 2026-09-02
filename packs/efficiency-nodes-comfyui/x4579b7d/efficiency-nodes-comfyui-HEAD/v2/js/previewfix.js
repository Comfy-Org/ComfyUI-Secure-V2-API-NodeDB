import { comfy } from '/comfy/api/v2.js';

const previewfix = {
    lastExecutedNodeId: null,
    blobsToRevoke: [], // Array to accumulate blob URLs for revocation
    debug: false,

    log(...args) {
        if (this.debug) console.log(...args);
    },

    error(...args) {
        if (this.debug) console.error(...args);
    },

    shouldRevokeBlobForNode(nodeId) {
        const node = nodeId == null ? undefined : comfy.graph.node(String(nodeId));

        const validTitles = [
            "KSampler (Efficient)",
            "KSampler Adv. (Efficient)",
            "KSampler SDXL (Eff.)"
        ];

        if (!node || !validTitles.includes(node.getTitle())) {
            return false;
        }

        const getValue = name => node.widgets.get(name)?.getValue();
        return getValue("preview_method") !== "none" && String(getValue("vae_decode")).includes("true");
    },
};

comfy.onReady(() => {
    // Intercepting blob creation to store and immediately revoke the last blob URL
    const originalCreateObjectURL = URL.createObjectURL;
    URL.createObjectURL = (object) => {
        const blobURL = originalCreateObjectURL(object);
        if (blobURL.startsWith('blob:')) {
            previewfix.log("[BlobURLLogger] Blob URL created:", blobURL);

            // If the current node meets the criteria, add the blob URL to the revocation list
            if (previewfix.shouldRevokeBlobForNode(previewfix.lastExecutedNodeId)) {
                previewfix.blobsToRevoke.push(blobURL);
            }
        }
        return blobURL;
    };

    // Listen to the start of the node execution to revoke all accumulated blob URLs
    comfy.backend.on("executing", (detail) => {
        if (previewfix.lastExecutedNodeId !== detail || detail === null) {
            previewfix.blobsToRevoke.forEach(blob => {
                previewfix.log("[BlobURLLogger] Revoking Blob URL:", blob);
                URL.revokeObjectURL(blob);
            });
            previewfix.blobsToRevoke = []; // Clear the list after revoking all blobs
        }

        // Update the last executed node ID
        previewfix.lastExecutedNodeId = detail;
    });

    previewfix.log("[BlobURLLogger] Hook attached.");
});
