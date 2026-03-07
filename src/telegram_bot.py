import logging
import asyncio
import io
import os
import time
import cv2
import threading
import numpy as np
from collections import defaultdict
from PIL import Image
import requests
from telegram import Update
from telegram.error import NetworkError
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from config.settings import (
    TELEGRAM_BOT_TOKEN, 
    AUTHORIZED_USER_ID,
    TELEGRAM_IMAGE_QUALITY,
    ENV_FILE,
    FRAME_SELECTION_ENABLED,
    FRAME_SELECTION_MODE,
    FACE_DETECTOR_TYPE,
    FACE_DETECTOR_MIN_SIZE,
    FRAME_SELECTION_FACE_WEIGHT,
    FRAME_SELECTION_SHARPNESS_WEIGHT,
    FRAME_SELECTION_CONFIDENCE_WEIGHT
)
from src.shared_state import SharedState
from src.stats import StatsGenerator
from src.image_utils import (
    draw_detections_on_frame,
    create_detection_collage_from_history
)
from src.runtime_settings import RuntimeSettings
from src.frame_quality_scorer import FrameQualityScorer

logger = logging.getLogger(__name__)

# COCO class names (80 classes that YOLOv8 can detect)
YOLO_COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush"
]

class TelegramBot:
    """
    Telegram bot for remote control and monitoring.
    Runs in its own thread/loop.
    """
    def __init__(self, shared_state: SharedState, runtime_settings: RuntimeSettings):
        self.state = shared_state
        self.settings = runtime_settings
        self.stats = StatsGenerator(shared_state)
        self._last_network_error_log = 0.0
        self._command_timestamps = defaultdict(float)
        self._rate_limit_seconds = 2.0
        self._bot = None  # Will be set after app is created
        
        # Initialize frame quality scorer for best-frame selection
        self.frame_scorer = FrameQualityScorer(
            face_detector_type=FACE_DETECTOR_TYPE,
            min_face_size=FACE_DETECTOR_MIN_SIZE,
            face_weight=FRAME_SELECTION_FACE_WEIGHT,
            sharpness_weight=FRAME_SELECTION_SHARPNESS_WEIGHT,
            confidence_weight=FRAME_SELECTION_CONFIDENCE_WEIGHT
        )
        
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token is missing! Bot will not start.")
            self.app = None
            return
        
        if not AUTHORIZED_USER_ID:
            logger.warning("AUTHORIZED_USER_ID is missing! Bot will not start.")
            self.app = None
            return

        try:
            int(AUTHORIZED_USER_ID)
        except ValueError:
            logger.warning("AUTHORIZED_USER_ID is not a valid integer! Bot will not start.")
            self.app = None
            return

        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._bot = self.app.bot  # Store bot reference for sending notifications
        self._register_handlers()
        logger.info("Telegram Bot initialized successfully.")

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
        
        # Settings commands
        self.app.add_handler(CommandHandler("settings", self.cmd_settings))
        self.app.add_handler(CommandHandler("set", self.cmd_set))
        self.app.add_handler(CommandHandler("classes", self.cmd_classes))
        self.app.add_handler(CommandHandler("enable", self.cmd_enable))
        self.app.add_handler(CommandHandler("disable", self.cmd_disable))
        
        self.app.add_error_handler(self._handle_error)

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

    def _check_rate_limit(self, update: Update, command: str) -> bool:
        """Check if command is rate-limited."""
        if not update.effective_user:
            return True
        
        user_id = update.effective_user.id
        key = f"{user_id}:{command}"
        now = time.time()
        last_time = self._command_timestamps[key]
        
        if now - last_time < self._rate_limit_seconds:
            return False
        
        self._command_timestamps[key] = now
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
            "📋 *Commands:*\n\n"
            "*Monitoring:*\n"
            "/scan - Get current snapshot with detections\n"
            "/status - System status overview\n"
            "/summary - Last 24h stats with visual summary\n"
            "/reset - Clear detection history\n\n"
            "*Settings:*\n"
            "/settings - View current settings\n"
            "/set <param> <value> - Change a setting\n"
            "/classes - List available object classes\n"
            "/enable <class> - Enable detection for class\n"
            "/disable <class> - Disable detection for class\n\n"
            "/help - Show this menu",
            parse_mode="Markdown"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        
        if not self._check_rate_limit(update, "status"):
            await update.message.reply_text("⏳ Please wait 2 seconds between status requests")
            return
        
        logger.info("Command /status received")
        status_text = self.stats.get_status_short()
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_auth(update) or not update.message: return
        
        if not self._check_rate_limit(update, "summary"):
            await update.message.reply_text("⏳ Please wait 2 seconds between summary requests")
            return
        
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
                logger.info(f"Creating visual summary for {len(detections_24h)} detections from last 24h...")
                
                # Check if best-frame selection is enabled for summary
                use_best_frames = FRAME_SELECTION_ENABLED and FRAME_SELECTION_MODE.get("summary", False)
                
                if use_best_frames:
                    # Try to create collage using best frames per track
                    logger.info("Using best-frame selection for summary collage")
                    # Group detections by track_id
                    tracks = {}
                    for d in detections_24h:
                        track_id = d.track_id if d.track_id is not None else f"static_{d.class_name}_{d.bbox[0]}"
                        if track_id not in tracks:
                            tracks[track_id] = []
                        tracks[track_id].append(d)
                    
                    # For each track, try to get best frame (if available in buffer)
                    # Otherwise fall back to thumbnails
                    best_frames = []
                    for track_id, track_dets in tracks.items():
                        if isinstance(track_id, int):
                            # Try to get best frame from buffer
                            best_frame, _ = self._get_best_frame_for_track(track_id)
                            if best_frame is not None:
                                best_frames.append((best_frame, track_dets))
                            elif track_dets and track_dets[0].thumbnail:
                                # Fallback to thumbnail
                                from PIL import Image as PILImage
                                best_frames.append((PILImage.open(io.BytesIO(track_dets[0].thumbnail)), track_dets))
                        else:
                            # Static detection, use thumbnail if available
                            if track_dets and track_dets[0].thumbnail:
                                from PIL import Image as PILImage
                                best_frames.append((PILImage.open(io.BytesIO(track_dets[0].thumbnail)), track_dets))
                    
                    # Create collage from best frames
                    if best_frames:
                        try:
                            from PIL import Image as PILImage
                            from PIL import ImageDraw
                            
                            # Simple grid layout for best frames
                            frame_size = 200
                            cols = min(3, len(best_frames))
                            rows = (len(best_frames) + cols - 1) // cols
                            
                            collage = PILImage.new('RGB', (cols * frame_size, rows * frame_size), color='black')
                            
                            for idx, (frame, dets) in enumerate(best_frames[:20]):  # Max 20 frames
                                row = idx // cols
                                col = idx % cols
                                
                                # Resize frame to fit grid
                                if isinstance(frame, np.ndarray):
                                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if len(frame.shape) == 3 and frame.shape[2] == 3 else frame
                                    frame_pil = PILImage.fromarray(frame_rgb)
                                else:
                                    frame_pil = frame
                                
                                frame_pil = frame_pil.resize((frame_size, frame_size))
                                collage.paste(frame_pil, (col * frame_size, row * frame_size))
                            
                            bio = io.BytesIO()
                            collage.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
                            bio.seek(0)
                            
                            await update.message.reply_photo(
                                photo=bio, 
                                caption="📊 Visual Summary - Best Frames (Last 24h)"
                            )
                            logger.info(f"Visual summary sent with {len(best_frames)} best frames")
                            return
                        except Exception as e:
                            logger.warning(f"Failed to create best-frame collage, falling back to thumbnail collage: {e}")
                
                # Fallback: use original thumbnail collage
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
        
        if not self._check_rate_limit(update, "scan"):
            await update.message.reply_text("⏳ Please wait 2 seconds between scans")
            return
        
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
        if annotated_frame is None:
            logger.warning("Annotated frame is empty; sending text fallback")
            await update.message.reply_text("⚠️ Snapshot unavailable right now.")
            return

        frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        
        # Save to memory buffer as JPEG
        bio = io.BytesIO()
        image.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
        bio.seek(0)
        
        logger.info("Sending annotated snapshot to user")
        sent_photo = await self._reply_photo_with_retry(update, bio, caption)
        if not sent_photo:
            return
        
        # Skip sending individual detection crops to avoid duplicate images

    def _get_best_frame_for_track(self, track_id: int):
        """
        Select the best frame from buffered frames for a track.
        
        Args:
            track_id: The track identifier
            
        Returns:
            Tuple of (best_frame, all_frames) or (None, []) if no frames found
        """
        if track_id is None:
            return None, []
        
        try:
            frame_data = self.state.get_track_frames(track_id)
            if not frame_data:
                logger.warning(f"No buffered frames for track {track_id}")
                return None, []
            
            frames = [f[0] for f in frame_data]  # Extract frame from (frame, detection, timestamp)
            detections = [f[1] for f in frame_data]
            
            best_frame, best_idx = self.frame_scorer.select_best_frame(frames, detections)
            logger.info(f"Selected best frame for track {track_id}: index {best_idx} out of {len(frames)}")
            return best_frame, frames
        except Exception as e:
            logger.error(f"Error selecting best frame for track {track_id}: {e}")
            return None, []

    def send_detection_alert(self, frame, detections, use_best_frame: bool = True):
        """
        Send an alert with detected objects to the authorized user.
        This is called from the main thread when motion + detection occurs.
        Thread-safe method.
        
        Args:
            frame: Current frame
            detections: List of Detection objects
            use_best_frame: Whether to use best-frame selection (if enabled in settings)
        """
        if not self._bot or not AUTHORIZED_USER_ID:
            return
        
        try:
            alert_frame = frame
            
            # Use best-frame selection if enabled
            if use_best_frame and FRAME_SELECTION_ENABLED and FRAME_SELECTION_MODE.get("alerts", False):
                # Try to select best frame from any buffered frames
                # (frames are buffered as detections stabilize)
                first_detection = detections[0] if detections else None
                if first_detection and first_detection.track_id is not None:
                    best_frame, _ = self._get_best_frame_for_track(first_detection.track_id)
                    if best_frame is not None:
                        alert_frame = best_frame
                        logger.debug("Using best frame for detection alert")
            
            # Draw bounding boxes on frame
            annotated_frame = draw_detections_on_frame(alert_frame, detections)
            
            # Create caption with detection info
            detection_labels = [f"{d.class_name} ({d.confidence:.0%})" for d in detections]
            caption = f"🚨 Detection Alert!\n\n" + "\n".join(f"• {label}" for label in detection_labels)
            
            # Convert to RGB and prepare image
            frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            
            bio = io.BytesIO()
            image.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
            bio.seek(0)
            
            # Send photo in a new thread to avoid blocking main loop
            alert_thread = threading.Thread(
                target=self._send_alert_sync,
                args=(bio, caption),
                daemon=True
            )
            alert_thread.start()
            logger.debug(f"Detection alert queued: {', '.join(detection_labels)}")
            
        except Exception as e:
            logger.error(f"Failed to prepare detection alert: {e}")

    def send_track_end_alert(self, track_id: int):
        """
        Send a follow-up alert with the best frame from a complete detection sequence.
        Called when a track ends (person/object leaves).
        
        Args:
            track_id: The track identifier that just ended
        """
        if not self._bot or not AUTHORIZED_USER_ID or not FRAME_SELECTION_ENABLED:
            return
        
        if not FRAME_SELECTION_MODE.get("alerts", False):
            logger.debug(f"Track-end alerts disabled, skipping for track {track_id}")
            return
        
        try:
            best_frame, all_frames = self._get_best_frame_for_track(track_id)
            if best_frame is None or all_frames is None or len(all_frames) == 0:
                logger.warning(f"No frames to send for ended track {track_id}")
                self.state.clear_track_frames(track_id)
                return
            
            # Get recent detections to associate with this track
            with self.state._lock:
                recent_detections = list(self.state.detections)
            
            # Find detections for this track
            track_detections = [d for d in recent_detections if d.track_id == track_id]
            if not track_detections:
                logger.warning(f"No detections found for ended track {track_id}")
                self.state.clear_track_frames(track_id)
                return
            
            # Get unique classes and average confidence for this track
            unique_classes = set(d.class_name for d in track_detections)
            avg_confidence = sum(d.confidence for d in track_detections) / len(track_detections)
            
            # Draw bounding boxes on best frame (use track_detections for visual info)
            annotated_frame = draw_detections_on_frame(best_frame, track_detections)
            
            # Create caption
            class_labels = ", ".join(sorted(unique_classes))
            caption = f"✅ Track Ended (Best Frame)\n\n" + f"Objects: {class_labels}\n" + f"Avg Confidence: {avg_confidence:.0%}"
            
            # Convert to RGB and prepare image
            frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            
            bio = io.BytesIO()
            image.save(bio, "JPEG", quality=TELEGRAM_IMAGE_QUALITY, optimize=True)
            bio.seek(0)
            
            # Send photo in a new thread
            alert_thread = threading.Thread(
                target=self._send_alert_sync,
                args=(bio, caption),
                daemon=True
            )
            alert_thread.start()
            logger.info(f"Track-end alert queued for track {track_id} with best frame from {len(all_frames)} captures")
            
            # Clean up buffered frames
            self.state.clear_track_frames(track_id)
            
        except Exception as e:
            logger.error(f"Failed to send track-end alert for track {track_id}: {e}")
            # Still clear the frames even on error
            try:
                self.state.clear_track_frames(track_id)
            except:
                pass
    
    
    def _send_alert_sync(self, bio: io.BytesIO, caption: str):
        """Send photo alert in a separate thread using requests (blocking)."""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {"photo": ("frame.jpg", bio, "image/jpeg")}
            data = {
                "chat_id": int(AUTHORIZED_USER_ID),
                "caption": caption,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, files=files, data=data, timeout=10)
            response.raise_for_status()
            logger.info("Detection alert sent successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send photo alert: {e}")
        except Exception as e:
            logger.error(f"Error sending photo alert: {e}")

    def run(self):
        """Run the bot (blocking). Should be run in a separate thread."""
        if not self.app:
            return

        logger.info("Telegram Bot polling started...")
        
        max_retries = 20
        base_delay = 5
        
        for attempt in range(max_retries):
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                logger.info("Starting polling connection to Telegram...")
                # Disable signal handlers since we're running in a background thread
                # (signal handlers only work in the main thread)
                self.app.run_polling(
                    poll_interval=2.0,
                    timeout=30,
                    bootstrap_retries=-1,
                    close_loop=False,
                    stop_signals=None  # Disable signal handlers for thread safety
                )
                
                if not loop.is_closed():
                    loop.close()
                break

            except Exception as e:
                delay = min(base_delay * (2 ** attempt), 300)  # Cap at 5 min
                logger.error(f"Telegram attempt {attempt+1}/{max_retries} failed: {e}")
                
                try:
                    if loop is not None and not loop.is_closed():
                        loop.close()
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up loop: {cleanup_error}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.critical("Max retries exceeded, bot disabled")
                    return

    async def _reply_photo_with_retry(self, update: Update, bio: io.BytesIO, caption: str, retries: int = 3) -> bool:
        """Attempt to send a photo and retry on transient network errors."""
        if not update.message:
            return False

        for attempt in range(1, retries + 1):
            try:
                bio.seek(0)
                await update.message.reply_photo(photo=bio, caption=caption)
                return True
            except NetworkError as exc:
                logger.warning(
                    "Telegram photo send failed (attempt %d/%d): %s",
                    attempt,
                    retries,
                    exc,
                )
                if attempt == retries:
                    await update.message.reply_text(
                        "⚠️ Failed to deliver image due to network issues."
                    )
                    return False
                await asyncio.sleep(2)
            except Exception:
                logger.exception("Unexpected error while sending photo")
                await update.message.reply_text(
                    "⚠️ Unexpected error while sending image."
                )
                return False

        return False

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display current runtime settings."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /settings received")
        
        summary = self.settings.get_settings_summary()
        help_text = (
            "\n\n💡 *Modify settings with:*\n"
            "`/set motion_canny_low 30`\n"
            "`/set motion_canny_high 150`\n"
            "`/set motion_threshold 0.5`\n"
            "`/set motion_cooldown 2.0`\n"
            "`/set yolo_confidence 0.6`\n"
            "`/set stability_frames 3`\n"
            "`/set stability_misses 2`"
        )
        
        await update.message.reply_text(
            summary + help_text,
            parse_mode="Markdown"
        )
    
    def _save_setting_to_env(self, key: str, value):
        """Save a setting to .env file for persistence across restarts."""
        try:
            env_file = ENV_FILE
            if not env_file.exists():
                logger.warning(f".env file not found at {env_file}")
                return False
            
            # Read current .env file
            lines = []
            found = False
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith(f"{key}="):
                        lines.append(f"{key}={value}\n")
                        found = True
                    else:
                        lines.append(line)
            
            # If setting not found, append it
            if not found:
                lines.append(f"{key}={value}\n")
            
            # Write atomically: write to a temp file next to .env, then rename
            tmp_file = env_file.parent / (env_file.name + ".tmp")
            try:
                with open(tmp_file, 'w') as f:
                    f.writelines(lines)
                    f.flush()
                    os.fsync(f.fileno())
                tmp_file.replace(env_file)
            except Exception:
                tmp_file.unlink(missing_ok=True)
                raise
            
            logger.info(f"Saved setting to .env: {key}={value}")
            return True
        except Exception as e:
            logger.error(f"Failed to save setting to .env: {e}")
            return False

    async def cmd_set(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set a runtime parameter."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /set received")
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ Usage: `/set <parameter> <value>`\n\n"
                "Parameters:\n"
                "• motion_canny_low (0-255)\n"
                "• motion_canny_high (0-255)\n"
                "• motion_threshold (0.0-100.0)\n"
                "• motion_cooldown (seconds)\n"
                "• yolo_confidence (0.0-1.0)\n"
                "• stability_frames (min frames)\n"
                "• stability_misses (max missed frames)",
                parse_mode="Markdown"
            )
            return
        
        param = context.args[0].lower()
        value_str = context.args[1]
        
        try:
            if param == "motion_canny_low":
                value = int(value_str)
                self.settings.set_motion_canny_low(value)
                self._save_setting_to_env("MOTION_CANNY_LOW", str(value))
                await update.message.reply_text(f"✅ Motion Canny Low set to {value}\n(persistent after restart)")
                
            elif param == "motion_canny_high":
                value = int(value_str)
                self.settings.set_motion_canny_high(value)
                self._save_setting_to_env("MOTION_CANNY_HIGH", str(value))
                await update.message.reply_text(f"✅ Motion Canny High set to {value}\n(persistent after restart)")
                
            elif param == "motion_threshold":
                value = float(value_str)
                self.settings.set_motion_pixel_threshold(value)
                self._save_setting_to_env("MOTION_PIXEL_THRESHOLD", str(value))
                await update.message.reply_text(f"✅ Motion Pixel Threshold set to {value}%\n(persistent after restart)")
                
            elif param == "motion_cooldown":
                value = float(value_str)
                self.settings.set_motion_cooldown(value)
                self._save_setting_to_env("MOTION_COOLDOWN", str(value))
                await update.message.reply_text(f"✅ Motion Cooldown set to {value}s\n(persistent after restart)")
                
            elif param == "yolo_confidence":
                value = float(value_str)
                self.settings.set_yolo_confidence(value)
                self._save_setting_to_env("YOLO_CONFIDENCE", str(value))
                await update.message.reply_text(f"✅ YOLO Confidence set to {value:.2f}\n(persistent after restart)")
                
            elif param == "stability_frames":
                value = int(value_str)
                self.settings.set_stability_frames(value)
                self._save_setting_to_env("DETECTION_STABILITY_FRAMES", str(value))
                await update.message.reply_text(f"✅ Stability Frames set to {value}\n(persistent after restart)")
                
            elif param == "stability_misses":
                value = int(value_str)
                self.settings.set_stability_max_misses(value)
                self._save_setting_to_env("DETECTION_STABILITY_MAX_MISSES", str(value))
                await update.message.reply_text(f"✅ Stability Max Misses set to {value}\n(persistent after restart)")
                
            else:
                await update.message.reply_text(f"❌ Unknown parameter: {param}")
                
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid value: {value_str}")
        except Exception as e:
            logger.error(f"Error setting parameter: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def cmd_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List available YOLO classes and their status."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /classes received")
        
        enabled_classes = self.settings.get_enabled_classes()
        
        if not enabled_classes:
            status_text = "✅ *All classes enabled*\n\n"
        else:
            status_text = f"⚙️ *Enabled: {len(enabled_classes)} classes*\n\n"
        
        status_text += (
            "Use `/enable <class>` to enable specific class\n"
            "Use `/disable <class>` to disable a class\n"
            "Use `/enable all` to enable all classes\n\n"
            "*Available classes:*\n"
        )
        
        # Show first 20 classes as examples
        for cls in YOLO_COCO_CLASSES[:20]:
            if not enabled_classes or cls in enabled_classes:
                status_text += f"✅ {cls}\n"
            else:
                status_text += f"❌ {cls}\n"
        
        status_text += f"\n...and {len(YOLO_COCO_CLASSES) - 20} more classes available"
        
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def cmd_enable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable detection for a specific class."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /enable received")
        
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: `/enable <class_name>` or `/enable all`\n"
                "Example: `/enable person`",
                parse_mode="Markdown"
            )
            return
        
        class_name = " ".join(context.args).lower()
        
        if class_name == "all":
            self.settings.set_enabled_classes(set())
            await update.message.reply_text("✅ All classes enabled")
        else:
            self.settings.add_enabled_class(class_name)
            await update.message.reply_text(f"✅ Class '{class_name}' enabled")

    async def cmd_disable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable detection for a specific class."""
        if not self._check_auth(update) or not update.message: return
        logger.info("Command /disable received")
        
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: `/disable <class_name>`\n"
                "Example: `/disable car`",
                parse_mode="Markdown"
            )
            return
        
        class_name = " ".join(context.args).lower()
        
        enabled_classes = self.settings.get_enabled_classes()
        
        # If all classes are currently enabled, we need to enable all except this one
        if not enabled_classes:
            # Enable all COCO classes except the one being disabled
            all_classes = set(YOLO_COCO_CLASSES)
            all_classes.discard(class_name)
            self.settings.set_enabled_classes(all_classes)
            await update.message.reply_text(
                f"✅ Class '{class_name}' disabled\n"
                f"ℹ️ Other classes remain enabled. Use /classes to see all."
            )
        else:
            self.settings.remove_enabled_class(class_name)
            remaining = self.settings.get_enabled_classes()
            if not remaining:
                await update.message.reply_text(
                    f"⚠️ All classes now disabled! Use `/enable all` to re-enable detection.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"✅ Class '{class_name}' disabled")

    async def _handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Throttle noisy network errors so console stays readable."""
        error = getattr(context, "error", None)
        if isinstance(error, NetworkError):
            now = time.monotonic()
            if now - self._last_network_error_log >= 30:
                logger.warning("Telegram connection hiccup detected, retrying quietly: %s", error)
                self._last_network_error_log = now
            return

        logger.exception("Unhandled Telegram error", exc_info=error)
