"""Lightweight content types for retained image bytes; no decoder dependency."""

IMAGE_HEADER_BYTES = 4096


def avif_header(header):
    """Recognize brands inside the leading ISO BMFF file-type box only.

    This chooses a MIME type/extension and does not certify image decoding.
    https://aomediacodec.github.io/av1-avif/#brands
    """
    if len(header) < 16 or header[4:8] != b'ftyp':
        return False
    size = int.from_bytes(header[:4], 'big')
    major, compatible = 8, 16
    if size == 1:
        if len(header) < 24:
            return False
        size = int.from_bytes(header[8:16], 'big')
        major, compatible = 16, 24
    if size < compatible or (size - compatible) % 4:
        return False
    brands = [header[major:major + 4]]
    brands.extend(header[offset:offset + 4]
                  for offset in range(compatible, min(size, len(header)) - 3, 4))
    return any(brand in (b'avif', b'avis') for brand in brands)


def image_type_from_header(header):
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', '.jpg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png', '.png'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif', '.gif'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'image/webp', '.webp'
    if header.startswith((b'II*\x00', b'MM\x00*')):
        return 'image/tiff', '.tiff'
    if header.startswith(b'BM'):
        return 'image/bmp', '.bmp'
    if avif_header(header):
        return 'image/avif', '.avif'
    return 'application/octet-stream', '.bin'
