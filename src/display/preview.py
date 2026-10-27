import logging

from config.settings import PREVIEW_PATH

logger = logging.getLogger(__name__)


class PreviewDisplay:
    """Writes the frame to a PNG instead of a panel: for development without hardware."""

    size = None   # use the configured DISPLAY_SIZE
    mono = True   # show what a black/white panel would look like

    def show(self, image):
        PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        image.save(PREVIEW_PATH)
        logger.info("Preview written to %s", PREVIEW_PATH)

    def close(self):
        pass
