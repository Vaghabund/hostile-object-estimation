import logging
import sys
from pathlib import Path
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    LOG_LEVEL,
    CPU_THREADS,
    ANALYTICS_DB_PATH,
    ANALYTICS_RETENTION_DAYS,
    ZONES,
    ALERT_PRIORITY_CLASSES,
    ANOMALY_DETECTION_ENABLED,
    ANOMALY_MIN_HISTORY_DAYS,
    DWELL_OUTLIER_MIN_SAMPLES,
    SEQUENCE_TARGET_CLASS,
    SEQUENCE_VEHICLE_CLASSES,
    SEQUENCE_WINDOW_SECONDS,
)
from src.camera import FrameCapture
from src.motion_detector import MotionDetector
from src.yolo_detector import YOLODetector
import threading
from src.telegram_bot import TelegramBot
from src.shared_state import SharedState
from src.stats import StatsGenerator
from src.image_utils import attach_detection_thumbnails
from src.detection_stabilizer import DetectionStabilizer
from src.runtime_settings import RuntimeSettings
from src.analytics_db import AnalyticsDB
from src.analysis import AnalysisEngine

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress verbose library logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


def main():
    """Main detection loop."""
    # ASCII Art Banner
    print("""
                                                                                                                                    
                                                                                                                                                  
                     #@@@@@@@@@@@@@@                                                                                                              
                 @@@@@@@@@@@@@@@@@@@@@@:                                                                                                          
              +@@@@@@@@@         +@@@@@@@@%%+:.                                                                                                   
             @@@@@@                  @@@@@@#+%%%%#**+=-.                                                                                          
            @@@@*                      #@@@@@    -=+*########*+-:                                                                                 
            @@@                          @@@@@%           :-=++**###**+=-.                                                                        
            @@@                            @@@@@                   .-==+*%%%%%#*=-.                                                               
            @@@@                             @@@@@                          .-=+**##%%@%*+-:                                                      
             @@@@                             @@@@@=                                 .:=++*##*****+=:.       -:                                   
              @@@@                              @@@@@                                          ..:=+**++++=---=+@%                                
              :@@@@                        %@@@@@-@@@@                                                  ..     .+@@#                              
                @@@@                      :@@@@@*#@@@@@@                                                        . .@@                             
                 @@@@                    -@@@=+@*%@@@@@@@                                                        :+ -@.                           
                  @@@@                  -@@ @@@@@@@@@@ @@@=                                                          :@=                          
                   @@@@                ..@+@@@@  @@@%@@ @@@@@@-                                                      ..@.                         
                    @@@@:            %@@@:@@       @@@@@ @@@@@@@@@@@@@@@@@@@@+:                                       .-@                         
                     @@@@@           @@@@@          -@ @   +@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*                           #@                        
                      @@@@@@.        @@@@*           @@@*     @@@@@@@@@@=   *@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@=         * @:                       
                        @@@@@        #-@:            @@@@     @@@@@@@@@@@@@@@@@@@@@@@@@@@@% -@@@@@@@@@@@@@@@@@@@@@+     :+-                       
                          @@@        @@@@           %@=%-     @@-    -#@@@@@@@@@@%##%@@@@@@@@@@@@@@@@@@@@@@= -@@@@@ .:  :-                        
                          @@@        @@@@@@        +@@@@      @@ .*%@@@@@@@@@@@%+-       -#@@@@@@@@@@@@@@@@@@@@@@@@#  :-                          
                          .@@=       @@@#@@@@     #@#@@#     @@@                            :+@@@@@@@@@@@:   :%@@#@@                              
                           @@@@@#     *@@:%@@@@@@@@%@@= .    @@@@@@@@@@@@@@@@@@@#+:             .      .  :@@@@@@@@+                              
                           @@@@ @      #@@  =@@@@@@@@+ : :  @@@                              -#@@@@@@@@@@@=@@@@@@@%                               
                            @@@@@       %@@@@@@#@@@@@   :  @@@#                                          #@@+@@@                                  
                            .@@@@        :@@@@@@@@@=      @@@@                                          +@@@@@@                                   
                             *@@@@          -@@@@       +@@@@                      ....:+*#%@@@@@@@@@@@@@@%@@@#                                   
                              .@@@@@                   @@@@*#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#@@@%                                    
                                @@@@@@@            -@@@@@@ @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ -#%@@@@@@ @@@@@@                                      
                                  @@@@@@@@@@@@@@@@@@@@@@#@@@@@@@@@@@@@@@@@=-::         .  @@@@@@@@@@@@@@@@.                                       
                                    =@@@@@@@@@@@@@@@@@-@@@@@%#%+      -%@%-..:         @@@@@@@@@@@@@@@@                                           
                                          =#@@%+       :@@@@@@@@@@@@@*%:-             @@@@@@                                                      
                                                          @@@@=@@@@@@ %@%-*##+----=%@@@@@           @@@@@@@@@@@+                                  
                                                           @@@@ @@@@#  @@@         :@@@+         @@@@@@@@@@@@@@@@@@                               
                                                            @@@@:       @@@  -@ #+ @@@=        @@@@@@@    .  #@@@@@@@                             
                                                             @@@@@@@@@@@.*@@.@*@@@@@@         @@@@%      -.      @@@@@                            
                                                              @@@@@@@@@@@%-@@@@@ -@@.        @@@@      -++**:    +.%@@@                           
                                                               @@@@@   .@@%-@@@@@@@%       .@@@@*%%%#####- .+=-=+@@.:@@@                          
                                                                *@@@*    =@-  =@@@@@@@@@@@@@@@@:-:  .-.      ::-=+@@ -@@.                         
                                                                 @@@@*%%@@%   +#@@@@@@@@@@@@@=+@@@@@@@@+          =@@.@@@                         
                                                                 @@@@         @= @-:#@@@@@@@@@@@@@@@@@@@%          @@.@@@                         
                                                                 @@@@@@@@@%%%%@#@@@@@@@@%#+=:.        *@@.         @@  @@                         
                                                                 @@%@   =.    @ : .       ...:-++=-:-#@@@.         @@  @@                         
                                                                 @@@@   =     @ - =@@@@%*++++#*==#@@@@@@+     . ..+@@ @@@                         
                                                                 @@@@   =.    @ +@@@@@@@@@@@@@: ::+#@%. ==   *#-*@@@+ @@@                         
                                                                 @@@@@*=%@@@@@@@@@@@@@@@@@@@@@@*  :***#@@@#+@%+=++** @@@                          
                                                                 =@@@@@@@@@@@@@@@@           @@@@  =##*- :@@*      :@@@@                          
                                                                   +@@@@@@@@@@@%.             @@@@.          . -  @@@@%                           
                                                                                               @@@@@@        + @@@@@@+                            
                                                                                                =@@@@@@@@@@@@@@@@@@@                              
                                                                                                   @@@@@@@@@@@@@@                                 
                                                                                                                                                  
    """)
    logger.info("Starting Hostile Object Estimation System")

    # Cap OpenCV + PyTorch worker threads so motion encoding (in alert threads) and
    # YOLO inference (main loop) don't oversubscribe weak CPUs. See CPU_THREADS.
    try:
        import cv2
        cv2.setNumThreads(CPU_THREADS)
        import torch
        torch.set_num_threads(CPU_THREADS)
        logger.info(f"CPU thread cap set to {CPU_THREADS}")
    except Exception as e:
        logger.warning(f"Could not set CPU thread caps: {e}")

    # Initialize runtime settings
    runtime_settings = RuntimeSettings()

    # Initialize camera
    camera = FrameCapture()
    motion_detector = MotionDetector(runtime_settings)
    shared_state = SharedState()
    stats_generator = StatsGenerator(shared_state)
    stabilizer = DetectionStabilizer(runtime_settings)

    # Analytics: persistence + interpretation (baselines, anomalies, digests, reports)
    analytics_db = AnalyticsDB(ANALYTICS_DB_PATH)
    analytics_db.prune(ANALYTICS_RETENTION_DAYS)
    analysis_engine = AnalysisEngine(
        analytics_db,
        priority_classes=ALERT_PRIORITY_CLASSES,
        zones=ZONES,
        anomaly_enabled=ANOMALY_DETECTION_ENABLED,
        anomaly_min_history_days=ANOMALY_MIN_HISTORY_DAYS,
        dwell_outlier_min_samples=DWELL_OUTLIER_MIN_SAMPLES,
        sequence_target_class=SEQUENCE_TARGET_CLASS,
        sequence_vehicle_classes=SEQUENCE_VEHICLE_CLASSES,
        sequence_window_s=SEQUENCE_WINDOW_SECONDS,
    )

    # Initialize YOLO (this might take a moment to download weights)
    try:
        yolo_detector = YOLODetector(runtime_settings)
    except Exception as e:
        logger.error(f"Critical error initializing YOLO: {e}")
        return

    # Phase 5: Start Telegram Bot in background thread
    bot = TelegramBot(shared_state, runtime_settings, analysis_engine)
    if bot.app:
        bot_thread = threading.Thread(target=bot.run, daemon=True)
        bot_thread.start()
        bot.start_digest_scheduler()
    
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
        last_prune = time.time()

        while True:
            frame, frame_id = camera.get_frame()
            
            if frame is None:
                logger.warning("Failed to get frame, retrying...")
                time.sleep(0.1)
                continue

            frame_count += 1

            # One owned copy per iteration. Everything that stores or defers work on
            # this frame (shared_state, frame buffer, Telegram worker threads) shares
            # this single snapshot instead of each making its own deep copy.
            frame_snapshot = frame.copy()

            # Phase 2: Motion Detection
            if motion_detector.detect(frame):
                # Phase 3: YOLO Inference (triggered by motion)
                detections = yolo_detector.detect(frame)
                stabilized = stabilizer.filter(detections)
                stable_detections = stabilized.display
                confirmed_detections = stabilized.confirmed
                stale_track_ids = stabilized.stale_track_ids

                # Always refresh the frame snapshot so /scan sees the latest image
                shared_state.update_frame_with_detections(frame_snapshot, stable_detections)

                # Buffer frames for each stable detection (for best-frame selection)
                for det in stable_detections:
                    shared_state.buffer_frame(frame_snapshot, det)

                if confirmed_detections:
                    attach_detection_thumbnails(frame_snapshot, confirmed_detections)
                    shared_state.add_detections(confirmed_detections)
                    analysis_engine.record_detections(confirmed_detections, frame_snapshot.shape)

                    # Log to console
                    for d in confirmed_detections:
                        logger.info(f"DETECTED: {d.class_name} ({d.confidence:.2f}) ID: {d.track_id}")

                    # Immediate Telegram push only for priority classes or anomalies
                    # (novel hour-of-day, vehicle-then-person sequence). Everything
                    # else is recorded silently and surfaces in the periodic digest.
                    if bot.app:
                        now = time.time()
                        classes_present = {d.class_name for d in confirmed_detections}
                        alert_classes = {
                            c for c in classes_present
                            if analysis_engine.should_alert_immediately(c, now)[0]
                        }
                        to_alert = [d for d in confirmed_detections if d.class_name in alert_classes]
                        if to_alert:
                            bot.send_detection_alert(frame_snapshot, to_alert)

                # Handle track-end alerts for stale tracks
                for track_id in stale_track_ids:
                    track_summary = analysis_engine.finalize_track(track_id, shared_state, frame_snapshot.shape)
                    if bot.app and bot._bot:
                        bot.handle_track_end(track_id, track_summary)  # clears its own buffer
                    else:
                        # No bot to consume the buffered frames — release them so
                        # track_frames doesn't grow without bound.
                        shared_state.clear_track_frames(track_id)
            else:
                # Keep the newest frame available without discarding the last detections
                shared_state.update_frame(frame_snapshot)

            # Debug: Show FPS every 30 frames
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                logger.debug(f"FPS: {fps:.1f} | Frames: {frame_count}")

            # Log stats summary every hour to console
            current_time = time.time()
            if current_time - last_stats_log > 3600:
                summary = stats_generator.get_status_short()
                logger.info(f"STATUS UPDATE:\n{summary.replace('*', '')}")
                last_stats_log = current_time

            # Prune old analytics rows once a day
            if current_time - last_prune > 86400:
                analytics_db.prune(ANALYTICS_RETENTION_DAYS)
                last_prune = current_time

            # cap.read() blocks until the next frame (BUFFERSIZE=1), so it already
            # paces the loop to the camera's FPS. A tiny yield keeps CPU from
            # busy-spinning on backends where read() can return without blocking.
            time.sleep(0.001)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        camera.stop()
        analytics_db.close()
        logger.info("System stopped")


if __name__ == "__main__":
    main()
