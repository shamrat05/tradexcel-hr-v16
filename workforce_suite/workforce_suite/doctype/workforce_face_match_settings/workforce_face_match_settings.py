import frappe
from frappe.model.document import Document

from workforce_suite.workforce_suite.face_match import FaceMatchUnavailable, validate_configuration


class WorkforceFaceMatchSettings(Document):
	def validate(self):
		if not self.enabled:
			return
		if self.provider != "OpenCV YuNet + SFace":
			frappe.throw("Only the configured OpenCV YuNet + SFace provider is supported")
		if not self.detector_model_path or not self.recognizer_model_path:
			frappe.throw("Both face model paths are required when face matching is enabled")
		if not 0 < float(self.cosine_threshold or 0) < 1:
			frappe.throw("Cosine match threshold must be between 0 and 1")
		if not 0 < float(self.minimum_face_confidence or 0) <= 1:
			frappe.throw("Minimum face confidence must be between 0 and 1")
		try:
			validate_configuration(
				enabled=bool(self.enabled),
				provider=self.provider,
				detector_model_path=self.detector_model_path,
				recognizer_model_path=self.recognizer_model_path,
				site_root=frappe.get_site_path(),
			)
		except FaceMatchUnavailable as exc:
			frappe.throw(str(exc))
