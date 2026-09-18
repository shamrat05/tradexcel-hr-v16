import frappe
from frappe.model.document import Document


class TradexFaceMatchSettings(Document):
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
