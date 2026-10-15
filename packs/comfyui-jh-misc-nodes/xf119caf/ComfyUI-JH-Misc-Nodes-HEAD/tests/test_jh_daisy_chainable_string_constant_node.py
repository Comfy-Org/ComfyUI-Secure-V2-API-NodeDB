import pytest

from comfyui_jh_misc_nodes.jh_daisy_chainable_string_constant_node import (
    JHDaisyChainableStringConstantNode,
)


@pytest.fixture
def node() -> JHDaisyChainableStringConstantNode:
    return JHDaisyChainableStringConstantNode()


def test_input_types(node: JHDaisyChainableStringConstantNode) -> None:
    input_types = node.INPUT_TYPES()

    assert "required" in input_types
    assert "optional" in input_types
    assert "hidden" not in input_types

    assert "text" in input_types["optional"]
    assert "input_text" in input_types["optional"]


def test_execute_with_only_text(node: JHDaisyChainableStringConstantNode) -> None:
    result = node.execute("Hello\nWorld")
    assert result == ("Hello World",)


def test_execute_with_text_and_input_text(
    node: JHDaisyChainableStringConstantNode,
) -> None:
    result = node.execute("Hello\nWorld", "Input")
    assert result == ("Input Hello World",)


def test_execute_with_empty_text(node: JHDaisyChainableStringConstantNode) -> None:
    result = node.execute("")
    assert result == ("",)


def test_execute_with_empty_text_and_input_text(
    node: JHDaisyChainableStringConstantNode,
) -> None:
    result = node.execute("", "Input")
    assert result == ("Input",)


def test_execute_with_multiple_newlines(
    node: JHDaisyChainableStringConstantNode,
) -> None:
    result = node.execute("Hello\n\n\nWorld")
    assert result == ("Hello World",)
