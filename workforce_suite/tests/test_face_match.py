import numpy as np
import pytest

from workforce_suite.workforce_suite.face_match import (
	FaceMatchUnavailable,
	_prepare_image,
	validate_configuration,
)


def test_face_match_normalizes_camera_images_to_detector_frame():
    image = np.zeros((1920, 1080, 3), dtype=np.uint8)

    prepared = _prepare_image(image)

    assert prepared.shape == (320, 320, 3)


def test_enabled_face_match_requires_both_model_files(tmp_path):
    (tmp_path / "detector.onnx").write_bytes(b"model")
    with pytest.raises(FaceMatchUnavailable, match="SFace recognizer model file is missing"):
        validate_configuration(
            enabled=True,
            provider="OpenCV YuNet + SFace",
            detector_model_path="detector.onnx",
            recognizer_model_path="recognizer.onnx",
            site_root=tmp_path,
        )


def test_disabled_face_match_does_not_require_optional_runtime(tmp_path):
    validate_configuration(
        enabled=False,
        provider="OpenCV YuNet + SFace",
        detector_model_path="",
        recognizer_model_path="",
        site_root=tmp_path,
    )
