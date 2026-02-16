import logging
import sys
from pathlib import Path
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import LOG_LEVEL
from src.camera import FrameCapture
from src.motion_detector import MotionDetector
from src.yolo_detector import YOLODetector
import threading
from src.telegram_bot import TelegramBot
from src.shared_state import SharedState
from src.stats import StatsGenerator

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main detection loop."""
    logger.info("Starting Hostile Object Estimation System")
    
    # Initialize camera
    camera = FrameCapture()
    motion_detector = MotionDetector()
    shared_state = SharedState()
    stats_generator = StatsGenerator(shared_state)
    
    # Initialize YOLO (this might take a moment to download weights)
    try:
        yolo_detector = YOLODetector()
    except Exception as e:
        logger.error(f"Critical error initializing YOLO: {e}")
        return

    # Phase 5: Start Telegram Bot in background thread
    bot = TelegramBot(shared_state)
    if bot.app:
        bot_thread = threading.Thread(target=bot.run, daemon=True)
        bot_thread.start()
    
    try:
        camera.start()
    except Exception as e:
        logger.error(f"Failed to start camera: {e}")
        return

    try:
        logger.info("Entering main detection loop...")
        frame_count = 0
        start_time = time.time()
        last_stats_log = 0

        while True:
            frame, frame_id = camera.get_frame()
            
            if frame is None:
                logger.warning("Failed to get frame, retrying...")
                time.sleep(0.1)
                continue

            frame_count += 1
            
            # Phase 2: Motion Detection
            if motion_detector.detect(frame):
                # Phase 3: YOLO Inference (triggered by motion)
                detections = yolo_detector.detect(frame)
                
                if detections:
                    shared_state.add_detections(detections)
                    # Update shared state with frame and associated detections
                    shared_state.update_frame_with_detections(frame, detections)
                    
                    # Simple console output for now
                    for d in detections:
                        logger.info(f"DETECTED: {d.class_name} ({d.confidence:.2f}) ID: {d.track_id}")
                else:
                    # Update frame with no detections, clearing any stale detection state
                    shared_state.update_frame_with_detections(frame, [])
            else:
                # Update frame even when no motion, and clear detections
                shared_state.update_frame_with_detections(frame, [])

            # Debug: Show FPS every 30 frames
            # TODO: Phase 4 - Logging will go here

            # Debug: Show FPS every 30 frames
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                logger.debug(f"FPS: {fps:.1f} | Frames: {frame_count}")

            # Log stats summary every 60 seconds to console (simulating bot request)
            current_time = time.time()
            if current_time - last_stats_log > 60:
                summary = stats_generator.get_status_short()
                logger.info(f"STATUS UPDATE:\n{summary.replace('*', '')}")
                last_stats_log = current_time

            # Small delay to prevent CPU spinning
            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        camera.stop()
        logger.info("System stopped")


if __name__ == "__main__":
    main()
