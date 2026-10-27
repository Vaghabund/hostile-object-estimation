import logging

logger = logging.getLogger(__name__)


class InkyDisplay:
    """Pimoroni Inky (Impression / wHAT / pHAT), auto-detected over the HAT EEPROM."""

    mono = False  # colour panels do their own palette conversion

    def __init__(self):
        from inky.auto import auto

        self._inky = auto(ask_user=False, verbose=False)
        self.size = tuple(self._inky.resolution)

    def show(self, image):
        self._inky.set_image(image)
        self._inky.show()
        logger.info("Inky refreshed")

    def close(self):
        pass
