"""Secure Nodes V2 entry point for Prompt Stash."""

from .nodes import PromptStashManager, PromptStashPassthrough, PromptStashSaver


NODE_CLASS_MAPPINGS = {
    "PromptStashPassthrough": PromptStashPassthrough,
    "PromptStashSaver": PromptStashSaver,
    "PromptStashManager": PromptStashManager,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptStashPassthrough": "Prompt Stash Passthrough",
    "PromptStashSaver": "Prompt Stash Saver",
    "PromptStashManager": "Prompt Stash Manager",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
