#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Vector racing game

[x] Create graph paper
[x] Convert between pixel coordinates and grid coordinates
[x] Render lines with alpha blending efficiently
[x] Render dots (filled circles) with alpha blending efficiently
[x] Make a consistent API for efficient rendering with alpha blending.
[x] Scale dot (filled circle) radius based on grid size
[x] Keep points on the grid as N changes. Do not respect original pixel location.
[x] Press escape to stop drawing vector
[x] Second mouse click stores the vector and a new vector starts
    [x] Determine vector drawing state by checking if self.vector.start == None
    [x] Store drawn vectors in list self.vectors
[x] Store drawn vectors -- IN GRID SPACE, NOT PIXEL SPACE!
[x] Draw the stored vectors!
[ ] Undo/redo last drawn vector
[ ] Show x and y components of the vector being drawn
"""

import sys
from pathlib import Path
import atexit
import logging
from dataclasses import dataclass
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color, Rect
from libs.utils import setup_logging, Window, scale_data, Text, DebugHud
from libs.graph_paper import GraphPaper, xfm_pix_to_grid, xfm_grid_to_pix
from libs.geometry import Line

def shutdown() -> None:
    if logger: logger.info("Shutdown")
    # Clean up GUI
    pygame.font.quit()                                  # Uninitialize the font module
    pygame.quit()                                       # Uninitialize all pygame modules

class Mouse:
    def __init__(self, game):
        self.game = game
        self.coords = {}

    def update(self) -> None:
        pix_mpos = pygame.mouse.get_pos()
        # Xfm mouse position from window pixel coordinates to "snapped" grid coordinates
        self.coords['grid'] = xfm_pix_to_grid(
                pix_mpos,
                self.game.graphPaper,
                self.game.surfs['surf_game_art'])
        # Xfm back to pixels to get "snapped" pixel coordinates
        self.coords['pixel'] = xfm_grid_to_pix(
                self.coords['grid'],
                self.game.graphPaper,
                self.game.surfs['surf_game_art'])

    def render_snap_dot(self, radius:int, color:Color) -> None:
        self.game.render_dot(self.coords['pixel'], radius, color)

@dataclass
class Vector:
    """Store vector 'start' and 'end' in grid coordinates."""
    start:tuple=None
    end:tuple=None

    @property
    def vector(self) -> tuple:
        if not self.start: return (None,None)
        if not self.end: return (None,None)
        return (self.end[0]-self.start[0], self.end[1]-self.start[1])


class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        # os.environ["SDL_VIDEO_WINDOW_POS"] = "800,0"    # Position window in upper right

        # Set up colors
        self.colors = {}
        self.colors['color_clear'] = Color(0,0,0,0)
        self.colors['color_os_window_bgnd'] = Color(30,30,30)
        self.colors['color_game_art_bgnd'] = Color(20,20,20)
        self.colors['color_debug_hud_light'] = Color(200,255,220)
        self.colors['color_debug_hud_dark'] = Color(50,30,0)

        # Set up surfaces
        self.surfs = {}
        # Set aspect ratio and size of game art
        # w = 16; h = 16; scale = 40
        w = 29; h = 16; scale = 50
        self.window = Window((scale*w,scale*h))
        ### Surface((width, height), flags=0, Surface) -> Surface
        self.surfs['surf_game_art'] = pygame.Surface(self.window.size, flags=0)
        ### set_mode(size=(0, 0), flags=0, depth=0, display=0, vsync=0) -> Surface
        self.surfs['surf_os_window'] = pygame.display.set_mode(
                self.window.size,
                self.window.flags,
                )
        # Temporary drawing surface -- draw on this, blit the drawn portion, than clear this.
        self.surfs['surf_draw'] = pygame.Surface(self.surfs['surf_game_art'].get_size(), flags=pygame.SRCALPHA)

        # Game data
        self.graphPaper = GraphPaper(self)
        self.graphPaper.update(N=40, margin=10, show_paper=False)
        self.vector = Vector()                          # An empty vector
        self.vectors = []                               # An empty list of vectors
        self.mouse = Mouse(self)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True: self.game_loop()

    def handle_keydown(self, event) -> None:
        ### get_mods() -> int
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_q: sys.exit()
            case pygame.K_n:
                if kmod & pygame.KMOD_SHIFT:
                    # Decrement and clamp at N=2
                    self.graphPaper.N = max(self.graphPaper.N - 1, 2)
                else:
                    # Increment and clamp at N=40
                    self.graphPaper.N = min(self.graphPaper.N + 1, 40)
            case pygame.K_p:
                self.graphPaper.show_paper = not self.graphPaper.show_paper
            case pygame.K_ESCAPE:
                self.vector = Vector()

    def handle_ui_events(self) -> None:
        for event in pygame.event.get():
            match event.type:
                case pygame.WINDOWRESIZED:
                    self.window.handle_WINDOWRESIZED(event)
                    self.surfs['surf_game_art'] = pygame.Surface(self.window.size, flags=0)
                    self.surfs['surf_draw'] = pygame.Surface(self.surfs['surf_game_art'].get_size(), flags=pygame.SRCALPHA)
                case pygame.QUIT: sys.exit()
                case pygame.KEYDOWN: self.handle_keydown(event)
                case pygame.MOUSEMOTION:
                    # logger.debug(f"{pygame.mouse.get_pos()}")
                    pass
                case pygame.MOUSEBUTTONDOWN:
                    # logger.debug("LEFT CLICK PRESS")
                    if self.vector.start == None:
                        self.vector.start = self.mouse.coords['grid']
                    else:
                        self.vector.end = self.mouse.coords['grid']
                        self.vectors.append(self.vector)
                        # Reset the active vector
                        self.vector = Vector()
                case pygame.MOUSEBUTTONUP:
                    # logger.debug("LEFT CLICK RELEASE")
                    pass
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def game_loop(self) -> None:

        # Get user input
        self.handle_ui_events()
        self.mouse.update()

        # Clear screen
        # self.surfs['surf_os_window'].fill(self.colors['color_os_window_bgnd'])
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])
        # Erase all old artwork
        self.surfs['surf_draw'].fill(self.colors['color_clear'])

        # Fill game art area with graph paper
        self.graphPaper.render(self.surfs['surf_game_art'])

        # Draw a line from start to the dot if I started a vector
        # Set color of the line drawn with the mouse
        line_color = Color(255,255,0,120)
        # Find the size of one grid box
        grid_size = xfm_grid_to_pix((1,self.graphPaper.N-1), self.graphPaper, self.surfs['surf_game_art'])
        # Set dot radii based on the grid_size
        big_radius = int(0.5*0.5*grid_size[0])
        small_radius = int(0.5*big_radius)

        # if self.vector['vector_start']:
        if self.vector.start:
            # Convert vector.start grid coordinates to pixel coordinates
            pix_vector_start = xfm_grid_to_pix(self.vector.start, self.graphPaper, self.surfs['surf_game_art'])
            # Draw started vector
            line = Line(pix_vector_start, self.mouse.coords['pixel'])
            self.render_line(line, line_color, width=5)
            # Draw a dot at the grid intersection closest to the mouse
            self.mouse.render_snap_dot(radius=big_radius, color=Color(0,200,255,150))
            # Draw a dot at the start of the vector
            self.render_dot(pix_vector_start, radius=small_radius, color=Color(255,0,0,150))
        else:
            # Draw a dot at the grid intersection closest to the mouse
            self.mouse.render_snap_dot(radius=big_radius, color=Color(255,0,0,150))

        # Draw the vectors
        for vector in self.vectors:
            # Draw the vector
            pix_vector_start = xfm_grid_to_pix(vector.start, self.graphPaper, self.surfs['surf_game_art'])
            pix_vector_end = xfm_grid_to_pix(vector.end, self.graphPaper, self.surfs['surf_game_art'])
            line = Line(pix_vector_start, pix_vector_end)
            self.render_line(line, line_color, width=5)


        # Draw game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # Create and render the debug HUD
        debugHud = DebugHud(self)

        # List vectors as strings as they are added by the user:
        vectors_str_list = [str(v) + ", vector = " + str(v.vector) for v in self.vectors]
        vectors_str = "\n".join(vectors_str_list)
        debugHud.add_text(
                f"Mouse: {self.mouse.coords['grid']}"
                f"\nN: {self.graphPaper.N}, grid_size: {grid_size} pixels"
                f"\n{vectors_str}"
                )
        if self.graphPaper.show_paper:
            debugHud.render(self.colors['color_debug_hud_dark'])
        else:
            debugHud.render(self.colors['color_debug_hud_light'])

        # Draw to the OS Window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def render_clean(self) -> None:
        """Clean up the temporary drawing surface for the next use.

        I clean after making the graph paper grid. But that's it. Usually, it
        is not necessary to clean.

        Don't clean too often! Frame rate will drop if the temporary drawing
        surface is large. Only clean if the desired drawing area is dirty.

        The symptom of a dirty area is that older draw calls are showing up --
        if there is alpha blending, these dirty area regions will show up less
        transparent (because they are blitted multiple times). Or the
        rectangular region being copied will look like a window into older
        drawing data.
        """
        self.surfs['surf_draw'].fill(self.colors['color_clear'])

    def render_rect_area(self, rect:Rect) -> None:
        """Low-level rendering -- don't call this directly.

        See also:
            render_line
            render_dot
        """
        self.surfs['surf_game_art'].blit(
                self.surfs['surf_draw'],                # On this surface
                rect,                                   # Go rect topleft x,y
                rect,                                   # Copy this rect area to game art
                special_flags=pygame.BLEND_ALPHA_SDL2   # Use alpha blending
                )

    def render_line(self, line:Line, color:Color, width:int) -> None:
        """Render a Line on the game art with pygame.draw.line().

        line -- Line(start_pos, end_pos)
        color -- pygame.Color(R,G,B,A)
        width -- line thickness in pixels
        """
        ### line(surface, color, start_pos, end_pos, width=1) -> Rect
        line_rect = pygame.draw.line(self.surfs['surf_draw'], color, line.start_pos, line.end_pos, width)
        self.render_rect_area(line_rect)

    def render_dot(self, center:tuple, radius:int, color:Color) -> None:
        """Render a filled-in circle on the game art with pygame.draw.circle().

        center: circle center (x,y) in pixel coordinates
        radius: circle radius in pixel coordinates
        color: pygame.Color(R,G,B,A)
        """
        ### circle(surface, color, center, radius) -> Rect
        circle_rect = pygame.draw.circle(self.surfs['surf_draw'], color, center, radius)
        self.render_rect_area(circle_rect)

if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)                           # Safe shutdown
    logger = setup_logging()
    Game().run()
