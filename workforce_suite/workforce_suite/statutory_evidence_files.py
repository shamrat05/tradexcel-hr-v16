"""Readable private originals and immutable reviewed file fingerprints."""
import hashlib
import frappe


def checked_original(url, expected_hash='', image_only=False):
    files=frappe.get_list('File',filters={'file_url':url},fields=['name','is_private'],limit_page_length=2)
    if len(files)!=1 or not files[0].is_private:
        frappe.throw('Supporting originals must be readable, private Frappe Files.',frappe.PermissionError)
    file=frappe.get_doc('File',files[0].name);file.check_permission('read')
    content=file.get_content()
    if isinstance(content,str):content=content.encode()
    digest=hashlib.sha256(content).hexdigest()
    if expected_hash and digest!=expected_hash:
        frappe.throw('Reviewed original content has changed; obtain a new independently reviewed evidence version.')
    if image_only and not (content.startswith(b'\x89PNG\r\n\x1a\n') or content.startswith(b'\xff\xd8')):
        frappe.throw('Portrait evidence requires an original PNG or JPEG image.')
    if image_only:
        from io import BytesIO
        import warnings
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as portrait:
                    portrait.verify()
                with Image.open(BytesIO(content)) as portrait:
                    portrait.load()
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            frappe.throw('Portrait original must be a readable PNG or JPEG image within native image limits.')
    return content,digest,file.name
