import logging
import sys
import os
from pathlib import Path
from datetime import datetime

def setup_global_logging(log_dir: str):
    """
    Configures a robust, dual-stream logger for the AgentGUI ecosystem.
    Logs to both stdout (for real-time terminal visibility) and 
    a persistent file in the specified log directory.
    """
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Critical Error: Could not create log directory {log_dir}: {e}")
        return

    # Create a rotating/timestamped filename for the session or daily use
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_path / f"agentgui_{date_str}.log"

    # Define standard format
    log_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name) 1s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. Root Logger Setup
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Capture everything

    # Clear existing handlers to avoid duplicate logs if re-initialized
    if logger.hasHandlers():
        logger.handlers.clear()

    # 2. Stream Handler (Console/Terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Terminal only shows INFO+ to avoid noise
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 3. File Handler (The "Black Box" for errors)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG) # File captures everything including DEBUG
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # 4. Global Exception Hook (The "Crash Capture" mechanism)
    def exception_handler(exctype, value, traceback):
        if issubclass(exctype, KeyboardInterrupt):
            sys.__excepthook__(exctype, value, traceback)
            return

        # Format the error message
        import traceback as tb
        error_msg = "".join(traceback.format_exception(exctype, value, traceback))
        
        logger.critical(f"UNHANDLED EXCEPTION CAPTURED:\n{error_msg}")
        
        # Also print to stdout so the user sees it in terminal immediately
        print(f"\n!!! CRITICAL ERROR DETECTED !!!\n{error_msg}", file=sys.stderr)

    sys.excepthook = exception_handler

    logging.info(f"Global logging initialized. Logging to: {log_file}")
    return logger

if __name__ == "__main__":
    # Test run
    setup_global_logging("/media/sf_CA_Ecosystem/10_Projects/02_AgentGUI/logs")
    logging.info("Test log message.")
    try:
        raise ValueError("Test error for testing the exception hook.")
    except Exception:
        logging.exception("An error occurred during test!")
