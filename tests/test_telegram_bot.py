import numpy as np
from PIL import Image

from src import telegram_bot
from src.shown import ShownPictures


class FakeCamera:
    def __init__(self, frame=None, active=True):
        self.frame, self.is_active = frame, active

    def get_latest_frame(self):
        return self.frame


class FakeMood:
    def average(self):
        return 0.42, 7

    def hourly(self):
        return [None] * 20 + [0.3, None, 0.6, 0.4]


def make_bot(monkeypatch, tmp_path, camera=None):
    calls, photos = [], []
    monkeypatch.setattr(telegram_bot, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram_bot, "_api", lambda method, **params: calls.append((method, params)) or [])
    monkeypatch.setattr(telegram_bot, "send_photo_now", lambda image, caption: photos.append((image, caption)))
    monkeypatch.setattr(telegram_bot, "send_document_now", lambda image, caption: photos.append((image, caption)))
    shown = ShownPictures(tmp_path)
    bot = telegram_bot.TelegramBot(camera or FakeCamera(), shown, FakeMood())
    return bot, shown, calls, photos


def message(text, chat=42):
    return {"chat": {"id": chat}, "text": text}


def test_ignores_other_chats(monkeypatch, tmp_path):
    bot, _, calls, photos = make_bot(monkeypatch, tmp_path, FakeCamera(np.zeros((4, 4, 3), np.uint8)))
    bot.handle(message("/snap", chat=99))
    assert calls == [] and photos == []


def test_snap_sends_the_camera_frame(monkeypatch, tmp_path):
    bot, _, _, photos = make_bot(monkeypatch, tmp_path, FakeCamera(np.zeros((4, 6, 3), np.uint8)))
    bot.handle(message("/snap"))
    assert photos[0][0].size == (6, 4)


def test_snap_without_camera_says_so(monkeypatch, tmp_path):
    bot, _, calls, photos = make_bot(monkeypatch, tmp_path, FakeCamera(None, active=False))
    bot.handle(message("/snap@HostileBot"))
    assert photos == [] and calls[0][1]["text"] == "Camera unavailable"


def test_review_sends_an_inline_photo_and_a_full_size_file(monkeypatch, tmp_path):
    bot, shown, _, photos = make_bot(monkeypatch, tmp_path)
    for h in (0.3, 0.8):
        shown.save(Image.new("RGB", (80, 48)), Image.new("RGB", (8, 8)), h, shown._clock())
    bot.handle(message("/review"))
    [(photo, caption), (document, _)] = photos
    assert caption == "Last 24h: 7 visits, mood 42%"
    assert photo.size == (1280, 768) and document.size == (2560, 1536)


def test_review_with_nothing_shown(monkeypatch, tmp_path):
    bot, _, calls, photos = make_bot(monkeypatch, tmp_path)
    bot.handle(message("/review"))
    assert photos == [] and calls[0][1]["text"] == "Nothing shown in the last 24h"


def test_anything_else_gets_the_command_list(monkeypatch, tmp_path):
    bot, _, calls, _ = make_bot(monkeypatch, tmp_path)
    bot.handle(message("hello"))
    assert "/snap" in calls[0][1]["text"] and "/review" in calls[0][1]["text"]


def test_backlog_from_before_startup_is_skipped(monkeypatch, tmp_path):
    bot, _, calls, _ = make_bot(monkeypatch, tmp_path)
    monkeypatch.setattr(
        telegram_bot, "_api",
        lambda method, **params: calls.append((method, params)) or ([{"update_id": 17}] if method == "getUpdates" else True),
    )
    bot._poll()
    assert [c[0] for c in calls] == ["setMyCommands", "getUpdates"]
    assert calls[1][1]["offset"] == -1 and bot._offset == 18
