# -*- coding: utf-8 -*-
"""
本地自测脚本（不依赖 ComfyUI 环境），直接 python test_local.py 即可验证逻辑。
"""
from string_compare_node import StringCompareNumber


def run(name, **kwargs):
    node = StringCompareNumber()
    # 补齐默认参数
    defaults = dict(
        input_string="",
        delimiter="comma (,)",
        custom_delimiter="",
        operator="==",
        compare_value=0.0,
        strip_whitespace=True,
        ignore_empty=True,
    )
    defaults.update(kwargs)
    result, detail = node.compare(**defaults)
    print(f"\n===== {name} =====")
    print(f"输入: {defaults['input_string']!r}  操作: X {defaults['operator']} {defaults['compare_value']}")
    print(f"result = {result}")
    print(detail)
    return result


if __name__ == "__main__":
    assert run("全部 >0", input_string="1,2,3", operator=">", compare_value=0) == 1
    assert run("存在 -3", input_string="1,2,-3", operator=">", compare_value=0) == 0
    assert run("包含非数字", input_string="1,abc,3", operator=">", compare_value=0) == 0
    assert run("整体比较", input_string="12.5", delimiter="none (whole string)", operator="<=", compare_value=13) == 1
    assert run("空字符串", input_string="", operator="==", compare_value=0) == 0
    assert run("自定义分隔符", input_string="1|2|3", delimiter="custom", custom_delimiter="|", operator="==", compare_value=1) == 0
    assert run("等于测试", input_string="5,5,5", operator="==", compare_value=5) == 1
    assert run("不等于测试", input_string="1,2,3", operator="!=", compare_value=0) == 1
    assert run("空格分隔", input_string="10 20 30", delimiter="space ( )", operator=">=", compare_value=10) == 1

    # 换行相关测试
    assert run(
        "\\n 换行", input_string="1\n2\n3",
        delimiter="newline (\\n / \\r\\n / \\r)", operator=">", compare_value=0,
    ) == 1
    assert run(
        "\\r\\n 换行", input_string="1\r\n2\r\n3",
        delimiter="newline (\\n / \\r\\n / \\r)", operator=">", compare_value=0,
    ) == 1
    assert run(
        "\\r 换行", input_string="1\r2\r3",
        delimiter="newline (\\n / \\r\\n / \\r)", operator=">", compare_value=0,
    ) == 1
    assert run(
        "混合换行", input_string="1\r\n2\n3\r4",
        delimiter="newline (\\n / \\r\\n / \\r)", operator=">=", compare_value=1,
    ) == 1
    assert run(
        "任意空白", input_string="1 2\t3\n4",
        delimiter="any whitespace (空白字符)", operator=">", compare_value=0,
    ) == 1
    assert run(
        "自定义填 \\n", input_string="1\n2\n3",
        delimiter="custom", custom_delimiter="\\n",
        operator=">", compare_value=0,
    ) == 1

    print("\n所有测试通过")
