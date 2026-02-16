import logging
import asyncio
import io
import cv2
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from config.settings import (
    TELEGRAM_BOT_TOKEN, 
    AUTHORIZED_USER_ID,
    TELEGRAM_IMAGE_QUALITY
)
from src.shared_state import SharedState
from src.stats import StatsGenerator

logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Telegram bot for remote control and monitoring.
    Runs in its own thread/loop.
    """
    def __init__(self, shared_state: SharedState):
        self.state = shared_state
        self.stats = StatsGenerator(shared_state)
        
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token is missing! Bot will not start.")
            self.app = None
            return

        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()
        logger.info("Telegram Bot initialized.")

    def _register_handlers(self):
        """Register command handlers."""
        if self.app is None:
            return
            
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("scan", self.cmd_scan))
        self.app.add_handler(CommandHandler("snapshot", self.cmd_scan)) # Alias
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("summary", self.cmd_summary))
        self.app.add_handler(CommandHandler("reset", self.cmd_reset))
        self.app.add_handler(CommandHandler("help", self.cmd_help))

    def _check_auth(self, update: Update) -> bool:
        """Check if user is authorized."""
        if not update.effective_user:
            return False
            
        user_id = str(update.effective_user.id)
        # if hasattr(self, 'authorized_id') and self.authorized_id:
        #      # If ID stored in self (not currently), logic here
        #      pass
        
        # Check against config
        if user_id != str(AUTHORIZED_USER_ID):
            logger.warning(f"Unauthorized access attempt from ID: {user_id}")
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        await update.message.reply_text(
            "🛡 *Hostile Object Estimation System*\n"
            "System is online and monitoring.\n\n"
            "Use /help to see available commands.",
            parse_mode="Markdown"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        await update.message.reply_text(
            "📋 *Commands:*\n"
            "/scan - Get current snapshot\n"
            "/status - System status overview\n"
            "/summary - Last 24h detection stats\n"
            "/reset - Clear detection history\n"
            "/help - Show this menu",
            parse_mode="Markdown"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        status_text = self.stats.get_status_short()
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        summary_text = self.stats.get_summary(hours=24)
        await update.message.reply_text(summary_text, parse_mode="Markdown")

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        
        with self.state._lock:
            self.state.detections.clear()
            self.state.class_counts.clear()
            
        await update.message.reply_text("✨ Detection history and stats cleared.")

    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a snapshot of the current frame."""
        if not self._check_auth(update) or not update.message: return
        
        frame = self.state.get_latest_frame()
        if frame is None:
            await update.message.reply_text("❌ No frame available (camera offline?)")
            return

        # Convert BGR (OpenCV) to RGB (Pillow)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        
        # Save to memory buffer as JPEG
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY)
        bio.seek(0)
        
        await update.message.reply_photo(photo=bio, caption="📸 Snapshot")

    def run(self):
        """Run the bot (blocking). Should be run in a separate thread."""
        if self.app:
            logger.info("Telegram Bot polling started...")
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.app.run_polling()
