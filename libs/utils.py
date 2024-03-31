#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Utilities
"""

import sys
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame

def setup_logging(loglevel:str="DEBUG") -> logging.Logger:
    """Set up a logger.

    Setup in main application:

        logger = setup_logging()

    Setup in library code:

        logger = logging.getLogger(__name__)

    Usage example 1: Debug a variable

        a = 1
        logger.debug(f"a: {a}")

    Usage example 2: Exit due to an error

        match a:
            case 1:
                pass
            case _:
                logger.error(f"Unexpected value of a: {a}")
                sys.exit("Exit due to error. See above.")
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fmt = '%(asctime)s %(levelname)s in \"%(funcName)s()\" at %(filename)s:%(lineno)d\n\t%(message)s'
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(loglevel)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

class Window:
    """OS window information.

    size -- (w,h)
    flags -- OR'd bitflags. Default is pygame.RESIZABLE
    """
    def __init__(self, size:tuple, flags:int=pygame.RESIZABLE):
        self.size = size
        self.flags = flags

if __name__ == '__main__':
    from pathlib import Path
    print(f"Run doctests in {Path(__file__).name}")
    import doctest
    doctest.testmod()
