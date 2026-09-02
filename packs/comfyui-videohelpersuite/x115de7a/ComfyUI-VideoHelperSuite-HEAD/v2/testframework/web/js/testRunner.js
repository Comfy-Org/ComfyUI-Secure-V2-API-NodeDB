
import { comfy } from '/comfy/api/v2.js';

let watched_nodes = {}
let resolve = undefined
let testURL = comfy.backend.url("/VHS_test")
let errors = []
comfy.backend.on("executed", async function (detail) {
    if (watched_nodes && watched_nodes[detail?.node]) {
        if (detail?.output?.unfinished_batch) {
            return
        }
        let requestBody = {tests: watched_nodes[detail.node], output: detail.output}
        try {
            let req = await fetch(comfy.backend.url("/VHS_test"),
                {method: "POST", body: JSON.stringify(requestBody)});
            let testResult = await req.json()
            if (testResult.length != 0) {
                errors.push(testResult)
            }
        } catch(e) {
            errors.push(e)
        }
        if (!(watched_nodes.length -= 1)) {
            resolve()
        }
    }
});

async function runTest(file) {
    if (!file?.name?.endsWith(".json")) {
        return false
    }
    let workflow = JSON.parse(await file.text())
    await comfy.workflow.open(workflow)
    //NOTE: API is not used so workflow data is actually processed
    watched_nodes = workflow.tests
    errors = []
    let p = new Promise((r) => resolve = r)
    await comfy.queue.run()
    //block until execution completes
    await p
    watched_nodes = {}
    if (errors.length > 0) {
        comfy.commands.notify({severity: 'error',
            summary: "Failed " + errors.length + " tests",
            detail: "" + errors})
        return true
    }
    await comfy.commands.run('Workspace.CloseWorkflow')
    return false
}
let iconOverride = document.createElement("style")
iconOverride.innerHTML = `.VHSTestIcon:before {content: '🧪';}`
document.body.append(iconOverride)

comfy.ui.addSidebarTab({id: 'VHStest', title: 'VHS Test', icon: 'VHSTestIcon',
    render: (e) => {
        e.innerHTML = `Select a folder containing tests
        <input>
        Or select a single test
        <input>
            `

        const folderInput = e.children[0]
        const fileInput = e.children[1]
        Object.assign(folderInput, {
            type: "file",
            webkitdirectory: true,
            onchange: async function() {
                const startTime = Date.now()
                let failedTests = false
                for(const file of this.files) {
                    failedTests ||= await runTest(file)
                }
                this.value=""
                if (!failedTests) {
                    console.log("All tests passed in " + ((Date.now() - startTime)/1000) + "s")
                }
            },
        });
        Object.assign(fileInput, {
            type: "file",
            accept: ".json",
            onchange: async function() {
                if (this.files.length) {
                    if(!(await runTest(this.files[0]))) {
                        console.log("Test complete")
                    }
                    this.value=""
                }
            },
        });
    }})
