"""
WorkflowName - ComfyUI Custom Node
workflowのファイル名（拡張子なし）をSTRING出力するノード。
SaveImageのfilename_prefixに繋いで使う。

配置場所: ComfyUI/custom_nodes/comfyui-workflow-name/__init__.py
"""

import os
import re
from aiohttp import web
from server import PromptServer

# ファイル名として使えない文字（Windows基準で最も厳しいセットに合わせる）
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_FALLBACK_NAME = "NO_WORKFLOW_NAME"


def sanitize_filename(name: str) -> str:
    """ワークフロー名をファイル名として安全な文字列に変換する"""
    # パス区切りを除去
    name = os.path.basename(name)
    # 拡張子("".json")を除去
    name = name.removesuffix(".json")
    # 禁止文字をアンダースコアに置換
    name = _INVALID_CHARS.sub("_", name)
    # 先頭末尾のスペース・ドット・アンダースコアを除去（Windowsで問題になる）
    name = name.strip(" ._")
    # 空になった場合はフォールバック
    return name if name else _FALLBACK_NAME


class WorkflowNameNode:
    """
    現在開いているworkflowのファイル名（拡張子なし）を返すノード。
    フロントエンドのJSがworkflow読み込み時にファイル名をサーバーへ送信し、
    このノードがそれをSTRINGとして出力する。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # JSから更新される。取得できなかった場合はこの値がそのまま出力される
                "workflow_name": ("STRING", {"default": _FALLBACK_NAME}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("workflow_name",)
    FUNCTION = "get_name"
    CATEGORY = "utils"
    OUTPUT_NODE = False

    def get_name(self, workflow_name=_FALLBACK_NAME):
        print(f"[WorkflowName] get_name called with: {repr(workflow_name)}")
        name = workflow_name.strip() if workflow_name else _FALLBACK_NAME
        return (name,)


# --- APIエンドポイント: JSからworkflow名を受け取る ---
# サニタイズ済みの名前を返すだけ。状態管理はJS側（ノードのwidget.value）が担う

@PromptServer.instance.routes.post("/workflow_name/set")
async def set_workflow_name(request):
    try:
        data = await request.json()
        raw = data.get("name", "")
        name = sanitize_filename(raw) if raw else _FALLBACK_NAME
        return web.json_response({"status": "ok", "name": name})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)


# --- ノード登録 ---

NODE_CLASS_MAPPINGS = {
    "WorkflowName": WorkflowNameNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WorkflowName": "Workflow Name",
}

WEB_DIRECTORY = "./web"
