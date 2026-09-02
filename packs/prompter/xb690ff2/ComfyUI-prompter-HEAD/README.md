# comfyui-prompter

# 🎨 ComfyUI Prompt Saver & Loader

A custom ComfyUI node to save, manage, and load prompts with a searchable dropdown, smart auto-save, and multi-file storage.

![Image alt](https://github.com/sinfisum/comfyui-prompter/raw/main/assets/1.png)

## ✨ Features

- **🔍 Searchable Dropdown**: Quickly find and load saved prompts (supports search like model loaders).
- **💾 Smart Auto-Save**: Automatically saves 60 seconds after you stop typing. If the title exists, it appends `_auto_1`, `_auto_2`, etc.
- **📂 Multi-File Storage**: Prompts are saved as individual `.txt` files, while an `index.json` stores only the titles. 
- **🛡️ No Escaping Issues**: Because prompts are stored as raw text files, you can safely save complex JSON, YAML, or Markdown inside your prompts without corruption.
- **⚡ On-Demand Loading**: Only titles are loaded into the dropdown. The actual prompt text is fetched only when you select it, keeping ComfyUI fast.
- **🔀 Multi-Node Support**: Use multiple instances of this node simultaneously; their states and timers are fully isolated.

## 📦 Installation

Navigate to your `custom_nodes` directory and clone the repository:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/infisum/comfyui-prompter.git
```
*Restart ComfyUI and refresh your browser (Ctrl+F5).*

## 🚀 Usage

1. Add the node: Right-click → `Add Node` → `utils` → **Prompt Saver & Loader**.
2. **To Save**: Enter a title (or use the auto-generated date/workflow name), type your prompt, and click **💾 Save Prompt** (or wait for auto-save).
3. **To Load**: Type in the `selected_title` dropdown to search, then select a prompt. The text will load instantly.
4. **Auto-Save Toggle**: Use the `auto_save` boolean switch to enable/disable the 60-second auto-save timer.

## 📁 Storage Structure

```text
custom_nodes/comfyui-prompt-saver/
├── __init__.py          # Backend logic & API
├── index.json           # Lightweight index of prompt titles
├── web/
│   └── prompt_saver.js  # Frontend UI logic
└── prompts/             # Your actual prompts (1 file = 1 prompt)
    ├── 2024-05-20_portrait.txt
    ├── my_complex_json.txt
    └── ...
```

*Note: You can open, edit, or backup the `.txt` files in the `prompts/` folder using any standard text editor.*

## 📄 License

MIT License. Feel free to use and modify.