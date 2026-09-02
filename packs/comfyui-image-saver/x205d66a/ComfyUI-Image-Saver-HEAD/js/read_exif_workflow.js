import { app } from '../../scripts/app.js'
import { ExifReader } from './lib/exif-reader.js' // https://github.com/mattiasw/ExifReader v4.26.2

const SETTING_CATEGORY_NAME = "Image Saver";
const SETTING_SECTION_FILE_HANDLING = "File Handling";

app.registerExtension({
    name: "ComfyUI-Image-Saver",
    settings: [
        {
            id: "ImageSaver.HandleImageWorkflowDrop",
            name: "Use a custom file drop handler to load workflows from JPEG and WEBP files",
            type: "boolean",
            defaultValue: true,
            category: [SETTING_CATEGORY_NAME, SETTING_SECTION_FILE_HANDLING, "Custom File Drop Handler"],
            tooltip:
                "Use a custom file handler for dropped JPEG and WEBP files.\n" +
                "This is needed to load embedded workflows.\n" +
                "Only disable this if it interferes with another extension's file drop handler.",
        },
    ],
    async setup() {
        // Save original function, reassign to our own handler
        const handleFileOriginal = app.handleFile;
        app.handleFile = async function (file) {
            if (app.ui.settings.getSettingValue("ImageSaver.HandleImageWorkflowDrop") && (file.type === "image/jpeg" || file.type === "image/webp")) {
                try {
                    const exifTags = await ExifReader.load(file);

                    const workflowString = "workflow:";
                    const promptString = "prompt:";
                    let workflow;
                    let prompt;
                    // Search Exif tag data for workflow and prompt
                    Object.values(exifTags).some(value => {
                        try {
                            const description = `${value.description}`;
                            if (workflow === undefined && description.slice(0, workflowString.length).toLowerCase() === workflowString) {
                                workflow = JSON.parse(description.slice(workflowString.length));
                            } else if (prompt === undefined && description.slice(0, promptString.length).toLowerCase() === promptString) {
                                prompt = JSON.parse(description.slice(promptString.length));
                            }
                        } catch (error) {
                            if (!(error instanceof SyntaxError)) {
                                console.error(`ComfyUI-Image-Saver: Error reading Exif value: ${error}`);
                            }
                        }

                        return workflow !== undefined;
                    });

                    if (workflow !== undefined) {
                        // Remove file extension
                        let filename = file.name;
                        let dot = filename.lastIndexOf('.');
                        if (dot !== -1) {
                            filename = filename.slice(0, dot);
                        }

                        app.loadGraphData(workflow, true, true, filename);
                        return;
                    } else if (prompt !== undefined) {
                        app.loadApiJson(prompt);
                        return;
                    }
                } catch (error) {
                    console.error(`ComfyUI-Image-Saver: Error parsing Exif: ${error}`);
                }
            }

            // Fallback to original function
            handleFileOriginal.call(this, file);
        }
    },
})