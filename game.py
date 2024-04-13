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
[x] Press escape to stop drawing line segment
[x] Second mouse click stores the line segment
    [x] Determine line segment drawing state by checking if self.lineSeg.start == None
    [x] Store drawn line segments in list self.lineSegs
    [x] A new line segment starts
[x] Store drawn line segments -- IN GRID SPACE, NOT PIXEL SPACE!
[x] Draw the stored line segments!
[x] Undo/redo last drawn line segment
    [x] Undo/redo navigate the history/future of drawn line segments
    [x] If a new line segment is drawn after some number of undos, the future is erased
    * To implement:
        * Replace simple "list.append()" with a record(lineSeg, lineSegs)
        * record(lineSeg, lineSegs) is a simple append if the present is pointing at the end of the lineSegs history
        * if the present is in the middle of the history, record deletes the future portion of the history before appending
[x] Show vector x and y components of the line segment being drawn
[x] Display an arrow head at the end of the line segment being drawn (will use this later for visually representing vectors)
[ ] Display number label for x and y components of the line segment being drawn
[ ] I don't like the similarity in these names: geometry.Line and LineSeg
"""

import math
import sys
from pathlib import Path
import atexit
import logging
from dataclasses import dataclass
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color, Rect
from libs.utils import setup_logging, Window, scale_data, Text, DebugHud, signum
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
class LineSeg:
    """Line segment stored in grid coordinates.

    start -- line segment start point in grid coordinates
    end -- line segment end point in grid coordinates

    Make a line segment:
    >>> lineSeg = LineSeg((1,2),(3,5))
    >>> lineSeg
    LineSeg(start=(1, 2), end=(3, 5))

    Get the vector that goes from 'start' to 'end':
    >>> lineSeg.vector
    (2, 3)

    Check if the line segment is started.

    A new line segment is not started:
    >>> lineSeg = LineSeg()
    >>> lineSeg.is_started
    False

    Start the line segment. Now it is started:
    >>> lineSeg.start = (0,0)
    >>> lineSeg.is_started
    True

    End the line segment. It is finished (not started):
    >>> lineSeg.end = (0,0)
    >>> lineSeg.is_started
    False
    """
    start:tuple=None
    end:tuple=None

    @property
    def vector(self) -> tuple:
        if not self.start: return (None,None)
        if not self.end: return (None,None)
        return (self.end[0]-self.start[0], self.end[1]-self.start[1])

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

class LineSegs:
    """All the line segments drawn so far.

    history:list -- all line segments in the history
    head:int -- a "play head" that points at a line segment in the history
    undo() -- move "head" backward in history
    redo() -- move "head" forward in history

    >>> lineSegs = LineSegs()
    >>> print(lineSegs.head)
    None
    >>> lineSegs.record(LineSeg((1,2),(3,5)))
    >>> print(lineSegs.head)
    0
    >>> lineSegs.record(LineSeg((-1,-2),(3,5)))
    >>> lineSegs.history
    [LineSeg(start=(1, 2), end=(3, 5)), LineSeg(start=(-1, -2), end=(3, 5))]
    >>> print(lineSegs.head)
    1
    >>> lineSegs.record(LineSeg((-1,-2),(3,5)))
    >>> print(lineSegs.head)
    2
    >>> lineSegs.undo()
    >>> print(lineSegs.head)
    1
    >>> lineSegs.undo()
    >>> print(lineSegs.head)
    0
    >>> lineSegs.undo()
    >>> print(lineSegs.head)
    None
    >>> lineSegs.redo()
    >>> print(lineSegs.head)
    0
    >>> lineSegs.redo()
    >>> print(lineSegs.head)
    1
    >>> lineSegs.redo()
    >>> print(lineSegs.head)
    2
    >>> lineSegs.redo()
    >>> print(lineSegs.head)
    2
    """
    def __init__(self):
        self.history = []                               # Initialize: empty list of line segments
        self.head = None                                # Initialize: head points at nothing
        self.size = 0                                   # Initialize: history size is 0

    def record(self, l:LineSeg) -> None:
        if (self.head == None):
            # Prune the future before appending
            self.size = 0
            self.history = []
        elif (self.head < self.size-1):
            # Prune the future before appending
            self.size = self.head+1
            self.history = self.history[0:self.size]
        # Normal append
        self.history.append(l)                          # Add this line segment to the history
        self.size += 1                                  # History size increases by 1
        self.move_head_forward()

    def move_head_forward(self) -> None:
        if self.head == None:
            self.head = 0                               # Point head at first element
        else:
            self.head = min(self.size-1, self.head+1)     # Point head at next element

    def undo(self) -> None:
        match self.head:
            case None: pass
            case 0: self.head = None
            case _: self.head -= 1

    def redo(self) -> None:
        self.move_head_forward()

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
        self.colors['color_line_started_light'] = Color(255,255,0,120)
        self.colors['color_line_started_dark'] = Color(50,30,0,120)

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
        self.grid_size = self.graphPaper.get_box_size(self.surfs['surf_game_art'])
        self.lineSeg = LineSeg()                        # An empty line segment
        self.lineSegs = LineSegs()                      # An empty history of line segments
        # self.lineSegs = []                              # An empty list of line segments
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
                # Clear the active line segment.
                self.lineSeg = LineSeg()
            case pygame.K_u:
                self.lineSegs.undo()
            case pygame.K_r:
                self.lineSegs.redo()

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
                    if self.lineSeg.is_started:
                        # Ending a line segment.
                        # This mouse click is the end point.
                        self.lineSeg.end = self.mouse.coords['grid']
                        # Store this line segment.
                        self.lineSegs.record(self.lineSeg)
                        # Reset the active line segment
                        self.lineSeg = LineSeg()
                        CONTINUE_DRAWING = True
                        if CONTINUE_DRAWING:
                            # Record this as the start
                            self.lineSeg.start = self.mouse.coords['grid']
                    else:
                        # Starting a line segment.
                        # This mouse click is the start point.
                        self.lineSeg.start = self.mouse.coords['grid']
                case pygame.MOUSEBUTTONUP:
                    # logger.debug("LEFT CLICK RELEASE")
                    pass
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def draw_started_lineSeg(self) -> None:
        # TODO: refactor this function

        # Define the started line segment
        lineSeg = LineSeg(start=self.lineSeg.start, end=self.mouse.coords['grid'])
        # TODO: use lineSeg.vector to orient the vector arrow head

        # Convert lineSeg.start grid coordinates to pixel coordinates
        pix_start = self.graphPaper.xfm_to_pix(lineSeg.start, self.surfs['surf_game_art'])

        # Create a line from the start to the current mouse position
        started_line = Line(pix_start, self.mouse.coords['pixel'])

        # Set dot radii based on the grid_size
        big_radius = int(0.5*0.5*self.grid_size[0])
        small_radius = int(0.5*big_radius)


        ### Draw x and y components
        pix_end = self.mouse.coords['pixel']
        # Set color of x and y components
        if self.graphPaper.show_paper:
            line_color = self.colors['color_debug_hud_dark']
        else:
            line_color = self.colors['color_debug_hud_light']
        # Draw x component
        xline = Line(started_line.start, (started_line.end[0],started_line.start[1]))
        self.render_line(xline, line_color, width=1)
        # Label x component
        xlabel = Text((0,0), font_size=max(self.grid_size[0], self.grid_size[1]), sys_font="Roboto Mono")
        xlabel.update(f"{lineSeg.vector[0]}")
        xlabel_width = xlabel.font.size(xlabel.text_lines[0])[0]
        xlabel_height = xlabel.font.get_linesize()*len(xlabel.text_lines)
        if lineSeg.vector[1] < 0:
            # If y-component is NEGATIVE, align center BOTTOM of label to midpoint of the x-component
            xlabel.pos = (xline.midpoint[0] - xlabel_width/2, xline.midpoint[1] - xlabel_height)
        else:
            # If y-component is POSITIVE, align center TOP of label to midpoint of the x-component
            xlabel.pos = (xline.midpoint[0] - xlabel_width/2, xline.midpoint[1])
        xlabel.render(self.surfs['surf_game_art'], line_color)
        # Draw y component
        yline = Line((started_line.end[0],started_line.start[1]), started_line.end)
        self.render_line(yline, line_color, width=1)
        # Label y component
        ylabel = Text((0,0), font_size=max(self.grid_size[0], self.grid_size[1]), sys_font="Roboto Mono")
        ylabel.update(f"{lineSeg.vector[1]}")
        ylabel_height = ylabel.font.get_linesize()*len(ylabel.text_lines)
        ylabel_width = ylabel.font.size(ylabel.text_lines[0])[0]
        if lineSeg.vector[0] < 0:
            # If x-component is NEGATIVE, put y-label LEFT of the line
            ylabel.pos = (yline.midpoint[0] - ylabel_width - ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_height/2)
        else:
            # If x-component is POSITIVE, put y-label RIGHT of the line
            ylabel.pos = (yline.midpoint[0] + ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_height/2)
        # Align center left of label to midpoint of the y-component
        ylabel.render(self.surfs['surf_game_art'], line_color)

        ### Draw little tick marks along these lines to indicate measuring (like a ruler has tick marks)
        # Draw a tick mark at every grid intersection along the x-component
        lineSeg = LineSeg(self.lineSeg.start, self.mouse.coords['grid'])
        tick_len = small_radius
        for i in range(abs(lineSeg.vector[0])):
            x = lineSeg.start[0] + signum(lineSeg.vector[0])*i
            y = lineSeg.start[1]
            pix_start = xfm_grid_to_pix((x,y), self.graphPaper, self.surfs['surf_game_art'])
            line = Line((pix_start[0],pix_start[1]-tick_len),
                        (pix_start[0],pix_start[1]+tick_len))
            self.render_line(line, line_color, width=1)
        # Draw a tick mark at every grid intersection along the y-component
        for i in range(abs(lineSeg.vector[1])):
            x = lineSeg.end[0]
            y = lineSeg.end[1] - signum(lineSeg.vector[1])*i
            pix_start = xfm_grid_to_pix((x,y), self.graphPaper, self.surfs['surf_game_art'])
            line = Line((pix_start[0]-tick_len,pix_start[1]),
                        (pix_start[0]+tick_len,pix_start[1]))
            self.render_line(line, line_color, width=1)

        # Set color of the line drawn with the mouse
        if self.graphPaper.show_paper:
            line_color = self.colors['color_line_started_dark']
        else:
            line_color = self.colors['color_line_started_light']


        DRAW_AS_VECTOR = True
        if DRAW_AS_VECTOR:
            # Find the minimum dimension of one grid box and scale it by s
            s = 2/3
            a = int(round(min(self.grid_size[0], self.grid_size[1])*s))
            # Use 'a' to calculate a scaling factor for the started_line.vector
            if started_line.start != started_line.end:
                k = math.sqrt((a**2)/(started_line.vector[0]**2 + started_line.vector[1]**2))
            else:
                # If the vector is zero, scaling factor is 0 (avoid divide by zero)
                k = 0
            # Start the arrow head back from the end of the line by a distance of 1/2 the min grid dimension
            arrow_head_base = (started_line.end[0] - k*started_line.vector[0], started_line.end[1] - k*started_line.vector[1])
            # Get the perpendicular vector
            pvec = (-1*started_line.vector[1], started_line.vector[0])
            # Form the arrow head with the tip at the end of the line and the
            # other two points of the triangle calc from pvec and arrow_head_base
            arrow_head_points = [ started_line.end,     # Arrow head tip
                                  (arrow_head_base[0] - k*pvec[0]/2, arrow_head_base[1] - k*pvec[1]/2),
                                  (arrow_head_base[0] + k*pvec[0]/2, arrow_head_base[1] + k*pvec[1]/2)
                                  ]
            arrow_rect = pygame.draw.polygon(self.surfs['surf_draw'], line_color, arrow_head_points)
            self.render_rect_area(arrow_rect)
            # Draw the line segment
            arrow_shaft = Line(started_line.start, arrow_head_base)
            self.render_line(arrow_shaft, line_color, width=5)
        else:
            # Draw the line segment
            self.render_line(started_line, line_color, width=5)
            # Draw a dot at the grid intersection closest to the mouse
            self.mouse.render_snap_dot(radius=big_radius, color=Color(0,200,255,150))

        # Draw a dot at the start of the vector
        self.render_dot(started_line.start, radius=small_radius, color=Color(255,0,0,150))

    def game_loop(self) -> None:

        # Get user input
        self.handle_ui_events()
        self.mouse.update()

        # Create the debug HUD
        self.debugHud = DebugHud(self)


        # Clear screen
        # self.surfs['surf_os_window'].fill(self.colors['color_os_window_bgnd'])
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # Fill game art area with graph paper
        self.graphPaper.render(self.surfs['surf_game_art'])

        # Find the size of one grid box
        self.grid_size = self.graphPaper.get_box_size(self.surfs['surf_game_art'])

        if self.lineSeg.start:
            # Draw a line from start to the dot if I started a line segment
            self.draw_started_lineSeg()
        else:
            # Set dot radii based on the grid_size
            big_radius = int(0.5*0.5*self.grid_size[0])
            # Draw a dot at the grid intersection closest to the mouse
            self.mouse.render_snap_dot(radius=big_radius, color=Color(255,0,0,150))

        # Draw the vectors
        for i,l in enumerate(self.lineSegs.history):
            # Draw nothing if play-head points to nothing
            if self.lineSegs.head == None: break
            # Only draw lines up until the play-head
            if i > self.lineSegs.head: break
            # Set color of the lines in the history
            if self.graphPaper.show_paper:
                # Brown if paper is visible
                line_color = Color(60,30,0,120)
            else:
                # Yellow if paper is invisible
                line_color = Color(210,200,0,120)
            # Convert this line segment to a line in pixel coordinates
            pix_start = xfm_grid_to_pix(l.start, self.graphPaper, self.surfs['surf_game_art'])
            pix_end = xfm_grid_to_pix(l.end, self.graphPaper, self.surfs['surf_game_art'])
            line = Line(pix_start, pix_end)
            # Draw the line segment
            self.render_line(line, line_color, width=5)


        # Draw game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # List vectors as strings as they are added by the user:
        vectors_str_list = ["Vector: " + str(l.vector) for l in self.lineSegs.history]
        vectors_str = "\n".join(vectors_str_list)
        self.debugHud.add_text(f"Mouse: {self.mouse.coords['grid']} | lineSegs.head: {self.lineSegs.head}")
        self.debugHud.add_text(f"N: {self.graphPaper.N}, grid_size: {self.grid_size} pixels")
        self.debugHud.add_text(f"{vectors_str}")

        if self.graphPaper.show_paper:
            self.debugHud.render(self.colors['color_debug_hud_dark'])
        else:
            self.debugHud.render(self.colors['color_debug_hud_light'])

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
        # Clean up just this rect area on the temporary surface (otherwise bits of line get highlighted)
        self.surfs['surf_draw'].fill(self.colors['color_clear'], rect=rect)

    def render_line(self, line:Line, color:Color, width:int) -> None:
        """Render a Line on the game art with pygame.draw.line().

        line -- Line(start, end)
        color -- pygame.Color(R,G,B,A)
        width -- line thickness in pixels
        """
        ### line(surface, color, start, end, width=1) -> Rect
        line_rect = pygame.draw.line(self.surfs['surf_draw'], color, line.start, line.end, width)
        self.render_rect_area(line_rect)

    def render_line_as_vector(self, line:Line, color:Color, width:int) -> None:
        """Render a Line on the game art with pygame.draw.line().

        line -- Line(start, end)
        color -- pygame.Color(R,G,B,A)
        width -- line thickness in pixels
        """
        # Set arrow head based on the grid_size
        a = int(0.5*0.5*self.grid_size[0])

        ### Draw Arrow Head
        ### polygon(surface, color, points, width=0) -> Rect
        p1 = (line.end[0]-a,line.end[1]-a)
        p2 = (line.end[0]-a,line.end[1]+a)
        p3 = (line.end[0],line.end[1])
        # TODO: rotate arrow head to point in direction of vector
        arrow_rect = pygame.draw.polygon(self.surfs['surf_draw'], color, [p1,p2,p3,p1])
        self.render_rect_area(arrow_rect)

        ### Draw Line
        ### line(surface, color, start, end, width=1) -> Rect
        # TODO: end line where arrow head starts
        line_rect = pygame.draw.line(self.surfs['surf_draw'], color, line.start, line.end, width)
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
