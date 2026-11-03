"""Unchanged pure functions extracted from the upstream host-dependent module."""
import re
import random

MAX_RESOLUTION = 16384

MAX_SEED = 0xffffffffffffffff

LINE_BREAK = "Line break"

SEPARATOR = ["Comma + Space", "Comma", "Line break", "Semicolon", "Space", "None"]

SEPARATOR_CHARS = {
    "Comma + Space": ", ",
    "Comma": ",",
    "Semicolon": ";",
    "Line break": "\n",
    "Space": " ",
    "None": "",
    # 旧表記エイリアス
    ",": ",",
    ";": ";",
    "newline": "\n",   # 旧 D2 Tag Report
    "comma": ", ",     # 旧 D2 Tag Report（旧実装は ", " で結合していた）
}

COMMENT_TYPES = ["# + // + /**/", "# only", "// only", "/* */ only", "None"]

COMMENT_TYPE_ALL = COMMENT_TYPES[0]

COMMENT_TYPE_NONE = "None"

def create_seed(num = 0):
    int_num = int(num)
    return random.randrange(MAX_SEED) if int_num == -1 else int_num

def get_separator_str(separator):
    return SEPARATOR_CHARS.get(separator, separator)

def list_to_text(list, separator):
    return get_separator_str(separator).join(list)

def delete_comment(text, type):
    """
    text のコメント行を消す
    type: "# only" なら行頭が「#」の行を消す
    type: "// only" なら行頭が「//」の行を消す
    type: "/* */ only" なら「/* 〜 */」を消す。これは複数行にも対応する
    type: "# + // + /**/" なら上記3つを全て実行する
    type: "None" ならなにもしない
    """
    result_text = text

    if type == "None": return text

    if type == "# only" or type == "# + // + /**/":
        # 行頭が # のコメント行を削除（行頭の空白は考慮しない）
        result_text = re.sub(r'^#.*$', '', result_text, flags=re.MULTILINE)
    
    if type == "// only" or type == "# + // + /**/":
        # 行頭が // のコメント行を削除（行頭の空白は考慮しない）
        result_text = re.sub(r'^//.*$', '', result_text, flags=re.MULTILINE)
    
    if type == "/* */ only" or type == "# + // + /**/":
        # /* */ コメントを削除（複数行対応）
        result_text = re.sub(r'/\*.*?\*/', '', result_text, flags=re.DOTALL)
    
    # # 空行が連続する場合、1つの空行にまとめる
    # result_text = re.sub(r'\n\s*\n+', '\n\n', result_text)
    
    # # 先頭と末尾の余分な改行を削除
    # result_text = result_text.strip()

    return result_text
