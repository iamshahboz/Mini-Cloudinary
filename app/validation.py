# Allowed formats: sniffed kind -> (content type, file extension)
ALLOWED_TYPES = {
    "jpeg": ("image/jpeg", "jpg"),
    "png": ("image/png", "png"),
    "webp": ("image/webp", "webp"),
}


def sniff_image_type(head: bytes) -> str | None:
    """Identify the image format from its first bytes (never trust the filename)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None