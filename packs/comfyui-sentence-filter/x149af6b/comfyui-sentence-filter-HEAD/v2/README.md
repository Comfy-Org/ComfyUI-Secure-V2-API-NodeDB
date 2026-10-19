# ComfyUI – Sentence Filter

A custom ComfyUI node that receives a text prompt from the workflow,
removes or replaces sentences based on user-defined trigger words,
and passes the filtered text to the next node.

---

## Features

- **Works inline** in your ComfyUI workflow – text in, text out
- **Delete sentences** that contain a single word or all words from a comma-separated list
- **Replace sentences** that contain all words from a comma-separated list with a custom sentence
- URL dots (e.g. `www.example.com`) are ignored during sentence splitting
- Optional **case-sensitive** matching
- Compatible with **Python 3.13+**

---

## Installation

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/Slartibart23/comfyui-sentence-filter.git
```

Restart ComfyUI. The node appears under **text › processing** as **"Sentence Filter ✂️"**.

---

## Node Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `text` | STRING | ✅ | Input text prompt from the workflow |
| `delete_words` | STRING | ➖ | Comma-separated words – sentence is **deleted** if it contains **all** of them |
| `replace_words` | STRING | ➖ | Comma-separated words – sentence is **replaced** if it contains **all** of them |
| `replacement_sentence` | STRING | ➖ | The sentence that replaces matched sentences |
| `case_sensitive` | BOOLEAN | ➖ | Enable case-sensitive matching (default: off) |

## Node Outputs

| Output | Type | Description |
|---|---|---|
| `text` | STRING | Filtered text, ready for the next node |
| `sentences_deleted` | INT | Number of sentences deleted |
| `sentences_replaced` | INT | Number of sentences replaced |

---

## How It Works

### Delete – single word
`delete_words` = `Watermark`
→ Any sentence containing the word *Watermark* is removed.

```
Input:  "A beautiful photo. The watermark www.femjoy.com is in the corner. Enjoy."
Output: "A beautiful photo. Enjoy."
```

### Delete – multiple words (AND logic)
`delete_words` = `blonde, straight, young`
→ A sentence is only removed if it contains **all three** words.

```
Input:  "Nice day. A young woman with straight hair of blonde color. The end."
Output: "Nice day. The end."
```

### Replace
`replace_words` = `blonde, straight, young`
`replacement_sentence` = `A mature woman with brown curly hair`

```
Input:  "Intro. A young woman with straight blonde hair. Outro."
Output: "Intro. A mature woman with brown curly hair. Outro."
```

### Priority
If a sentence matches **both** `delete_words` and `replace_words`,
**deletion takes priority**.

---

## Running Tests

```bash
cd comfyui-sentence-filter
pip install pytest
python -m pytest tests/ -v
```

---

## Requirements

- Python **3.13+**
- ComfyUI (any recent version)
- No additional Python packages required

---

## License

MIT License – see [LICENSE](LICENSE) for details.
