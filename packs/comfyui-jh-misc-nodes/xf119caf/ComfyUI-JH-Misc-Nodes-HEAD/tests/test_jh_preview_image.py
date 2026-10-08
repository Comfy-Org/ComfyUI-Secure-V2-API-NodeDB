from unittest.mock import MagicMock, patch

import pytest
import torch

from comfyui_jh_misc_nodes.jh_preview_image import JHPreviewImage


@pytest.fixture
def node() -> JHPreviewImage:
    return JHPreviewImage()


@patch("comfyui_jh_misc_nodes.jh_preview_image.folder_paths.get_save_image_path")
@patch("PIL.Image.Image.save")
def test_preview_images(
    mock_save: MagicMock, mock_get_save_image_path: MagicMock, node: JHPreviewImage
) -> None:
    # Mock the get_save_image_path function to return a fake path structure
    mock_get_save_image_path.return_value = (
        "/fake/output/folder",
        "test_image_%batch_num%",
        1,
        "subfolder_name",
        "ComfyUI_temp_xyz123",
    )

    # Create a fake image tensor (batch of 2 images, 3 channels, 64x64 resolution)
    images = torch.rand(2, 64, 64, 3)

    # Mock inputs for prompt and extra_pnginfo
    prompt = {"text": "This is a test prompt"}
    extra_pnginfo = {"metadata_key": "metadata_value"}

    # Call the method
    result = node.preview_images(
        images, filename_prefix="TestPrefix", prompt=prompt, extra_pnginfo=extra_pnginfo
    )

    # Assertions
    assert mock_get_save_image_path.called, "get_save_image_path was not called"
    assert mock_save.call_count == 2, "save was not called for all images in the batch"
    assert (
        len(result["ui"]["images"]) == 2
    ), "Result does not contain the expected number of images"

    # Verify the returned filenames and structure
    for _, image_data in enumerate(result["ui"]["images"]):
        assert image_data["filename"].startswith("test_image_")
        assert image_data["subfolder"] == "subfolder_name"
        assert image_data["type"] == "temp"

    # Ensure the result tensor matches the input tensor
    assert (
        result["result"][0] is images
    ), "Returned tensor does not match the input tensor"
