from PIL import Image

from src import notify


def test_sends_png_with_caption_to_the_chat(monkeypatch):
    sent = {}

    class Response:
        def close(self):
            pass

    def fake_urlopen(request, timeout):
        sent["url"], sent["body"] = request.full_url, request.data
        return Response()

    monkeypatch.setattr(notify, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(notify, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    notify._send(Image.new("RGB", (8, 8), "white"), "Hostility 70%")

    assert sent["url"] == "https://api.telegram.org/bot123:abc/sendPhoto"
    assert b'name="chat_id"\r\n\r\n42\r\n' in sent["body"]
    assert b"Hostility 70%" in sent["body"]
    assert b"\x89PNG" in sent["body"]


def test_network_error_is_swallowed(monkeypatch):
    def failing_urlopen(request, timeout):
        raise OSError("no network")

    monkeypatch.setattr(notify.urllib.request, "urlopen", failing_urlopen)
    notify._send(Image.new("RGB", (8, 8)), "x")  # must not raise


def test_does_nothing_without_credentials(monkeypatch):
    monkeypatch.setattr(notify, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(notify.threading, "Thread", lambda **_: (_ for _ in ()).throw(AssertionError("sent")))
    notify.send_photo(Image.new("RGB", (8, 8)), "x")
