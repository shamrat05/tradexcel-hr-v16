"""Optional local face matching adapter.

The provider is deliberately lazy-loaded. A site cannot enable face matching
until OpenCV and both pinned ONNX models are installed and configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FaceMatchUnavailable(RuntimeError):
	pass


def _load_image(path: str):
	try:
		import cv2
	except ImportError as exc:
		raise FaceMatchUnavailable("opencv-contrib-python-headless is not installed") from exc
	image = cv2.imread(path)
	if image is None:
		raise FaceMatchUnavailable("Face image could not be decoded")
	return cv2, _prepare_image(image)


def _prepare_image(image):
	"""Normalize camera uploads before YuNet sees high-resolution backgrounds."""
	import cv2

	return cv2.resize(image, (320, 320), interpolation=cv2.INTER_AREA)


def match_images(
	reference_path: str,
	query_path: str,
	detector_model_path: str,
	recognizer_model_path: str,
	*,
	cosine_threshold: float = 0.363,
	minimum_face_confidence: float = 0.90,
) -> dict[str, Any]:
	"""Compare one reference face with one query face using local OpenCV DNN.

	A result is evidence, not an authentication guarantee. Multiple faces,
	missing faces, low detector confidence, and low similarity fail closed.
	"""
	if not 0 < float(cosine_threshold) < 1:
		raise ValueError("Cosine threshold must be between 0 and 1")
	if not 0 < float(minimum_face_confidence) <= 1:
		raise ValueError("Minimum face confidence must be between 0 and 1")
	cv2, reference = _load_image(reference_path)
	_, query = _load_image(query_path)
	try:
		detector = cv2.FaceDetectorYN.create(
			detector_model_path, "", (320, 320), float(minimum_face_confidence), 0.3, 5000
		)
		recognizer = cv2.FaceRecognizerSF.create(recognizer_model_path, "")
	except Exception as exc:
		raise FaceMatchUnavailable(f"Face models could not be loaded: {exc}") from exc

	def detect(image):
		detector.setInputSize((image.shape[1], image.shape[0]))
		_, faces = detector.detect(image)
		if faces is None:
			return []
		return [face for face in faces if float(face[-1]) >= minimum_face_confidence]

	reference_faces = detect(reference)
	query_faces = detect(query)
	if len(reference_faces) != 1:
		raise FaceMatchUnavailable("Reference image must contain exactly one clear face")
	if len(query_faces) != 1:
		raise FaceMatchUnavailable("Selfie must contain exactly one clear face")
	try:
		reference_aligned = recognizer.alignCrop(reference, reference_faces[0][:-1])
		query_aligned = recognizer.alignCrop(query, query_faces[0][:-1])
		reference_feature = recognizer.feature(reference_aligned)
		query_feature = recognizer.feature(query_aligned)
		score = float(recognizer.match(reference_feature, query_feature, cv2.FaceRecognizerSF_FR_COSINE))
	except Exception as exc:
		raise FaceMatchUnavailable(f"Face feature extraction failed: {exc}") from exc
	return {
		"status": "Matched" if score >= cosine_threshold else "Mismatch",
		"score": round(score, 6),
		"threshold": float(cosine_threshold),
		"provider": "OpenCV YuNet + SFace",
	}
