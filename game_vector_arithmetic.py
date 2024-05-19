#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Graph paper on my screen for demonstrating vectors and addition.

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
[ ] Click to draw a vector
"""

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

    >>> os_window = OsWindow(60*16, 60*9)
    >>> os_window.toggle_fullscreen()
    >>> os_window.handle_WINDOWRESIZED()

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
    colors['color_green_dark'] = Color(200,255,220)
    colors['color_brown_light'] = Color(50,30,0)
    colors['color_mouse_dot_dark'] = Color(200,50,50)
    colors['color_mouse_dot_light'] = Color(200,50,50)
    return colors

class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module
        pygame.mouse.set_visible(False)                 # Hide the OS mouse icon
        pygame.display.set_caption("Vector arithmetic")

        os.environ["PYGAME_BLEND_ALPHA_SDL2"] = "1"     # Use SDL2 alpha blending
        # os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,0"   # Position window in upper right

        self.os_window = OsWindow((60*16, 60*9), is_fullscreen=False) # Track OS Window size and flags
        self.surfs = define_surfaces(self.os_window)    # Dict of Pygame Surfaces (including pygame.display)
        self.settings = define_settings()               # Dict of game settings
        self.colors = define_colors()                   # Dict of pygame Colors

        # Game Data
        self.grid = Grid(self, N=40)

        # FPS
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True: self.game_loop()

    def game_loop(self) -> None:
        # DebugHud
        if self.settings['setting_debug']: self.debug_hud = DebugHud(self)
        else: self.debug_hud = None

        # Track mouse position in game coordinates
        if self.debug_hud:
            mpos_p = pygame.mouse.get_pos()             # Mouse in pixel coord sys
            mpos_g = self.grid.xfm_pg(mpos_p)           # Mouse in game coord sys
            self.debug_hud.add_text(f"Mouse (game): {mpos_g}")

        # UI
        self.handle_ui_events()

        # Game art
        self.surfs['surf_game_art'].fill(self.color_graph_paper_bgnd)
        self.grid.draw(self.surfs['surf_game_art'])
        self.draw_mouse_as_snapped_dot(self.surfs['surf_game_art'])


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
                    # Resize and recenter the grid
                    self.grid.reset()
                case pygame.KEYDOWN: self.handle_keydown(event)
                case pygame.MOUSEWHEEL:
                    ### {'flipped': False, 'x': 0, 'y': 1, 'precise_x': 0.0, 'precise_y': 1.0, 'touch': False, 'window': None}
                    match event.y:
                        case 1: self.grid.zoom_in()
                        case -1: self.grid.zoom_out()
                        case _: pass
                # Log any other events
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

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
            case pygame.K_r: self.grid.reset()

            case _:
                logger.debug(f"{event.unicode}")

    def update_surfaces(self) -> None:
        """Call this after os_window handles WINDOWRESIZED event. See 'define_surfaces()'"""
        self.surfs['surf_game_art'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)
        self.surfs['surf_draw'] = pygame.Surface(self.os_window.size, flags=pygame.SRCALPHA)

    def toggle_dark_mode(self) -> None:
        self.settings['setting_dark_mode'] = not self.settings['setting_dark_mode']

    def draw_mouse_as_snapped_dot(self, surf:pygame.Surface) -> None:
        mpos = pygame.mouse.get_pos()
        grid_size = min(abs(self.grid.size[0]), abs(self.grid.size[1]))
        radius = grid_size/3
        # Xfm mouse position from pixel to grid with precision=0 to snap to grid
        mpos_snapped_g = self.grid.xfm_pg(mpos, p=0)
        # Xfm back to pixels to get "snapped" pixel coordinates
        mpos_snapped_p = self.grid.xfm_gp(mpos_snapped_g)
        ### circle(surface, color, center, radius) -> Rect
        pygame.draw.circle(surf, self.color_mouse_dot, mpos_snapped_p, radius)

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
    def color_mouse_dot(self) -> Color:
        if self.settings['setting_dark_mode']:
            return self.colors['color_mouse_dot_dark']
        else:
            return self.colors['color_mouse_dot_light']

@dataclass
class LineSeg:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

class Grid:
    """Define a grid of lines.

    :param N:int -- number of grid lines (grid is NxN)
    """
    def __init__(self, game:Game, N:int):
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
        self.a = 20
        self.b = 0
        self.c = 0
        self.d = -20

        # Define offset vector (in pixel coordinates)
        # Place origin at center of game art
        ctr = (int(self.game.os_window.size[0]/2),
               int(self.game.os_window.size[1]/2))
        self.e = ctr[0]
        self.f = ctr[1]

        self.scale = self.zoom_to_fit()

    def zoom_to_fit(self) -> float:
        # Get the size of the grid
        size_g = (self.N, self.N)
        
        # Get an unscaled 2x2 transformation matrix
        a,b,c,d = self.a, self.b, self.c, self.d

        # Transform the size to pixel coordinates (as if the size were a point)
        size_p = (a*size_g[0] + b*size_g[1], c*size_g[0] + d*size_g[1])

        # Add some margin
        size_p = (abs(size_p[0]) + 20, abs(size_p[1]) + 20)

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

if __name__ == '__main__':
    print(f"Run {Path(__file__).name}")
    atexit.register(shutdown)
    logger = setup_logging()
    Game().run()
