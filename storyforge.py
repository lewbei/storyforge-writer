#!/usr/bin/env python3
"""
StoryForge AI - Command-line entry point with logging.

Usage:
    python storyforge.py "Your writing prompt here"
    python storyforge.py --recover path/to/context.md
    python storyforge.py --status ProjectName
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add the current directory to Python path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Setup logging
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Create log filename with timestamp
log_filename = LOG_DIR / f"storyforge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point with error handling and logging."""
    logger.info("=" * 60)
    logger.info("StoryForge AI - Starting")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Command: {' '.join(sys.argv)}")
    logger.info(f"Log file: {log_filename}")
    logger.info("=" * 60)

    try:
        # Import the main module
        logger.info("Importing storyforge.main...")
        from storyforge.main import main as storyforge_main
        logger.info("Successfully imported storyforge.main")

        # Run the main application
        logger.info("Starting StoryForge main application...")
        storyforge_main()

        logger.info("StoryForge completed successfully")
        return 0

    except ImportError as e:
        logger.error(f"Import error: {e}", exc_info=True)
        print(f"\nImport Error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Check if all dependencies are installed: pip install -r requirements.txt")
        print("2. Verify Python environment is activated")
        print("3. Check that storyforge/ directory exists with __init__.py")
        print(f"\nFull error log saved to: {log_filename}")
        return 1

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}", exc_info=True)
        print(f"\nFile Error: {e}")
        print(f"\nFull error log saved to: {log_filename}")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nError: {e}")
        print(f"\nFull error log saved to: {log_filename}")
        return 1

    finally:
        logger.info("StoryForge session ended")
        logger.info("=" * 60)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
