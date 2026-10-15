import pytest

from comfyui_jh_misc_nodes.jh_n_way_switch_node import JHTwoWaySwitchNode


@pytest.fixture
def node() -> JHTwoWaySwitchNode:
    return JHTwoWaySwitchNode()


def test_two_way_switch_node_none_none(node: JHTwoWaySwitchNode) -> None:
    assert node.do_switch(input_1=None, input_2=None) == (None,)


def test_two_way_switch_node_none_value(node: JHTwoWaySwitchNode) -> None:
    assert node.do_switch(input_1=None, input_2="value") == ("value",)


def test_two_way_switch_node_value_none(node: JHTwoWaySwitchNode) -> None:
    assert node.do_switch(input_1="value", input_2=None) == ("value",)
