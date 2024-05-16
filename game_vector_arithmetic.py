#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Graph paper on my screen for demonstrating vectors and addition.

[x] F11 toggles full screen
[x] Start in full screen -- set is_fullscreen=True when instantiating OsWindow
"""

from pathlib import Path
import sys
import atexit
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color, Rect
from libs.utils import setup_logging

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up GUI
    pygame.font.quit()                                  # Uninitialize the font module
    pygame.quit()                                       # Uninitialize all pygame modules

class OsWindow:
    """OS window information.

    size -- (w,h) - sets initial window size and tracks value when window is resized.
    flags -- OR'd bitflags for window behavior. Windowed: pygame.RESIZABLE, Full Screen: pygame.FULLSCREEN.
    is_fullscreen -- bool to track whether fullscreen or windowed

    Instantiate with a size and flags.
    Read size to get the current size (returns window size if windowed or fullscreen size if fullscreen).
    Write size. The windowed and fullscreen values are tracked internally.

    Example
    -------

    >>> os_window = OsWindow(60*16, 60*9)
    >>> os_window.toggle_fullscreen()
    >>> os_window.handle_WINDOWRESIZED()

    After toggling full screen, user must do this:

        self.surfs['surf_os_window'] = pygame.display.set_mode(self.os_window.size, self.os_window.flags)

    Since that is in 'define_surfaces(OsWindow)', just call that function. The
    other surfaces that depend on the OsWindow size need to be updated anyway.
    """
    def __init__(self, size:tuple, is_fullscreen:bool=False):
        # Set initial sizes for windowed and fullscreen
        self._windowed_size = size
        self._fullscreen_size = pygame.display.get_desktop_sizes()[-1]

        # Set initial state: windowed or fullscreen
        self._is_fullscreen = is_fullscreen

        # Update window size and flags to match state of is_fullscreen
        # (size will set to windowed or fullscreen size depending on is_fullscreen)
        # (flags will set to RESIZABLE or FULLSCREEN depending on is_fullscreen)
        self._set_size_and_flags()

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    @property
    def size(self) -> tuple:
        return self._size

    @property
    def flags(self) -> tuple:
        return self._flags

    def _set_size_and_flags(self) -> None:
        """Set _size and _flags."""
        if self.is_fullscreen:
            # Update w x h of fullscreen (in case external display changed while game is running).
            # Always use last display listed (if I have an external display, it will list last).
            self._fullscreen_size = pygame.display.get_desktop_sizes()[-1]
            self._size = self._fullscreen_size
            self._flags = pygame.FULLSCREEN
        else:
            self._size = self._windowed_size
            self._flags = pygame.RESIZABLE
        # Report new window size
        logger.debug(f"Window size: {self.size[0]} x {self.size[1]}")


    def toggle_fullscreen(self) -> None:
        """Toggle OS window between full screen and windowed.

        List the sizes of the connected displays:

        ### pygame.display.get_desktop_sizes(): [(2256, 1504), (1920, 1080)]
        logger.debug(f"pygame.display.get_desktop_sizes(): {desktop_sizes}")

        Always use the last size listed:

        ### If my laptop is in Ubuntu Xorg mode and is the only display:
        ###     Fullscreen size: (2256, 1504)
        ### If I connect my Acer monitor:
        ###     Fullscreen size: (1920, 1080)
        logger.debug(f"Fullscreen size: {desktop_sizes[-1]}")
        """
        self._is_fullscreen = not self.is_fullscreen
        logger.debug(f"FULLSCREEN: {self.is_fullscreen}")
        self._set_size_and_flags() # Set size and flags based on is_to fullscreen or windowed

    def handle_WINDOWRESIZED(self, event) -> None:
        """Track size of resized OS window in self._windowed_size"""
        logger.debug(f"Window resized")
        self._windowed_size = (event.x, event.y)
        self._set_size_and_flags()

def define_surfaces(os_window:OsWindow) -> dict:
    """Return dictionary of pygame Surfaces.

    :param os_window:OsWindow -- defines OS Window 'size' and 'flags'
    :return dict -- {'surf_name': pygame.Surface, ...}

    Call this to create the initial window.

    Call this again when toggling fullscreen.

    Do not call this when resizing the window.
    """
    surfs = {}                                      # Dict of Pygame Surfaces

    # The first surface is the OS Window. Initialize the window for display.
    ### set_mode(size=(0, 0), flags=0, depth=0, display=0, vsync=0) -> Surface
    surfs['surf_os_window'] = pygame.display.set_mode(os_window.size, os_window.flags)

    # Blend artwork on the game art surface.
    # This is the final surface that is  copied to the OS Window.
    surfs['surf_game_art'] = pygame.Surface(os_window.size, flags=pygame.SRCALPHA)

    # Temporary drawing surface -- draw on this, blit the drawn portion, then clear this.
    surfs['surf_draw'] = pygame.Surface(surfs['surf_game_art'].get_size(), flags=pygame.SRCALPHA)

    return surfs

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        # os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((60*16, 60*9), is_fullscreen=True) # Track OS Window size and flags

        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces (including pygame.display)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True: self.game_loop()

    def game_loop(self) -> None:
        self.handle_ui_events()

        # Draw to the OS window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def handle_ui_events(self) -> None:
        for event in pygame.event.get():
            match event.type:
                # No use for these events yet
                case pygame.AUDIODEVICEADDED: pass
                case pygame.ACTIVEEVENT: pass
                case pygame.MOUSEMOTION: pass
                case pygame.WINDOWENTER: pass
                case pygame.WINDOWLEAVE: pass
                case pygame.WINDOWEXPOSED: pass
                case pygame.VIDEOEXPOSE: pass
                case pygame.WINDOWHIDDEN: pass
                case pygame.WINDOWMOVED: pass
                # case pygame.WINDOWSIZECHANGED: pass
                # case pygame.VIDEORESIZE: pass
                case pygame.WINDOWSHOWN: pass
                case pygame.WINDOWFOCUSGAINED: pass
                case pygame.WINDOWFOCUSLOST: pass
                case pygame.WINDOWTAKEFOCUS: pass
                case pygame.TEXTINPUT: pass
                case pygame.KEYUP: pass
                # Handle these events
                case pygame.QUIT: sys.exit()
                case pygame.WINDOWRESIZED:
                    self.os_window.handle_WINDOWRESIZED(event) # Update OS window size
                    self.update_surfaces() # Update surfaces affected by OS window size
                    logger.debug(f"game art: {self.surfs['surf_game_art'].get_size()}")
                case pygame.KEYDOWN: self.handle_keydown(event)
                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def handle_keydown(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_q: sys.exit()                 # q - Quit
            case pygame.K_F11:
                self.os_window.toggle_fullscreen() # F11 - toggle fullscreen
                define_surfaces(self.os_window)

            case _:
                logger.debug(f"{event.unicode}")

    def update_surfaces(self) -> None:
        """See 'define_surfaces()'"""
        self.surfs['surf_game_art'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)
        self.surfs['surf_draw'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)


if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)
    logger = setup_logging()
    Game().run()
