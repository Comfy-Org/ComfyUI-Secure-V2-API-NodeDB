#!/usr/bin/env python

"""Tests for `immac_tools` package."""

import pytest
from src.immac_tools.nodes import ConcatenateSigmasNode

@pytest.fixture
def example_node():
    """Fixture to create an Example node instance."""
    return ConcatenateSigmasNode()

def test_example_node_initialization(example_node):
    """Test that the node can be instantiated."""
    assert isinstance(example_node, ConcatenateSigmasNode)

def test_return_types():
    """Test the node's metadata."""
    assert ConcatenateSigmasNode.RETURN_TYPES == ("IMAGE",)
    assert ConcatenateSigmasNode.FUNCTION == "test"
    assert ConcatenateSigmasNode.CATEGORY == "Example"
