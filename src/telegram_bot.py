import logging
import asyncio
import io
import time
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
from src.image_utils import (
    draw_detections_on_frame,
    create_detection_collage_from_history,
    create_latest_detections_collage
)

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
        
        if not AUTHORIZED_USER_ID:
            logger.warning("AUTHORIZED_USER_ID is missing! Bot will not start.")
            self.app = None
            return

        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()
        logger.info("Telegram Bot initialized successfully.")
        logger.info(f"Authorized user ID: {AUTHORIZED_USER_ID}")

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
            logger.warning("Received update without effective_user")
            return False
            
        user_id = str(update.effective_user.id)
        username = update.effective_user.username or "N/A"
        
        # Check against config
        if not AUTHORIZED_USER_ID:
            logger.error("AUTHORIZED_USER_ID is not configured in .env file!")
            return False
            
        if user_id != str(AUTHORIZED_USER_ID):
            logger.warning(f"Unauthorized access attempt from user '{username}' (ID: {user_id})")
            return False
            
        logger.debug(f"Authorized request from user '{username}' (ID: {user_id})")
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /start received")
        await update.message.reply_text(
            "🛡 *Hostile Object Estimation System*\n"
            "System is online and monitoring.\n\n"
            "Use /help to see available commands.",
            parse_mode="Markdown"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /help received")
        await update.message.reply_text(
            "📋 *Commands:*\n"
            "/scan - Get current snapshot with detections\n"
            "/status - System status overview\n"
            "/summary - Last 24h stats with visual summary\n"
            "/reset - Clear detection history\n"
            "/help - Show this menu",
            parse_mode="Markdown"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /status received")
        status_text = self.stats.get_status_short()
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /summary received")
        
        # Send text summary first
        summary_text = self.stats.get_summary(hours=24)
        await update.message.reply_text(summary_text, parse_mode="Markdown")
        
        # Create and send visual summary
        try:
            with self.state._lock:
                recent_detections = list(self.state.detections)
            
            # Filter detections to only those from the last 24 hours
            now = time.time()
            cutoff_time = now - (24 * 3600)
            detections_24h = [d for d in recent_detections if d.timestamp >= cutoff_time]
            
            if detections_24h:
                logger.info(f"Creating visual summary collage for {len(detections_24h)} detections from last 24h...")
                collage = create_detection_collage_from_history(
                    detections_24h, 
                    max_images=20
                )
                
                if collage:
                    bio = io.BytesIO()
                    collage.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
                    bio.seek(0)
                    
                    await update.message.reply_photo(
                        photo=bio, 
                        caption="📊 Visual Summary (Last 24h)"
                    )
                    logger.info("Visual summary sent successfully")
                else:
                    logger.warning("Failed to create collage")
            else:
                logger.info("No detections from the last 24h available for visual summary")
                
        except Exception as e:
            logger.error(f"Error creating visual summary: {e}", exc_info=True)
            # Don't fail the command, text summary was already sent

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /reset received")
        
        with self.state._lock:
            self.state.detections.clear()
            self.state.class_counts.clear()
            
        await update.message.reply_text("✨ Detection history and stats cleared.")

    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a snapshot of the current frame with bounding boxes."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /scan received")
        
        # Get frame and detections
        frame, detections = self.state.get_latest_frame_with_detections()
        
        if frame is None:
            logger.warning("No frame available for snapshot")
            await update.message.reply_text("❌ No frame available (camera offline?)")
            return

        # Draw bounding boxes and labels if detections exist
        if detections:
            logger.info(f"Drawing {len(detections)} detections on frame")
            annotated_frame = draw_detections_on_frame(frame, detections)
            caption = f"📸 Snapshot - {len(detections)} detection(s)"
        else:
            logger.info("No detections to draw on frame")
            annotated_frame = frame
            caption = "📸 Snapshot - No detections"
        
        # Convert BGR (OpenCV) to RGB (Pillow)
        frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        
        # Save to memory buffer as JPEG
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
        bio.seek(0)
        
        logger.info("Sending annotated snapshot to user")
        await update.message.reply_photo(photo=bio, caption=caption)
        
        # If there are detections, also send a collage of individual crops
        if detections:
            try:
                logger.info("Creating detection crops collage...")
                collage = create_latest_detections_collage(
                    frame, 
                    detections,
                    max_crops=9,
                    target_size=(150, 150),
                    collage_width=3
                )
                
                if collage:
                    bio_collage = io.BytesIO()
                    collage.save(bio_collage, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
                    bio_collage.seek(0)
                    
                    await update.message.reply_photo(
                        photo=bio_collage,
                        caption=f"🔍 Detected Objects ({len(detections)})"
                    )
                    logger.info("Detection collage sent successfully")
            except Exception as e:
                logger.error(f"Error creating detection collage: {e}", exc_info=True)
                # Don't fail the command, main image was already sent

    def run(self):
        """Run the bot (blocking). Should be run in a separate thread."""
        if not self.app:
            return

        logger.info("Telegram Bot polling started...")
        
        # Retry loop for network issues
        while True:
            loop = None
            try:
                # Create a new event loop for each attempt to avoid "Event loop is closed" errors
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                logger.info("Starting polling connection to Telegram...")
                self.app.run_polling(
                    poll_interval=2.0,
                    timeout=30,
                    bootstrap_retries=-1,  # Infinite retries on startup
                    close_loop=False       # Don't close the loop automatically so we can manage it
                )
                
                # If we get here, it exited cleanly
                if not loop.is_closed():
                    loop.close()
                break

            except Exception as e:
                logger.error(f"Telegram connection failed: {e}. Retrying in 5s...")
                logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
                try:
                    # Attempt to clean up the loop if it's still open
                    if loop is not None and not loop.is_closed():
                        loop.close()
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up loop: {cleanup_error}")
                
                time.sleep(5)
