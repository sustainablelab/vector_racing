#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Vector racing game
"""

from pathlib import Path
import atexit
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from libs.utils import setup_logging

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up GUI
    pygame.quit()


if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)                           # Safe shutdown
    logger = setup_logging()

