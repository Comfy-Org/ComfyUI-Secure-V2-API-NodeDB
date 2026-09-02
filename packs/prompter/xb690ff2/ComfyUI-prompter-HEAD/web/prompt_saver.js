import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "ComfyUI.PromptSaver",
    async nodeCreated(node) {
        if (node.comfyClass !== "PromptSaverNode") return;

        console.log("[PromptSaver] Node initialized.");
        const titleDropdown = node.widgets.find(w => w.name === "selected_title");
        const autoSaveWidget = node.widgets.find(w => w.name === "auto_save");
        const titleNameWidget = node.widgets.find(w => w.name === "title_name");
        const promptWidget = node.widgets.find(w => w.name === "prompt_text");

        let isLoadingFromDropdown = false;
        let lastSavedPrompt = "";
        let lastSavedTitle = "";
        let autoSaveTimer = null;
        let hasChanges = false;

        function generateDefaultTitle() {
            const now = new Date();
            const dateStr = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
            let wfName = "Prompt";
            if (app.graph?.extra?.workflow_name) {
                wfName = app.graph.extra.workflow_name.replace(/\s+/g, '_');
            }
            return `${dateStr}_${wfName}`;
        }

        if (!titleNameWidget.value) titleNameWidget.value = generateDefaultTitle();

        async function refreshDropdown() {
            try {
                const res = await fetch("/prompt_saver/get_titles");
                const titles = await res.json();
                titleDropdown.options.values = titles;
                if (!titles.includes(titleDropdown.value)) titleDropdown.value = "[New Prompt]";
            } catch (e) { console.error("[PromptSaver] Dropdown refresh error:", e); }
        }
        await refreshDropdown();
        setInterval(refreshDropdown, 60000);

        async function fetchContent(title) {
            isLoadingFromDropdown = true;
            hasChanges = false;
            clearTimeout(autoSaveTimer);
            try {
                const res = await fetch(`/prompt_saver/get_content?title=${encodeURIComponent(title)}`);
                const text = await res.text();
                promptWidget.value = text;
                titleNameWidget.value = title;
                lastSavedPrompt = text;
                lastSavedTitle = title;
                node.setDirtyCanvas(true, true);
                console.log(`[PromptSaver] Loaded: ${title}`);
            } catch (e) { console.error("[PromptSaver] Load error:", e); }
            isLoadingFromDropdown = false;
        }

        const origDropdownCallback = titleDropdown.callback;
        titleDropdown.callback = (value) => {
            if (origDropdownCallback) origDropdownCallback.apply(titleDropdown, arguments);
            if (value !== "[New Prompt]") {
                fetchContent(value);
            } else {
                promptWidget.value = "";
                titleNameWidget.value = generateDefaultTitle();
                lastSavedPrompt = "";
                lastSavedTitle = "";
                hasChanges = false;
                node.setDirtyCanvas(true, true);
            }
        };

        function scheduleAutoSave() {
            if (isLoadingFromDropdown || !autoSaveWidget.value) return;
            hasChanges = true;
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(async () => {
                if (hasChanges) await performAutoSave();
            }, 60000);
        }

        async function performAutoSave() {
            const currentTitle = titleNameWidget.value.trim();
            const currentPrompt = promptWidget.value;
            if (!currentTitle || currentTitle === "[New Prompt]") return;

            try {
                const checkRes = await fetch(`/prompt_saver/check_title?title=${encodeURIComponent(currentTitle)}`);
                const checkData = await checkRes.json();
                const titleToSave = checkData.available_title || currentTitle;

                console.log(`[PromptSaver] Auto-saving as: ${titleToSave}`);
                await savePrompt(titleToSave, true);
                hasChanges = false;
            } catch (e) { console.error("[PromptSaver] Auto-save check failed:", e); }
        }

        async function savePrompt(titleToUse, isAuto = false) {
            const title = titleToUse || titleNameWidget.value.trim();
            const text = promptWidget.value;
            if (!title || title === "[New Prompt]") return;

            try {
                const res = await fetch("/prompt_saver/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, text })
                });
                if (res.ok) {
                    const result = await res.json();
                    console.log(`[PromptSaver] ${isAuto ? 'Auto-saved' : 'Saved'}: ${result.title}`);
                    await refreshDropdown();
                    titleDropdown.value = result.title;
                    lastSavedPrompt = text;
                    lastSavedTitle = result.title;
                }
            } catch (e) { console.error("[PromptSaver] Save error:", e); }
        }

        const bindWidget = (widget) => {
            const orig = widget.callback;
            widget.callback = (value) => {
                if (orig) orig.apply(widget, arguments);
                scheduleAutoSave();
            };
        };
        bindWidget(titleNameWidget);
        bindWidget(promptWidget);

        const origAutoCallback = autoSaveWidget.callback;
        autoSaveWidget.callback = (value) => {
            if (origAutoCallback) origAutoCallback.apply(autoSaveWidget, arguments);
            if (!value) {
                clearTimeout(autoSaveTimer);
                hasChanges = false;
                console.log("[PromptSaver] Auto-save disabled. Timer cleared.");
            }
        };

        node.addWidget("button", "💾 Save Prompt", "save_btn", async () => {
            console.log("[PromptSaver] Manual save triggered.");
            clearTimeout(autoSaveTimer);
            hasChanges = false;
            const currentTitle = titleNameWidget.value.trim();
            if (currentTitle && currentTitle !== "[New Prompt]") {
                await savePrompt(currentTitle, false);
            }
        });
    }
});