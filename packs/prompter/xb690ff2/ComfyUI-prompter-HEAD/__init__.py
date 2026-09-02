import os
import json
import re
from server import PromptServer
from aiohttp import web

NODE_DIR = os.path.dirname(__file__)
PROMPTS_DIR = os.path.join(NODE_DIR, "prompts")
INDEX_PATH = os.path.join(NODE_DIR, "index.json")

os.makedirs(PROMPTS_DIR, exist_ok=True)

def load_index():
    if not os.path.exists(INDEX_PATH): return {}
    try:
        with open(INDEX_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print(f"[PromptSaver] Error loading index: {e}")
        return {}

def save_index(data):
    try:
        with open(INDEX_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"[PromptSaver] Error saving index: {e}")

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_safe_filename_by_title(title, index_data):
    for safe_name, orig_title in index_data.items():
        if orig_title == title: return safe_name
    return None

class PromptSaverNode:
    @classmethod
    def INPUT_TYPES(cls):
        index_data = load_index()
        titles = ["[New Prompt]"] + list(index_data.values())
        return {
            "required": {
                "selected_title": (titles, {"default": "[New Prompt]", "comboSearch": True}),
                "auto_save": ("BOOLEAN", {"default": True}),
                "title_name": ("STRING", {"default": ""}),
                "prompt_text": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "execute"
    CATEGORY = "utils"

    def execute(self, selected_title, auto_save, title_name, prompt_text):
        return (prompt_text,)

@PromptServer.instance.routes.get("/prompt_saver/get_titles")
async def get_titles(request):
    index_data = load_index()
    return web.json_response(["[New Prompt]"] + list(index_data.values()))

@PromptServer.instance.routes.get("/prompt_saver/get_content")
async def get_content(request):
    title = request.query.get("title", "")
    if not title: return web.Response(text="", content_type='text/plain')
    index_data = load_index()
    safe_name = get_safe_filename_by_title(title, index_data)
    if not safe_name: return web.Response(text="", content_type='text/plain')
    file_path = os.path.join(PROMPTS_DIR, f"{safe_name}.txt")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: return web.Response(text=f.read(), content_type='text/plain')
        except Exception as e: print(f"[PromptSaver] Error reading file: {e}")
    return web.Response(text="", content_type='text/plain')

@PromptServer.instance.routes.post("/prompt_saver/save")
async def save_prompt(request):
    try:
        data = await request.json()
        title, text = data.get("title"), data.get("text")
        if not title or title == "[New Prompt]":
            return web.json_response({"error": "Invalid title"}, status=400)

        index_data = load_index()
        safe_name = get_safe_filename_by_title(title, index_data)
        if not safe_name:
            safe_name = sanitize_filename(title)
            base_safe_name = safe_name
            counter = 1
            while safe_name in index_data:
                safe_name = f"{base_safe_name}_{counter}"
                counter += 1
                
        file_path = os.path.join(PROMPTS_DIR, f"{safe_name}.txt")
        with open(file_path, 'w', encoding='utf-8') as f: f.write(text)
        index_data[safe_name] = title
        save_index(index_data)
        print(f"[PromptSaver] Saved: '{safe_name}.txt'")
        return web.json_response({"status": "success", "title": title})
    except Exception as e:
        print(f"[PromptSaver] Save error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@PromptServer.instance.routes.get("/prompt_saver/check_title")
async def check_title(request):
    base_title = request.query.get("title", "")
    if not base_title: return web.json_response({"error": "Title is required"}, status=400)
    index_data = load_index()
    existing_titles = set(index_data.values())
    if base_title not in existing_titles:
        return web.json_response({"available_title": base_title})
    index = 1
    while True:
        new_title = f"{base_title}_auto_{index}"
        if new_title not in existing_titles:
            return web.json_response({"available_title": new_title})
        index += 1

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {"PromptSaverNode": PromptSaverNode}
NODE_DISPLAY_NAME_MAPPINGS = {"PromptSaverNode": "Prompt Saver & Loader"}