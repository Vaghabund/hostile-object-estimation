from config.settings import DISPLAY_BACKEND


def get_display(name=DISPLAY_BACKEND):
    """Build the configured display backend. Hardware libs are imported lazily."""
    if name == "preview":
        from src.display.preview import PreviewDisplay
        return PreviewDisplay()
    if name == "inky":
        from src.display.inky import InkyDisplay
        return InkyDisplay()
    if name == "waveshare":
        from src.display.waveshare import WaveshareDisplay
        return WaveshareDisplay()
    raise ValueError(f"Unknown DISPLAY_BACKEND {name!r} (use preview, inky or waveshare)")
