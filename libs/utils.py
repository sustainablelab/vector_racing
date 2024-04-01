#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Utilities
"""

import sys
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame

logger = logging.getLogger(__name__)

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

def scale_data(data:list, a:float=0, b:float=1) -> list:
    """Scale a 1d list of data to the range a:b. Useful for making game art.

    Examples
    --------

    >>> scale_data(data=[1,2,3], a=100,b=200)
    [100.0, 150.0, 200.0]

    Note that setting 'a' to the screen-y "bottom" coordinate does the y-flip:
    >>> scale_data(data=[1,2,3], a=200,b=100)
    [200.0, 150.0, 100.0]

    Explanation
    -----------

    We are in one dimension with the following givens:
    - A: MIN data value
    - B: MAX data value
    - a: MIN plot art pixel
    - b: MAX plot art pixel
    - C: some value of data between A and B

    Our goal is to map data value C to plot art pixel c.

    Express C as a linear combination of min/max data:
            A + λ(B-A) = C

    Solve for λ:
                (C-A)
            λ = ────
                (B-A)

    Note that whether we find λ using A,B,C or a,b,c, it is the same λ!
    So we find λ from the data using the above equation.

    Now apply λ to the plot art pixels.

    Rewrite the linear combination like this:
            (1-λ)A + λB = C

    The art goes from a to b. So, substituting into the above,
    substitute a for A, b for B, and c for C:
            (1-λ)a + λb = c
    """
    data_min = min(data)
    data_max = max(data)
    scaled_data = []
    for x in data:
        scale = (x - data_min)/(data_max - data_min)
        scaled_data.append((1-scale)*a + scale*b)
    return scaled_data

class Window:
    """OS window information.

    size -- (w,h) - sets initial window size and tracks value when window is resized.
    flags -- OR'd bitflags for window behavior. Default is pygame.RESIZABLE.
    """
    def __init__(self, size:tuple, flags:int=pygame.RESIZABLE):
        self.size = size
        self.flags = flags
    def handle_WINDOWRESIZED(self, event) -> None:
        """Track size of OS window in self.size"""
        self.size = (event.x, event.y)
        logger.debug(f"Window resized, self.size: {self.size}")

if __name__ == '__main__':
    from pathlib import Path
    print(f"Run doctests in {Path(__file__).name}")
    import doctest
    doctest.testmod()
