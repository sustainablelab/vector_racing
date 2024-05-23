#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Orbit game.

[x] F11 toggles full screen
[x] Start in full screen -- set is_fullscreen=True when instantiating OsWindow
[x] Resize window with mouse (when window is not fullscreen) and game art surface resizes
[x] Game art fills OS window in full screen
[x] Add DebugHud
[x] Add dark mode toggle: 'd'
[x] Add dark and light color schemes
    * Define 'colors' dict with suffix '_dark' for dark mode and '_light' for light mode
    * API:
        * Game has 'property' methods for each color WITHOUT the '_dark'/'_light' suffix
        * Reading a 'game.color_blah' does the check for dark mode and returns the appropriate color
[x] Draw grid
[x] Center grid on screen
    * 'r' resets the xfm matrix and recenters the grid
[x] Re-center grid when toggling between fullscreen and windowed
[x] Draw mouse dot snapped to grid
[x] Click to draw a vector
    * [x] Click to start a line segment
    * [x] Draw an arrow-head
    * [x] Show the x-y components
[x] Pan with mouse middle button
[x] F10 to toggle gravity setting
[x] Left click to finish a line -- do not start a new line yet
    * [x] Draw finished lines as vectors
[x] 'u' and 'r' to undo/redo line art history
    * Change key binding for view 'reset' to 'R'
[x] Set color with number keys
    * [x] Indicate draw color by changing the color of the mouse dot
    * [x] Save color in the game_history
    * [x] Force vectors will always be the same color, but line segments (also
          drawn as vectors) will be whatever color I chose
[x] Draw force vectors

=====[ Changes from game_cannon to game_orbit begin here ]=====

[x] Set up initial player position
    * [x] Get rid of Player.shot
    * [x] Get rid of Player.is_hit
    * [x] Simplify Player.state to two states: "Pick position" and
          "Step physics" (Get rid of state "Shoot")
    * [x] When player is placed, set first history entry to (0,0) velocity
[x] Calculate physics force vector in 'Player.update_force_vector'
[x] 'Tab' goes to next player
[x] Render player positions
[x] Set color of mouse dot and vector art to the color of the active player
[x] Use active_player to check the state of the player to see how to interpret
    UI actions:
    * In 'handle_mousebuttondown_leftclick'
        * match active_player state:
            * case "Pick position"
    * In 'Player.update':
        * match active_player state:
            * case "Pick position"
    * In 'step_physics':
        * match active_player state:
            * case "Step physics"
[x] Store player's initial position
[x] Create a separate game history for each player
[x] Ctrl+R resets the game: players have not picked positions yet
[x] Undo moves satellite back in history
[x] Shift+U undoes all history for active player but initial position is maintained
[x] FIXED: After undo all of the way, stepping physics again crashes the program
[x] Assign players a number instead of a color
    * Then give Player class an @property color method to look up the color
    * Player also needs access to game state to get colors and dark mode vs light mode
[x] Draw force vectors
[x] Gravity on/off sets force vector to one of nine "normalized" vectors or (0,0)
[x] Ctrl+R to reset game: pick new locations for players
[x] Add force vector to velocity vector and draw resulting vector
    * Record resulting vector to history in 'final_segs'
    * self.physics holds latest value of 'final_seg'
    * [x] Add 'final_seg' to 'handle_mousebuttondown_leftclick'
    * [x] Add 'final_seg' to 'step_physics'
    * [x] Add 'final_seg' to 'draw_game_history'
[x] Color 'line_seg' (inital) and 'final_seg' (final) vectors differently
    * 'final_seg' pops
    * 'line_seg' is muted
[x] Make arrow heads skinnier
[ ] Add more players
[x] Hold 'n' to advance simulation instead of stepping with space bar
"""

import math
from pathlib import Path
from dataclasses import dataclass
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

def signum(num) -> int:
    """Return sign of num as +1, -1, or 0.

    >>> signum(5)
    1
    >>> signum(-5)
    -1
    >>> signum(0)
    0
    >>> signum(0.1)
    1
    >>> signum(-0.1)
    -1
    """
    if num > 0: return 1
    elif num < 0: return -1
    else: return 0

class Text:
    def __init__(self, pos:tuple, font_size:int, sys_font:str):
        self.pos = pos
        self.font_size = font_size
        self.sys_font = sys_font
        self.antialias = True

        if not pygame.font.get_init(): pygame.font.init()

        self.font = pygame.font.SysFont(self.sys_font, self.font_size)

        self.text_lines = []

    def update(self, text:str) -> None:
        """Update text. Split multiline text into a list of lines of text."""
        self.text_lines = text.split("\n")

    def render(self, surf:pygame.Surface, color:Color) -> None:
        """Render text on the surface."""
        for i, line in enumerate(self.text_lines):
            ### render(text, antialias, color, background=None) -> Surface
            text_surf = self.font.render(line, self.antialias, color)
            surf.blit(text_surf,
                      (self.pos[0], self.pos[1] + i*self.font.get_linesize()),
                      special_flags=pygame.BLEND_ALPHA_SDL2
                      )

class DebugHud:
    def __init__(self, game):
        self.game = game
        self.debug_text = ""
        self.text = Text((0,0), font_size=15, sys_font="Roboto Mono")

    def add_text(self, debug_text:str):
        """Add another line of debug text.

        :param debug_text:str -- add this string to the HUD

        Debug text always has FPS and Mouse.
        Each call to add_text() adds a line below that.
        """
        self.debug_text += f"\n{debug_text}"

    def render(self) -> None:
        color = self.game.color_debug_hud
        mpos = pygame.mouse.get_pos()
        self.text.update(f"FPS: {self.game.clock.get_fps():0.1f} | Window: {self.game.os_window.size} | Mouse: {mpos}"
                         f"{self.debug_text}")
        self.text.render(self.game.surfs['surf_os_window'], color)

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

    # >>> os_window = OsWindow(60*16, 60*9)
    # >>> os_window.toggle_fullscreen()
    # >>> os_window.handle_WINDOWRESIZED()

    After toggling full screen, user must do this:

        self.surfs['surf_os_window'] = pygame.display.set_mode(self.os_window.size, self.os_window.flags)

    Since that is in 'define_surfaces(OsWindow)', just call that function (and redefine self.surfs). The
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
        self._set_size_and_flags() # Set size and flags based on fullscreen or windowed

    def handle_WINDOWRESIZED(self, event) -> None:
        """Track size of resized OS window in self._windowed_size"""
        logger.debug(f"Window resized")
        self._windowed_size = (event.x, event.y)
        self._set_size_and_flags()

def define_settings() -> dict:
    settings = {}
    settings['setting_debug'] = True
    settings['setting_dark_mode'] = True
    settings['setting_gravity_on'] = True
    return settings

def define_surfaces(os_window:OsWindow) -> dict:
    """Return dictionary of pygame Surfaces.

    :param os_window:OsWindow -- defines OS Window 'size' and 'flags'
    :return dict -- {'surf_name': pygame.Surface, ...}

    Call this to create the initial window.

    Call this again when toggling fullscreen.

    Do not call this when resizing the window. Instead, Game calls self.update_surfaces().
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

def define_colors() -> dict:
    colors = {}
    colors['color_debug_hud_dark'] = Color(255,255,255)
    colors['color_debug_hud_light'] = Color(0,0,0)
    colors['color_graph_paper_bgnd_dark'] = Color(20,20,20)
    colors['color_graph_paper_bgnd_light'] = Color(180,200,255,255)
    colors['color_graph_paper_lines_dark'] = Color(100,100,255,50)
    colors['color_graph_paper_lines_light'] = Color(100,100,255,50)
    colors['color_pop_dark'] = Color(200,255,220)
    colors['color_pop_light'] = Color(50,30,0)
    colors['color_mouse_dot_dark'] = Color(200,50,50)
    colors['color_mouse_dot_light'] = Color(200,50,50)
    colors['color_mouse_vector_dark'] = Color(180,180,0)
    colors['color_mouse_vector_light'] = Color(50,30,0)
    colors['color_1_dark'] = Color(150,200,0)
    colors['color_2_dark'] = Color(200,0,0)
    colors['color_3_dark'] = Color(0,200,200)
    colors['color_1_light'] = Color(200,200,0)
    colors['color_2_light'] = Color(200,0,0)
    colors['color_3_light'] = Color(0,200,200)
    colors['color_player_1_final_dark'] = Color(220, 10, 200)
    colors['color_player_2_final_dark'] = Color(10, 220, 200)
    colors['color_player_3_final_dark'] = Color(200, 220, 10)
    colors['color_player_1_final_light'] = Color(220, 10, 100)
    colors['color_player_2_final_light'] = Color(10, 170, 120)
    colors['color_player_3_final_light'] = Color(200, 220, 10)
    colors['color_player_1_line_dark'] = Color(150, 50, 130)
    colors['color_player_2_line_dark'] = Color(50, 150, 130)
    colors['color_player_3_line_dark'] = Color(150, 170, 50)
    colors['color_player_1_line_light'] = Color(160, 40, 90)
    colors['color_player_2_line_light'] = Color(40, 130, 60)
    colors['color_player_3_line_light'] = Color(100, 140, 40)
    colors['color_hit_dark'] = Color(255,0,0)
    colors['color_hit_light'] = Color(255,0,0)
    return colors

@dataclass
class LineSeg:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

    @property
    def is_started(self) -> bool:
        """Return True if a line segment is started but not finished.

        Implements this truth table:

            start | end  | started
            ----- | ---  | -------
            None  | x    | False
            !None | None | True
            !None | !None| False
        """
        return (self.start != None) and (self.end == None)

    @property
    def midpoint(self) -> tuple:
        if not self.start: return (None, None)
        if not self.end: return (None, None)
        return (self.start[0] + self.vector[0]*0.5, self.start[1] + self.vector[1]*0.5)

class Grid:
    """Define a grid of lines.

    :param N:int -- number of grid lines (grid is NxN)
    """
    def __init__(self, game, N:int):
        self.game = game
        self.N = N
        self.scale = 1.0 # zoom
        self.reset()

    def reset(self) -> None:
        """Reset to initial transformation matrix: top-down view, grid centered.

        Define a 2x3 transformation matrix [a,b,e;c,d,f] to
        go from g (game grid) to p (pixels).
        """
        # Define 2x2 transform
        # Use a top-down view
        self.a = 1
        self.b = 0
        self.c = 0
        self.d = -1

        # Define offset vector (in pixel coordinates)
        # Place origin at center of game art
        ctr = (int(self.game.os_window.size[0]/2),
               int(self.game.os_window.size[1]/2))
        self.e = ctr[0]
        self.f = ctr[1]
        self.pan_origin = (self.e, self.f) # Stores initial (e,f) during panning
        self.pan_ref = (None, None) # Stores initial mpos during panning
        self.is_panning = False # Tracks whether mouse is panning

        self.scale = self.zoom_to_fit()

    def zoom_to_fit(self) -> float:
        # Get the size of the grid
        size_g = (self.N, self.N)
        
        # Get an unscaled 2x2 transformation matrix
        a,b,c,d = self.a, self.b, self.c, self.d

        # Transform the size to pixel coordinates (as if the size were a point)
        size_p = (a*size_g[0] + b*size_g[1], c*size_g[0] + d*size_g[1])

        # Add some margin
        margin = 10
        size_p = (abs(size_p[0]) + margin, abs(size_p[1]) + margin)

        scale_x = self.game.os_window.size[0]/size_p[0]
        scale_y = self.game.os_window.size[1]/size_p[1]

        return min(scale_x, scale_y)

    def scaled(self) -> tuple:
        return (self.a*self.scale, self.b*self.scale, self.c*self.scale, self.d*self.scale)

    @property
    def det(self) -> float:
        a,b,c,d = self.scaled()
        det = a*d-b*c
        if det == 0:
            # If det=0, Ainv will have div by 0, so just make det very small.
            return 0.0001
        else:
            return a*d-b*c

    def xfm_gp(self, point:tuple) -> tuple:
        """Transform point from game grid coordinates to OS Window pixel coordinates."""
        # Define 2x2 transform
        a,b,c,d = self.scaled()
        # Define offset vector (in pixel coordinates)
        e,f = (self.e, self.f)
        return (a*point[0] + b*point[1] + e, c*point[0] + d*point[1] + f)

    def xfm_pg(self, point:tuple, p:int=0) -> tuple:
        """Transform point from OS Window pixel coordinates to game grid coordinates.

        :param point:tuple -- (x,y) in pixel coordinates
        :param p:int -- decimal precision of returned coordinate (default: 0, return ints)
        :return tuple -- (x,y) in grid goordinates
        """
        # Define 2x2 transform
        a,b,c,d = self.scaled()
        # Define offset vector (in pixel coordinates)
        e,f = (self.e, self.f)
        # Calculate the determinant of the 2x2
        det = self.det
        g = ((   d/det)*point[0] + (-1*b/det)*point[1] + (b*f-d*e)/det,
             (-1*c/det)*point[0] + (   a/det)*point[1] + (c*e-a*f)/det)
        # Define precision
        if p==0:
            return (int(round(g[0])), int(round(g[1])))
        else:
            return (round(g[0],p), round(g[1],p))

    def zoom_in(self) -> None:
        self.scale *= 1.1

    def zoom_out(self) -> None:
        self.scale *= 0.9

    def pan(self, mpos:tuple) -> None:
        self.e = self.pan_origin[0] + (mpos[0] - self.pan_ref[0])
        self.f = self.pan_origin[1] + (mpos[1] - self.pan_ref[1])

    @property
    def hlinesegs(self) -> list:
        """Return list of horizontal line segments."""
        ### Put origin in center
        a = -1*int(self.N/2)
        b = int(self.N/2)
        cs = list(range(a,b+1))
        hls = []
        for c in cs:
            hls.append(LineSeg(start=(a,c), end=(b,c)))
        return hls

    @property
    def vlinesegs(self) -> list:
        ### Put origin in center
        a = -1*int(self.N/2)
        b = int(self.N/2)
        cs = list(range(a,b+1))
        vls = []
        for c in cs:
            vls.append(LineSeg(start=(c,a), end=(c,b)))
        return vls

    def draw(self, surf:pygame.Surface) -> None:
        color = self.game.color_graph_paper_lines
        linesegs = self.hlinesegs + self.vlinesegs
        for grid_line in linesegs:
            ### Anti-aliased:
            ### aaline(surface, color, start_pos, end_pos, blend=1) -> Rect
            ### Blend is 0 or 1. Both are anti-aliased.
            ### 1: (this is what you want) blend with the surface's existing pixel color
            ### 0: completely overwrite the pixel (as if blending with black)
            pygame.draw.aaline(surf, color, 
                    self.xfm_gp(grid_line.start),
                    self.xfm_gp(grid_line.end),
                    blend=1                             # 0 or 1
                    )

    @property
    def size(self) -> tuple:
        """Return grid size in pixels."""
        size_g = (1,1) # Size of one grid box in grid coordinates

        # Get the 2x2 transformation matrix
        a,b,c,d = self.scaled()

        # Transform the size to pixel coordinates (as if the size were a point)
        size_p = (a*size_g[0] + b*size_g[1], c*size_g[0] + d*size_g[1])

        return size_p

@dataclass
class Physics:
    """Just a struct for 'line_seg', 'force_vector', and 'final_seg'."""
    line_seg:LineSeg = LineSeg(None, None)              # Initial vector on this step
    force_vector:tuple = (None, None)                   # Force applied on this step
    final_seg:LineSeg = LineSeg(None, None)             # Final vector on this step

class GameHistory:
    """All the line segments drawn and force vectors applied so far.

    head:int -- a "play head" that points at a specific iteration in the game history
    size:int -- length of all lists in the history (all lists are always the same size)
    line_segs:list -- all line segments in the game history
    colors:list -- color of each line segment in the game history
    force_vectors:list -- all force vectors in the game history
    undo() -- move "head" backward in game history
    redo() -- move "head" forward in game history

    Start an empty Game History
    >>> gameHistory = GameHistory()
    >>> print(gameHistory.head)
    None

    Record three iterations of history
    >>> physics = Physics(LineSeg((1,2),(3,5)))
    >>> gameHistory.record(physics)
    >>> print(gameHistory.head)
    0
    >>> physics.line_seg = LineSeg((-1,-2),(3,5))
    >>> gameHistory.record(physics)
    >>> gameHistory.line_segs
    [LineSeg(start=(1, 2), end=(3, 5)), LineSeg(start=(-1, -2), end=(3, 5))]
    >>> print(gameHistory.head)
    1
    >>> gameHistory.record(physics)
    >>> print(gameHistory.head)
    2

    Undo all three, redo all three
    >>> gameHistory.undo()
    >>> print(gameHistory.head)
    1
    >>> gameHistory.undo()
    >>> print(gameHistory.head)
    0
    >>> gameHistory.undo()
    >>> print(gameHistory.head)
    None
    >>> gameHistory.redo()
    >>> print(gameHistory.head)
    0
    >>> gameHistory.redo()
    >>> print(gameHistory.head)
    1
    >>> gameHistory.redo()
    >>> print(gameHistory.head)
    2

    Redo again (play-head already at end) and play-head does not move.
    >>> gameHistory.redo()
    >>> print(gameHistory.head)
    2
    """
    def __init__(self):
        self.line_segs = []                             # Initialize: empty list of line segments
        self.line_colors = []                           # Initialize: empty list of line colors
        self.force_vectors = []                         # Initialize: empty list of force vectors
        self.final_segs = []                           # Initialize: empty list of sum vectors
        self.head = None                                # Initialize: head points at nothing
        self.size = 0                                   # Initialize: history size is 0

    def record(self, physics:Physics) -> None:
        if (self.head == None):
            # Prune the future before appending
            self.size = 0
            self.line_segs = []
            self.line_colors = []
            self.force_vectors = []
            self.final_segs = []
        elif (self.head < self.size-1):
            # Prune the future before appending
            self.size = self.head+1
            self.line_segs = self.line_segs[0:self.size]
            self.line_colors = self.line_colors[0:self.size]
            self.force_vectors = self.force_vectors[0:self.size]
            self.final_segs = self.final_segs[0:self.size]
        # Normal append
        self.line_segs.append(physics.line_seg)         # Add this line segment to the history
        self.force_vectors.append(physics.force_vector) # Add this force vector to the history
        self.final_segs.append(physics.final_seg)       # Add the final vector to the history
        self.size += 1                                  # History size increases by 1
        self.move_head_forward()

    def move_head_forward(self) -> None:
        if self.head == None:
            self.head = 0                               # Point head at first element
        else:
            self.head = min(self.size-1, self.head+1)   # Point head at next element

    def undo(self) -> None:
        match self.head:
            case None: pass
            case 0:
                self.head = None
            case _: self.head -= 1

    def redo(self) -> None:
        self.move_head_forward()

class Player:
    """Track a single player.

    :param game:Game -- Share game state: colors, and dark mode vs light mode
    :param n:int -- Player number (Player 1, Player 2, etc.)

    Attributes
    :attr color:pygame.Color -- color of the player's satellite and vectors
    :attr pos:tuple -- satellite (x,y) grid coordinate
    :attr state:str -- track player's game state
    :attr game_history:GameHistory -- track velocity vectors for this player
    """
    def __init__(self, game, n:int):
        self.game = game
        self.n = n
        self.reset()

    def reset(self) -> None:
        self.init_pos = (None,None)
        self.pos = (None,None)
        self.state = "Pick position"
        self.game_history = GameHistory()

    def update(self) -> None:
        match self.state:
            case "Pick position":
                mpos_g = self.game.grid.xfm_pg(pygame.mouse.get_pos())
                self.pos = mpos_g
                self.update_force_vector()
            case _:
                pass

    def update_force_vector(self) -> None:
        if self.game.settings['setting_gravity_on']:
            l = LineSeg(self.pos, (0,0))
            # Approximate l.vector with the closest of nine possible "normalized" vectors
            norm_vectors = [(0,0), (-1,0), (1,0), (0,1), (0,-1), (-1,-1), (-1,1), (1,1), (1,-1)]
            diff_vectors = [LineSeg((l.start[0]+n[0],l.start[1]+n[1]),l.end).vector for n in norm_vectors]
            diff_quads = [(d[0]**2 + d[1]**2 ) for d in diff_vectors]
            self.game.physics.force_vector = norm_vectors[diff_quads.index(min(diff_quads))]
        else:
            self.game.physics.force_vector = (0,0)

    @property
    def color_line(self) -> Color:
        if self.game.settings['setting_dark_mode']:
            return self.game.colors[f'color_player_{self.n}_line_dark']
        else:
            return self.game.colors[f'color_player_{self.n}_line_light']

    @property
    def color_final(self) -> Color:
        if self.game.settings['setting_dark_mode']:
            return self.game.colors[f'color_player_{self.n}_final_dark']
        else:
            return self.game.colors[f'color_player_{self.n}_final_light']


def get_next_player(active_player:int, num_players:int) -> int:
    """Return number of next player (player 1, player 2, etc.).

    Two players:
    >>> get_next_player(1, 2)
    2
    >>> get_next_player(2, 2)
    1

    Three players:
    >>> get_next_player(1, 3)
    2
    >>> get_next_player(2, 3)
    3
    >>> get_next_player(3, 3)
    1
    """
    next_player = (active_player+1) % num_players
    if next_player == 0: next_player = num_players
    return next_player

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module
        # pygame.mouse.set_visible(False)                 # Hide the OS mouse icon
        pygame.display.set_caption("Cannon game")

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        # os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((100*16, 100*9), is_fullscreen=False) # Track OS Window size and flags
        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces (including pygame.display)
        self.settings = define_settings()               # Dict of game settings
        self.colors = define_colors()                   # Dict of pygame Colors

        # Game Data
        self.grid = Grid(self, N=40)
        self.is_stepping = False
        self.physics = Physics()
        self.active_player = 1
        self.num_players = 2
        self.players = {}
        for i in range(self.num_players):
            n = i+1
            # self.players[f'player_{n}'] = Player(self.colors[f'color_player_{n}'])
            self.players[f'player_{n}'] = Player(self, n)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True: self.game_loop()

    def game_loop(self) -> None:
        # DebugHud
        if self.settings['setting_debug']: self.debug_hud = DebugHud(self)
        else: self.debug_hud = None

        if self.debug_hud: self.add_debug_text()

        # UI
        self.handle_ui_events()
        if self.is_stepping: self.step_physics()
        if self.grid.is_panning:
            self.grid.pan(pygame.mouse.get_pos())
        self.player.update() # Do physics in this update

        # Game art
        self.surfs['surf_game_art'].fill(self.color_graph_paper_bgnd)
        self.grid.draw(self.surfs['surf_game_art'])
        self.draw_mouse_as_snapped_dot(self.surfs['surf_game_art'])
        self.draw_mouse_vector(self.surfs['surf_game_art'])
        self.draw_game_history(self.surfs['surf_game_art'])
        self.draw_players(self.surfs['surf_game_art'])

        # Copy game art to OS window
        ### pygame.Surface.blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # Add overlays to OS window
        if self.debug_hud:
            self.debug_hud.render()

        # Draw to the actual OS window
        pygame.display.update()

        ### clock.tick(framerate=0) -> milliseconds
        self.clock.tick(60)

    def add_debug_text(self) -> None:
        # Track mouse position in game coordinates
        mpos_p = pygame.mouse.get_pos()             # Mouse in pixel coord sys
        mpos_g = self.grid.xfm_pg(mpos_p)           # Mouse in game coord sys
        self.debug_hud.add_text(f"Mouse (game): {mpos_g}")
        # Display gravity on/off
        if self.settings['setting_gravity_on']:
            self.debug_hud.add_text("Gravity on")
        else:
            self.debug_hud.add_text("Gravity off")
        self.debug_hud.add_text(f"Go player {self.active_player}")
        self.debug_hud.add_text(f"Player state: {self.player.state}")
        self.debug_hud.add_text(f"Physics line_seg: {self.physics.line_seg}")
        if 0:
            for player_n in self.players:
                player = self.players[player_n]
                self.debug_hud.add_text(f"Player {player_n} history head: {player.game_history.head}")
                vectors_str_list = [f"Player {player_n} Vector: " + str(l.vector) for l in player.game_history.line_segs]
                vectors_str = "\n".join(vectors_str_list)
                self.debug_hud.add_text(f"{vectors_str}")


    def handle_ui_events(self) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
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
                # Handle these events
                case pygame.QUIT: sys.exit()
                case pygame.WINDOWRESIZED:
                    self.os_window.handle_WINDOWRESIZED(event) # Update OS window size
                    self.update_surfaces() # Update surfaces affected by OS window size
                    logger.debug(f"game art: {self.surfs['surf_game_art'].get_size()}")
                    # Resize and recenter the grid
                    self.grid.reset()
                case pygame.KEYDOWN: self.handle_keydown(event)
                case pygame.KEYUP: self.handle_keyup(event)
                case pygame.MOUSEWHEEL:
                    ### {'flipped': False, 'x': 0, 'y': 1, 'precise_x': 0.0, 'precise_y': 1.0, 'touch': False, 'window': None}
                    match event.y:
                        case 1: self.grid.zoom_in()
                        case -1: self.grid.zoom_out()
                        case _: pass
                case pygame.MOUSEBUTTONDOWN:
                    match event.button:
                        case 1:
                            logger.debug("Left-click")
                            if kmod & pygame.KMOD_SHIFT:
                                # Let shift+left-click be my panning
                                # because I cannot do right-click-and-drag on the trackpad
                                self.handle_mousebuttondown_rightclick()
                            else:
                                self.handle_mousebuttondown_leftclick()
                        case 2:
                            logger.debug("Middle-click")
                            self.handle_mousebuttondown_middleclick()
                        case 3:
                            logger.debug("Right-click")
                            self.handle_mousebuttondown_rightclick()
                        case 4: logger.debug("Mousewheel y=+1")
                        case 5: logger.debug("Mousewheel y=-1")
                        case 6: logger.debug("Logitech G602 Thumb button 6")
                        case 7: logger.debug("Logitech G602 Thumb button 7")
                        case _: logger.debug(event)
                case pygame.MOUSEBUTTONUP:
                    match event.button:
                        case 1:
                            if kmod & pygame.KMOD_SHIFT:
                                logger.debug("Shift+Left mouse button released")
                                self.handle_mousebuttonup_rightclick()
                        case 2:
                            logger.debug("Middle mouse button released")
                            self.handle_mousebuttonup_middleclick()
                        case 3:
                            logger.debug("Right mouse button released")
                            self.handle_mousebuttonup_rightclick()
                        case _: logger.debug(event)
                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")
    def handle_keyup(self, event) -> None:
        komd = pygame.key.get_mods()
        match event.key:
            case pygame.K_n:
                self.is_stepping = False
    def handle_keydown(self, event) -> None:
        kmod = pygame.key.get_mods()                    # Which modifier keys are held
        match event.key:
            case pygame.K_q: sys.exit()                 # q - Quit
            case pygame.K_F11:
                self.os_window.toggle_fullscreen() # F11 - toggle fullscreen
                self.surfs = define_surfaces(self.os_window)
                logger.debug(f"game art: {self.surfs['surf_game_art'].get_size()}")
                # Resize and recenter the grid
                self.grid.reset()
            case pygame.K_F2:
                self.settings['setting_debug'] = not self.settings['setting_debug']
                logger.debug(f"Debug: {self.settings['setting_debug']}")
            case pygame.K_d: self.toggle_dark_mode()
            case pygame.K_r:
                if kmod & pygame.KMOD_SHIFT:
                    self.grid.reset()
                if kmod & pygame.KMOD_CTRL:
                    # Reset latest physics velocity vector
                    self.physics.line_seg = LineSeg(None,None)
                    # Reset game history for all players
                    for player_n in self.players:
                        player = self.players[player_n]
                        player.reset()
                else:
                    self.player.game_history.redo()
                    # self.game_history.redo()
            case pygame.K_ESCAPE: self.physics.line_seg = LineSeg(None,None)
            case pygame.K_F10: self.toggle_gravity()
            case pygame.K_u:
                if kmod & pygame.KMOD_SHIFT:
                    # Undo ALL history for the active player
                    self.player.game_history.head = None
                else:
                    # Undo one step/move for the active player
                    self.player.game_history.undo()
                head = self.player.game_history.head
                if head == None:
                    # Set position to initial position
                    self.player.pos = self.player.init_pos
                    # Set initial velocity to (0,0)
                    self.physics.line_seg.start = self.player.pos
                    self.physics.line_seg.end = self.player.pos
                    # Sum to find final_seg
                    l = self.physics.line_seg
                    self.player.update_force_vector()
                    v = self.physics.force_vector
                    self.physics.final_seg = LineSeg(l.start, (l.end[0]+v[0], l.end[1]+v[1]))
                    # Store line segment, force vector, and final segment in history.
                    self.player.game_history.record(self.physics)
                else:
                    self.player.pos = self.player.game_history.final_segs[head].end
            case pygame.K_TAB:
                self.set_next_player()
                # If next player hasn't been positioned yet, reset the latest physics line seg
                match self.player.state:
                    case "Pick position":
                        self.physics.line_seg = LineSeg(None,None)
                    case _:
                        pass
            case pygame.K_SPACE: self.step_physics()
            case pygame.K_n: self.is_stepping = True
            case _:
                logger.debug(f"{event.unicode}")

    def handle_mousebuttondown_leftclick(self) -> None:
        match self.player.state:
            case "Pick position":
                self.player.init_pos = self.player.pos
                self.player.state = "Step physics"
                # Set initial velocity to (0,0)
                self.physics.line_seg.start = self.player.pos
                self.physics.line_seg.end = self.player.pos
                # Sum to find final_seg
                l = self.physics.line_seg
                v = self.physics.force_vector
                self.physics.final_seg = LineSeg(l.start, (l.end[0]+v[0], l.end[1]+v[1]))
                # Store line segment, force vector, and final segment in history.
                self.player.game_history.record(self.physics)
            case _:
                pass

    def handle_mousebuttondown_middleclick(self) -> None:
        self.grid.pan_ref = pygame.mouse.get_pos()
        self.grid.is_panning = True

    def handle_mousebuttondown_rightclick(self) -> None:
        self.handle_mousebuttondown_middleclick()

    def handle_mousebuttonup_middleclick(self) -> None:
        self.grid.pan_ref = (None,None)
        self.grid.pan_origin = (self.grid.e, self.grid.f)
        self.grid.is_panning = False

    def handle_mousebuttonup_rightclick(self) -> None:
        self.handle_mousebuttonup_middleclick()

    def update_surfaces(self) -> None:
        """Call this after os_window handles WINDOWRESIZED event. See 'define_surfaces()'"""
        self.surfs['surf_game_art'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)
        self.surfs['surf_draw'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)

    def toggle_dark_mode(self) -> None:
        self.settings['setting_dark_mode'] = not self.settings['setting_dark_mode']

    def toggle_gravity(self) -> None:
        self.settings['setting_gravity_on'] = not self.settings['setting_gravity_on']
        if self.settings['setting_gravity_on']:
            self.physics.force_vector = (0,-1)
        else:
            self.physics.force_vector = (0,0)

    @property
    def player(self) -> Player:
        """'self.player' is shorthand for 'self.players[f'player_{self.active_player}']'."""
        return self.players[f'player_{self.active_player}']

    def set_next_player(self) -> None:
        """Set active player to next player."""
        self.active_player = get_next_player(self.active_player, self.num_players)

    def step_physics(self) -> None:
        """Step the physics simulation for the active player."""
        match self.player.state:
            case "Step physics":
                logger.debug(f"STEP player {self.active_player}")
                # To be in this state, it is guaranteed that the game history is not empty
                if self.player.game_history.head == None:
                    sys.exit("ERROR: Expected self.player.game_history.head != None")
                # Take the latest final segment
                head = self.player.game_history.head
                last_f = self.player.game_history.final_segs[head]
                # Make a next line segment
                next_l = LineSeg((last_f.start[0] + last_f.vector[0],
                                  last_f.start[1] + last_f.vector[1]),
                                 (last_f.end[0] + last_f.vector[0],
                                  last_f.end[1] + last_f.vector[1]))
                ### Apply a force vector
                self.player.update_force_vector()
                # Add force to prev velocity to get new vector
                v = self.physics.force_vector
                next_f = LineSeg(next_l.start, (next_l.end[0] + v[0], next_l.end[1] + v[1]))
                # Move player to new position
                self.player.pos = next_f.end
                # Record the next line segment
                self.physics.line_seg = next_l
                self.physics.final_seg = next_f
                self.player.game_history.record(self.physics)
            case _:
                pass

    def snap_to_grid(self, point:tuple) -> tuple:
        """Snap a point in pixel coordinates to the grid.

        point -- (x,y) in pixel coordinates

        Return point in pixel coordinates, but snapped to the grid.
        """
        # Xfm position from pixel to grid with precision=0 to snap to grid
        snapped_g = self.grid.xfm_pg(point, p=0)
        # Xfm back to pixels to get "snapped" pixel coordinates
        snapped_p = self.grid.xfm_gp(snapped_g)
        return snapped_p

    def draw_mouse_as_snapped_dot(self, surf:pygame.Surface) -> None:
        grid_size = min(abs(self.grid.size[0]), abs(self.grid.size[1]))
        if self.physics.line_seg.is_started:
            # Keep dot at start of line
            snapped = self.grid.xfm_gp(self.physics.line_seg.start)
            radius = grid_size/4
        else:
            # Move dot with mouse
            snapped = self.snap_to_grid(pygame.mouse.get_pos())
            radius = grid_size/3
        ### circle(surface, color, center, radius) -> Rect
        pygame.draw.circle(surf, self.player.color_final, snapped, radius)

    def draw_mouse_vector(self, surf:pygame.Surface) -> None:
        if self.physics.line_seg.is_started:
            ### Draw a vector from self.physics.line_seg.start to the grid-snapped mouse position
            # # Get the grid-snapped line segment in pixel coordinates
            # tail = self.grid.xfm_gp(self.physics.line_seg.start)
            # head = self.snap_to_grid(pygame.mouse.get_pos())
            tail = self.physics.line_seg.start
            head = self.grid.xfm_pg(self.snap_to_grid(pygame.mouse.get_pos()))
            l = LineSeg(start=tail, end=head)
            # Draw line segment as a vector (a line with an arrow head)
            self.draw_line_as_vector(surf, l, self.player.color_line)
            # Draw x and y components
            self.draw_xy_components(surf, l, self.color_pop)

    def draw_game_history(self, surf:pygame.Surface) -> None:
        """Draw all line segments and forces in the game history as vectors."""
        for player_n in self.players:
            player = self.players[player_n]
            if player.game_history.head == None:
                pass
            else:
                for i in range(player.game_history.head+1):
                    ### Draw the player's velocity vector
                    l = player.game_history.line_segs[i]
                    self.draw_line_as_vector(surf, l, player.color_line)
                    ### Draw the force vector
                    v = player.game_history.force_vectors[i]
                    # Define line segment 'v_l': translate vector 'v' to the end of line segment 'l'
                    v_l = LineSeg(
                            (l.end[0],          l.end[1]),
                            (l.end[0] + v[0],   l.end[1] + v[1]))
                    self.draw_line_as_vector(surf, v_l, self.color_mouse_vector)
                    ### Draw the final vector
                    f = player.game_history.final_segs[i]
                    self.draw_line_as_vector(surf, f, player.color_final)


    def draw_players(self, surf:pygame.Surface) -> None:
        """Draw player positions."""
        for player_n in self.players:
            player = self.players[player_n]
            match player.state:
                case "Pick position":
                    pass
                case _:
                    # Draw player
                    grid_size = min(abs(self.grid.size[0]), abs(self.grid.size[1]))
                    radius = grid_size*4/5
                    center = self.grid.xfm_gp(player.pos)
                    width = max(1, int(radius/10))
                    ### circle(surface, color, center, radius) -> Rect
                    pygame.draw.circle(surf, player.color_final, center, radius, width)
                    radius = radius/2
                    width = max(1, int(width/2))
                    pygame.draw.circle(surf, player.color_final, center, radius, width)

    def draw_line_as_vector(self, surf:pygame.Surface, l:LineSeg, color:Color) -> None:
        """Draw line segment as a vector: a line with an arrow head.

        surf -- draw on this pygame.Surface
        l -- LineSeg(start=tail, end=head) in game coordinates
        color -- pygame.Color(R,G,B)

        Draw an arrow head:
          An isosceles triangle with its tip at the vector head.

        Draw an arrow shaft:
          A thick line from the vector tail to the base of the arrow head.
        """
        # Convert to pixel coordinates
        l = LineSeg(self.grid.xfm_gp(l.start), self.grid.xfm_gp(l.end))
        # Get the vector from the line segment
        v = l.vector
        # Get the unit vector
        v_dist = math.sqrt(v[0]**2 + v[1]**2)
        # Use 'if/else' to avoid div by 0 (in case vector has length 0)
        if v_dist == 0:
            unit_v = (0,0)
        else:
            unit_v = (v[0]/v_dist, v[1]/v_dist)
        # Get the perpendicular unit vector
        unit_vp = (-1*unit_v[1], unit_v[0])
        # Set the arrow head size relative to the grid size
        grid_size = min(abs(self.grid.size[0]), abs(self.grid.size[1]))
        a = grid_size*2/3 # a: arrow head triangle height is 2/3 the length of a grid box
        b = grid_size*1/5 # a: arrow head triangle base is 1/5 the length of a grid box
        # Define a vector that is the arrow head from base to tip
        arrow_head_v = (a*unit_v[0], a*unit_v[1])
        # Fine the pixel coordinate of the base of the arrow head triangle
        base = (l.end[0] - arrow_head_v[0], l.end[1] - arrow_head_v[1])
        # Describe the arrow head as a list of three points
        arrow_head_points = [ l.end,
                              (base[0] - b*unit_vp[0], base[1] - b*unit_vp[1]),
                              (base[0] + b*unit_vp[0], base[1] + b*unit_vp[1])
                             ]
        # Draw the arrow head
        pygame.draw.polygon(surf, color, arrow_head_points)
        # Draw the arrow shaft
        width = max(1, int(grid_size/6)) # Scale line width to grid size
        # Extend the arrow shaft into the harrow head to avoid gaps between pygame line and arrow head 
        base = (l.end[0] - arrow_head_v[0]/2, l.end[1] - arrow_head_v[1]/2)
        pygame.draw.line(surf, color, l.start, base, width)

    def draw_xy_components(self, surf:pygame.Surface, l:LineSeg, color:Color) -> None:
        """Draw x and y components of the line segment.

        surf:pygame.Surface -- Surface to draw on
        l:LineSeg -- Line segment in game coordinates
        color:Color -- Color of lines and text
        """
        start = self.grid.xfm_gp(l.start)
        end = self.grid.xfm_gp(l.end)

        # Draw x,y lines
        xline = LineSeg(start, (end[0], start[1]))
        yline = LineSeg((end[0], start[1]), end)

        pygame.draw.line(surf, color, xline.start, xline.end)
        pygame.draw.line(surf, color, yline.start, yline.end)

        # Draw ticks on x,y lines
        grid_size = min(abs(self.grid.size[0]), abs(self.grid.size[1]))
        tick_len = grid_size/6
        if l.vector[1] == 0:
            # Draw one more tick if the vector is horizontal
            xstop = abs(l.vector[0])+1
        else:
            xstop = abs(l.vector[0])
        for i in range(1, xstop):
            x = l.start[0] + signum(l.vector[0])*i
            y = l.start[1]
            tick_p = self.grid.xfm_gp((x,y))
            tick = LineSeg((tick_p[0], tick_p[1]-tick_len),
                           (tick_p[0], tick_p[1]+tick_len))
            pygame.draw.line(surf, color, tick.start, tick.end, width=max(1,int(grid_size/20)))
        for i in range(1, abs(l.vector[1])):
            x = l.end[0]
            y = l.end[1] - signum(l.vector[1])*i
            tick_p = self.grid.xfm_gp((x,y))
            tick = LineSeg((tick_p[0]-tick_len, tick_p[1]),
                           (tick_p[0]+tick_len, tick_p[1]))
            pygame.draw.line(surf, color, tick.start, tick.end, width=max(1,int(grid_size/20)))

        if l.vector[0] != 0:
            # Label x component
            xlabel = Text((0,0), font_size=max(15,int(grid_size)), sys_font="Roboto Mono")
            xlabel.update(f"{l.vector[0]}")
            xlabel_w = xlabel.font.size(xlabel.text_lines[0])[0]
            xlabel_h = xlabel.font.get_linesize()*len(xlabel.text_lines)
            if l.vector[1] < 0:
                # If y-component is NEGATIVE, align center BOTTOM of label to midpoint of the x-component
                xlabel.pos = (xline.midpoint[0] - xlabel_w/2, xline.midpoint[1] - xlabel_h)
            else:
                # If y-component is POSITIVE, align center TOP of label to midpoint of the x-component
                xlabel.pos = (xline.midpoint[0] - xlabel_w/2, xline.midpoint[1])
            xlabel.render(surf, color)
        if l.vector[1] != 0:
            # Label y component
            ylabel = Text((0,0), font_size=max(15,int(grid_size)), sys_font="Roboto Mono")
            ylabel.update(f"{l.vector[1]}")
            ylabel_w = ylabel.font.size(ylabel.text_lines[0])[0]
            ylabel_h = ylabel.font.get_linesize()*len(ylabel.text_lines)
            if l.vector[0] < 0:
                # If x-component is NEGATIVE, align center LEFT of label to midpoint of the y-component
                ylabel.pos = (yline.midpoint[0] - ylabel_w - ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_h/2)
            else:
                # If x-component is POSITIVE, align center RIGHT of label to midpoint of the y-component
                ylabel.pos = (yline.midpoint[0] + ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_h/2)
            ylabel.render(surf, color)

    @property
    def color_debug_hud(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_debug_hud_dark']
        else:
            return self.colors['color_debug_hud_light']

    @property
    def color_graph_paper_bgnd(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_graph_paper_bgnd_dark']
        else:
            return self.colors['color_graph_paper_bgnd_light']

    @property
    def color_graph_paper_lines(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_graph_paper_lines_dark']
        else:
            return self.colors['color_graph_paper_lines_light']

    @property
    def color_pop(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_pop_dark']
        else:
            return self.colors['color_pop_light']

    @property
    def color_hit(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_hit_dark']
        else:
            return self.colors['color_hit_light']

    @property
    def color_mouse_dot(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_mouse_dot_dark']
        else:
            return self.colors['color_mouse_dot_light']

    @property
    def color_mouse_vector(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_mouse_vector_dark']
        else:
            return self.colors['color_mouse_vector_light']

    @property
    def color_1(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_1_dark']
        else:
            return self.colors['color_1_light']

    @property
    def color_2(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_2_dark']
        else:
            return self.colors['color_2_light']

    @property
    def color_3(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_3_dark']
        else:
            return self.colors['color_3_light']


if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)
    logger = setup_logging()
    Game().run()
