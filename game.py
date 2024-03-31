#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Vector racing game
"""

import sys
from pathlib import Path
import atexit
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
from libs.utils import setup_logging, Window

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up GUI
    pygame.quit()

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        os.environ["SDL_VIDEO_WINDOW_POS"] = "800,0"    # Position window in upper right

        # Set up colors
        self.colors = {}
        self.colors['color_game_art_bgnd'] = Color(20,20,20)
        self.colors['color_os_window_bgnd'] = Color(30,30,30)

        # Set up surfaces
        self.surfs = {}
        w = 16; h = 9; scale = 40
        self.window = Window((scale*w,scale*h))
        ### Surface((width, height), flags=0, Surface) -> Surface
        self.surfs['surf_game_art'] = pygame.Surface(self.window.size, flags=0)
        ### set_mode(size=(0, 0), flags=0, depth=0, display=0, vsync=0) -> Surface
        self.surfs['surf_os_window'] = pygame.display.set_mode(
                self.window.size,
                self.window.flags,
                )

        # FPS
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True: self.game_loop()

    def handle_ui_events(self) -> None:
        ### get_mods() -> int
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT: sys.exit()
                case pygame.KEYDOWN:
                    match event.key:
                        case pygame.K_q: sys.exit()
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def game_loop(self) -> None:
        self.handle_ui_events()

        # Clear screen
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])
        self.surfs['surf_os_window'].fill(self.colors['color_os_window_bgnd'])

        # Draw game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(
                ### scale(surface, size, dest_surface=None) -> Surface
                pygame.transform.scale(self.surfs['surf_game_art'], self.window.size),
                (0,0),
                )

        # Draw to the OS Window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)                           # Safe shutdown
    logger = setup_logging()
    Game().run()
