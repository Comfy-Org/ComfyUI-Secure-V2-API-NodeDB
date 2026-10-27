# -*- coding: utf-8 -*-
"""
String Compare Node for ComfyUI
功能：将输入字符串按指定分隔符切分，然后将每一段与指定数字按照指定比较方式进行比较。
只要有一个分段不满足条件（或无法转换为数字），就返回 0；所有分段都满足条件才返回 1。
"""

import re


class StringCompareNumber:
    """
    字符串与数字比较节点
    - input_string: 需要比较的字符串
    - delimiter: 字符串分割方式（支持常见分隔符，选择 custom 时使用 custom_delimiter）
    - custom_delimiter: 自定义分隔符（仅在 delimiter 选择 custom 时生效）
    - compare_value: 用于比较的数字
    - operator: 比较方式（==, !=, >, >=, <, <=）
    - strip_whitespace: 是否去除每段首尾空白
    - ignore_empty: 是否忽略空字符串分段
    输出：
    - result (INT): 比较结果 0 或 1
    - detail (STRING): 详细的比较过程（便于调试）
    """

    # 预设分隔符映射
    # 值为 str -> 普通字符串分割
    # 值为 ("regex", pattern) -> 使用正则分割（用于换行等多形式场景）
    # 值为 None -> 不分割（整体比较）
    # 值为 "__CUSTOM__" -> 启用 custom_delimiter
    DELIMITER_MAP = {
        "comma (,)": ",",
        "semicolon (;)": ";",
        "space ( )": " ",
        "tab (\\t)": "\t",
        "newline (\\n / \\r\\n / \\r)": ("regex", r"\r\n|\r|\n"),
        "any whitespace (空白字符)": ("regex", r"\s+"),
        "pipe (|)": "|",
        "slash (/)": "/",
        "colon (:)": ":",
        "dash (-)": "-",
        "underscore (_)": "_",
        "dot (.)": ".",
        "none (whole string)": None,  # 不分割，整体比较
        "custom": "__CUSTOM__",
    }

    OPERATORS = ["==", "!=", ">", ">=", "<", "<="]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_string": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "需要进行比较的字符串",
                }),
                "delimiter": (list(cls.DELIMITER_MAP.keys()), {
                    "default": "comma (,)",
                    "tooltip": "字符串分割方式",
                }),
                "custom_delimiter": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "自定义分隔符（仅当 delimiter 选择 custom 时生效）",
                }),
                "operator": (cls.OPERATORS, {
                    "default": "==",
                    "tooltip": "比较方式",
                }),
                "compare_value": ("FLOAT", {
                    "default": 0.0,
                    "min": -1e18,
                    "max": 1e18,
                    "step": 0.0001,
                    "tooltip": "用于比较的数字",
                }),
                "strip_whitespace": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "是否去除每段首尾空白字符",
                }),
                "ignore_empty": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "是否忽略空字符串分段（不参与比较）",
                }),
            },
        }

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("result", "detail")
    FUNCTION = "compare"
    CATEGORY = "utils/string"
    OUTPUT_NODE = False

    # ---------- 内部工具 ----------
    @staticmethod
    def _to_number(text):
        """尝试将字符串转成数字，失败返回 None。支持整数与浮点数。"""
        if text is None:
            return None
        s = str(text).strip()
        if s == "":
            return None
        try:
            # 优先尝试 int（保证 "10" 不变成 10.0 时比较的一致性）
            return int(s)
        except (ValueError, TypeError):
            pass
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _do_compare(a, op, b):
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        return False

    # ---------- 主逻辑 ----------
    def compare(self, input_string, delimiter, custom_delimiter, operator,
                compare_value, strip_whitespace, ignore_empty):
        details = []

        # 处理 compare_value：如果是整数值的 float，以 int 展示（不影响比较结果）
        cmp_val = compare_value
        if isinstance(cmp_val, float) and cmp_val.is_integer():
            cmp_val_display = int(cmp_val)
        else:
            cmp_val_display = cmp_val

        # 空字符串判断
        if input_string is None or str(input_string) == "":
            detail = "输入字符串为空 -> 返回 0"
            return (0, detail)

        # 解析分隔符
        sep_raw = self.DELIMITER_MAP.get(delimiter, ",")
        sep_mode = "plain"  # plain / regex / none
        sep = None
        sep_display = ""

        if sep_raw == "__CUSTOM__":
            user_sep = custom_delimiter
            if user_sep is None or user_sep == "":
                detail = "选择了 custom 分隔符但未填写 custom_delimiter -> 返回 0"
                return (0, detail)
            # 允许用户在 custom_delimiter 中填写转义字符：\n \r \t \\
            user_sep = (
                user_sep.replace("\\\\", "\x00")
                        .replace("\\n", "\n")
                        .replace("\\r", "\r")
                        .replace("\\t", "\t")
                        .replace("\x00", "\\")
            )
            sep_mode = "plain"
            sep = user_sep
            sep_display = repr(sep)
        elif sep_raw is None:
            sep_mode = "none"
            sep_display = "无（整体比较）"
        elif isinstance(sep_raw, tuple) and sep_raw[0] == "regex":
            sep_mode = "regex"
            sep = sep_raw[1]
            sep_display = f"regex({sep})"
        else:
            sep_mode = "plain"
            sep = sep_raw
            sep_display = repr(sep)

        # 切分字符串
        text = str(input_string)
        if sep_mode == "none":
            parts = [text]
        elif sep_mode == "regex":
            parts = re.split(sep, text)
        else:
            parts = text.split(sep)

        # 预处理
        processed = []
        for p in parts:
            if strip_whitespace:
                p = p.strip()
            if ignore_empty and p == "":
                continue
            processed.append(p)

        if len(processed) == 0:
            detail = "分割后没有有效分段 -> 返回 0"
            return (0, detail)

        # 逐段比较
        all_pass = True
        for idx, seg in enumerate(processed):
            num = self._to_number(seg)
            if num is None:
                details.append(
                    f"[{idx}] '{seg}' 无法转换为数字 -> FAIL"
                )
                all_pass = False
                continue

            # 为了展示整洁，如果是整数就按 int 显示
            num_display = int(num) if isinstance(num, float) and num.is_integer() else num
            ok = self._do_compare(num, operator, compare_value)
            details.append(
                f"[{idx}] {num_display} {operator} {cmp_val_display} -> {'PASS' if ok else 'FAIL'}"
            )
            if not ok:
                all_pass = False

        result = 1 if all_pass else 0
        detail_text = (
            f"分隔符: {sep_display} | "
            f"比较: X {operator} {cmp_val_display} | 段数: {len(processed)}\n"
            + "\n".join(details)
            + f"\n最终结果: {result}"
        )
        return (result, detail_text)


# ---- ComfyUI 节点注册 ----
NODE_CLASS_MAPPINGS = {
    "StringCompareNumber": StringCompareNumber,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StringCompareNumber": "String Compare Number (字符串数字比较)",
}
