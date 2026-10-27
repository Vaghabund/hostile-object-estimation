import importlib
import logging

from config.settings import WAVESHARE_MODEL

logger = logging.getLogger(__name__)


class WaveshareDisplay:
    """Black/white Waveshare panel, chosen with WAVESHARE_MODEL (e.g. epd7in5_V2)."""

    mono = True

    def __init__(self):
        module = importlib.import_module(f"waveshare_epd.{WAVESHARE_MODEL}")
        self._epd = module.EPD()
        self.size = (self._epd.width, self._epd.height)

    def show(self, image):
        self._epd.init()
        self._epd.display(self._epd.getbuffer(image.convert("1")))
        # Sleep between updates: the panel holds the image with no power at all.
        self._epd.sleep()
        logger.info("Waveshare refreshed")

    def close(self):
        pass
