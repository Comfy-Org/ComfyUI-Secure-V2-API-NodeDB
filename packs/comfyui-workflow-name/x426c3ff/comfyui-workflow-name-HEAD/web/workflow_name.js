/**
 * WorkflowName - フロントエンド
 *
 * app.queuePrompt をフックして、キュー投入前にworkflow名をサーバーへ送信する。
 * これにより1枚目からPython側に正しい名前が渡る。
 */

import { app } from "../../scripts/app.js";

const FALLBACK = "NO_WORKFLOW_NAME";

/** activeWorkflow.filename からworkflow名を取得する */
function getCurrentName() {
    try {
        const filename = app.extensionManager?.workflow?.activeWorkflow?.filename;
        if (filename) return filename;
    } catch (e) {
        console.warn("[WorkflowName] Failed to read activeWorkflow.filename:", e);
    }
    return FALLBACK;
}

/** グラフ内のすべてのWorkflowNameノードのwidget.valueを更新する */
function updateNodes(name) {
    if (!app.graph?._nodes) return;
    for (const node of app.graph._nodes) {
        if (node.type !== "WorkflowName") continue;
        for (const widget of node.widgets ?? []) {
            if (widget.name === "workflow_name") {
                widget.value = name;
            }
        }
    }
}

/** サーバーにworkflow名を送り、サニタイズ済みの名前を受け取る */
async function pushNameToServer(rawName) {
    try {
        const res = await fetch("/workflow_name/set", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: rawName }),
        });
        const data = await res.json();
        return data.name || FALLBACK;
    } catch (e) {
        console.warn("[WorkflowName] Server unreachable:", e);
        return FALLBACK;
    }
}

app.registerExtension({
    name: "WorkflowName",

    async setup() {
        // app.queuePrompt をフックして送信完了後にキュー投入する
        const origQueuePrompt = app.queuePrompt.bind(app);
        app.queuePrompt = async function (...args) {
            const raw = getCurrentName();
            const sanitized = await pushNameToServer(raw);
            updateNodes(sanitized);
            console.log("[WorkflowName] queuePrompt -> name:", sanitized);
            return origQueuePrompt(...args);
        };

        console.log("[WorkflowName] Extension loaded.");
    },
});
