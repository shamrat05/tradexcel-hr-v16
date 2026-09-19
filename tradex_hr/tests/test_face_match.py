import numpy as np

from tradex_hr.tradexcel_hr.face_match import _prepare_image


def test_face_match_normalizes_camera_images_to_detector_frame():
    image = np.zeros((1920, 1080, 3), dtype=np.uint8)

    prepared = _prepare_image(image)

    assert prepared.shape == (320, 320, 3)
