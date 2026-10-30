"""Send the picture on the panel to a Telegram chat (optional)."""
import io
import logging
import threading
import urllib.request
import uuid

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _multipart(fields, png, field="photo"):
    """Encode form fields plus one PNG as multipart/form-data (the stdlib has no helper for this)."""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="hostile.png"\r\n'
        "Content-Type: image/png\r\n\r\n".encode() + png + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _upload(method, field, image, caption):
    buf = io.BytesIO()
    image.save(buf, "PNG")
    body, content_type = _multipart({"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, buf.getvalue(), field)
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=body, headers={"Content-Type": content_type},
    )
    try:
        urllib.request.urlopen(request, timeout=30).close()
        logger.info("Sent to Telegram")
    except Exception as e:  # a network hiccup must never stop the meter
        logger.warning("Telegram send failed: %s", e)


def send_photo_now(image, caption):
    """Send and wait; errors are logged, never raised. Telegram recompresses photos."""
    _upload("sendPhoto", "photo", image, caption)


def send_document_now(image, caption=""):
    """Like send_photo_now, but as a file, so Telegram leaves every pixel alone."""
    _upload("sendDocument", "document", image, caption)


def send_photo(image, caption):
    """Send in the background; does nothing unless TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    threading.Thread(target=send_photo_now, args=(image, caption), daemon=True).start()
