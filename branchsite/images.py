"""Make uploaded photos smaller before saving (phones send 5-10 MB photos; the page should stay fast)."""
import io
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

MAX_UPLOAD_MB = 8


def check_size(upload):
    if upload and upload.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"Photo is too large. Please use a photo under {MAX_UPLOAD_MB} MB.")
    return upload


def shrink(upload, max_px=1600):
    """Return a smaller copy of an uploaded image (keeps PNG for transparent logos, else JPEG)."""
    from PIL import Image, ImageOps

    upload.seek(0)
    img = Image.open(upload)
    img = ImageOps.exif_transpose(img)  # phone photos: keep them the right way up
    img.thumbnail((max_px, max_px))
    name = os.path.splitext(os.path.basename(upload.name))[0][:40] or "photo"
    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P") and upload.name.lower().endswith(".png"):
        img.save(buf, format="PNG", optimize=True)
        ext = "png"
    else:
        img.convert("RGB").save(buf, format="JPEG", quality=82, optimize=True)
        ext = "jpg"
    return ContentFile(buf.getvalue(), name=f"{name}.{ext}")
