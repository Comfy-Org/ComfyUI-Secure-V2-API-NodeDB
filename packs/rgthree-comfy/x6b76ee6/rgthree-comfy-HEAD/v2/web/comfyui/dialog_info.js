import { comfy } from '/comfy/api/v2.js';

// PUNTED IN FULL — 292 lines removed, nothing converted.
//
// The model info modal: a lora's or checkpoint's file, sha256, Civitai link,
// click-to-select trained words, clip skip, recommended strength range, user notes
// and preview media, with a few inline-editable fields saved back to rgthree's own
// server.
//
// This file is almost entirely plain DOM and touches no graph or canvas API. It is
// punted for two reasons, and the second is the decisive one:
//
//  1. Its two remaining couplings are to the punted rgthree.js singleton —
//     `rgthree.showMessage({...})` for the "copied N keywords" toast, which maps to
//     `comfy.commands.notify({severity, summary})`, and `rgthree.isDevMode()`,
//     which gates a dev-only actions menu and reads a log level that no longer
//     exists.
//  2. Its only importer is power_lora_loader.js, which is punted. Converting it
//     would produce a module nothing loads.
//
// Nothing else here needs the API. If Power Lora Loader is ever ported, this file
// converts in two lines.
