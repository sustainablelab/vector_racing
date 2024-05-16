#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Shoot cannon balls.

[x] Start game with a lineSeg already started (started at location of cannon)
[x] Ignore additional mouse clicks once a single lineSeg exists
    * This lineSeg is the initial velocity vector.
[x] Store this first vector as initial velocity
[x] Keep showing the x and y component of initial velocity vector
[x] 'Space' draws next iteration
[x] Draw all lineSegs in lineSegs.history as vectors (lines with arrow heads)
[x] 'F10' toggles gravity on/off
[x] Draw force vector (gravity)
    - Ways I might do this:
        1. Store force vector along with final lineSeg at each step
        2. Store force vector along with initial lineSeg at each step (then compute final lineSeg as needed)
        3. Store a separate history of force vectors and use playhead to scrub all histories
    - I like method 3 the most.
    - So, really 'LineSegs' is not line segments, it is History. And
      'self.history' is not history, it is just line segments.
    - Restructure as 'History' with attributes 'line_segments', 'head', and 'size'
    [x] Change class 'LineSegs' to 'GameHistory'
    [x] Change attribute 'LineSegs.history' to 'GameHistory.line_segments'
    [x] Add attribute 'GameHistory.force_vectors'
    [x] Record force_vectors
[x] Make a 'Shift+R' to restart
[ ] Make a 'Help'
[x] Undo past initial velocity vector should put me back to drawing an initial velocity vector
[ ] Make a future mode: instead of pressing space, toggle on show_future to see the path: drag out the mouse until the path hits the target!
[ ] Let vectors go off screen!
    - Fix rendering "bug" that is clamping them to the top of the screen.
    - Fix rendering "bug" that is clamping them to the side of the screen.
    - It's as if I accidentally made some amazing collision detection....
[ ] Randomize cannon location
[ ] Show location of target
[ ] Randomize target location
[ ] Maintain 'square' aspect ratio of grid boxes
"""

import math
import sys
from pathlib import Path
import atexit
import logging
import json
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

    @property
    def is_finished(self) -> bool:
        """Return True if a line segment is finished.

        Implements this truth table:

            start | end  | started
            ----- | ---  | -------
            None  | None | False
            None  | !None| False
            !None | None | False
            !None | !None| True
        """
        return (self.start != None) and (self.end != None)

class GameHistory:
    """All the line segments drawn and force vectors applied so far.

    head:int -- a "play head" that points at a specific iteration in the game history
    size:int -- length of all lists in the history (all lists are always the same size)
    line_segments:list -- all line segments in the game history
    force_vectors:list -- all force vectors in the game history
    undo() -- move "head" backward in game history
    redo() -- move "head" forward in game history

    Start an empty Game History
    >>> gameHistory = GameHistory()
    >>> print(gameHistory.head)
    None

    Record three iterations of history
    >>> gameHistory.record(LineSeg((1,2),(3,5)))
    >>> print(gameHistory.head)
    0
    >>> gameHistory.record(LineSeg((-1,-2),(3,5)))
    >>> gameHistory.line_segments
    [LineSeg(start=(1, 2), end=(3, 5)), LineSeg(start=(-1, -2), end=(3, 5))]
    >>> print(gameHistory.head)
    1
    >>> gameHistory.record(LineSeg((-1,-2),(3,5)))
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
        self.line_segments = []                         # Initialize: empty list of line segments
        self.force_vectors = []                         # Initialize: empty list of force vectors
        self.head = None                                # Initialize: head points at nothing
        self.size = 0                                   # Initialize: history size is 0

    def record(self, l:LineSeg, v:tuple) -> None:
        if (self.head == None):
            # Prune the future before appending
            self.size = 0
            self.line_segments = []
            self.force_vectors = []
        elif (self.head < self.size-1):
            # Prune the future before appending
            self.size = self.head+1
            self.line_segments = self.line_segments[0:self.size]
            self.force_vectors = self.force_vectors[0:self.size]
        # Normal append
        self.line_segments.append(l)                    # Add this line segment to the history
        self.force_vectors.append(v)                    # Add this force vector to the history
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


class Game:
    def __init__(self):
        pygame.init()                                   # Init pygame -- quit in shutdown
        pygame.font.init()                              # Initialize the font module
        pygame.display.set_caption("Cannon game")

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
        # w = 29; h = 16; scale = 50
        # self.window = Window((scale*w,scale*h))
        self.window = Window((1800,1000))
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
        self.mouse = Mouse(self)
        self.graphPaper = GraphPaper(self)
        self.graphPaper.update(N=40, margin=10, show_paper=False, show_grid=True)
        self.grid_size = self.graphPaper.get_box_size(self.surfs['surf_game_art'])
        self.define_initial_state()


        # FPS
        self.clock = pygame.time.Clock()

    def define_settings(self) -> None:
        self.settings = {}
        self.settings['setting_gravity_on'] = True
        self.settings['setting_show_debugHud'] = True
        self.settings['setting_show_future'] = False

    def define_initial_state(self) -> None:
        self.define_settings()
        self.lineSeg = LineSeg()                        # An empty line segment
        self.forceVector = (0,0)                        # A zero-vector force-vector
        self.gameHistory = GameHistory()                # An empty history of line segments and force vectors
        # Start the game with a cannon shot
        self.lineSeg.start = (0,4)
        # Store game data related to the cannon game
        self.cannons = {}
        # Initial velocity vector set by player
        self.cannons['cannon_initial_velocity'] = (0,0)

    def save(self, path) -> None:
        """Save gameHistory to file.

        gameHistory.line_segments is a list of LineSeg.
        I need to convert this into something JSON can serialize

            TypeError: Object of type LineSeg is not JSON serializable

        See https://docs.python.org/3/library/json.html#py-to-json-table
        JSON encodable types are:
        - dict
            - dict keys must be str, int, or float
        - list, tuple
        - str
        - int, float
        - True, False
        - None

        So, I have these choices:
        Choice 1. Do not use 'json.dump()' to save the game data. Roll my own.
            Con: Rolling my own format for saving data is probably a rabbit hole.
        Choice 2. Learn how to set up a JSONEncoder.default() method to return a serializable object for a LineSeg.
            Con: This sounds like a Python rabbit hole.
        Choice 3. Change my data structures for game data to be one of the JSON encodable types.
            Con: I shouldn't bend my design to meet this requirement, unless doing so improves my design.
        Choice 4. Write a serializer that first encodes the game data to the JSON encodable types.
            Con: I have to write a serializer/deserializer.

        I think choice 4 is probably the best route.
        """
        with open(path, 'w') as fp:
            # json.dump({'lineSegs': {
            #     'history':self.lineSegs.history,
            #     'head':self.lineSegs.head
            #     }}, fp)
            # Serialize
            game_data = {}
            game_data['gameHistory'] = {}
            game_data['gameHistory']['history'] = []
            for lineSeg in self.gameHistory.line_segments:
                game_data['gameHistory']['history'].append((lineSeg.start, lineSeg.end))
            json.dump({'settings':self.settings,
                       'graphPaper':{
                           'N':self.graphPaper.N,
                           'margin':self.graphPaper.margin,
                           'show_paper':self.graphPaper.show_paper,
                           'show_grid':self.graphPaper.show_grid,
                           },
                       'gameHistory':{
                           'head':self.gameHistory.head,
                           'history':game_data['gameHistory']['history']
                           },
                       },
                      fp) # , indent=4)
            logger.debug(f"Game saved to \"{path}\"")

    def load(self, path) -> None:
        with open(path, 'r') as fp:
            game_data = json.load(fp)
        logger.debug(f"Game loaded from \"{path}\"")
        # Deserialize
        self.settings = game_data['settings']
        self.graphPaper.N = game_data['graphPaper']['N']
        self.graphPaper.margin = game_data['graphPaper']['margin']
        self.graphPaper.show_paper = game_data['graphPaper']['show_paper']
        self.graphPaper.show_grid = game_data['graphPaper']['show_grid']
        self.gameHistory = GameHistory()
        for lineSeg in game_data['gameHistory']['history']:
            start = lineSeg[0]
            end = lineSeg[1]
            self.gameHistory.record(LineSeg(start,end))
        self.gameHistory.head = game_data['gameHistory']['head']

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
            case pygame.K_g:
                self.graphPaper.show_grid = not self.graphPaper.show_grid
            case pygame.K_F2:
                self.settings['setting_show_debugHud'] = not self.settings['setting_show_debugHud']
            case pygame.K_F3:
                self.settings['setting_show_future'] = not self.settings['setting_show_future']
            case pygame.K_F10:
                self.settings['setting_gravity_on'] = not self.settings['setting_gravity_on']
            case pygame.K_ESCAPE:
                # Clear the active line segment.
                self.lineSeg = LineSeg()
            case pygame.K_u:
                self.gameHistory.undo()
                if self.gameHistory.head == None:
                    self.lineSeg.end = None             # Let player pick new initial velocity
            case pygame.K_r:
                if kmod & pygame.KMOD_SHIFT:
                    # 'R' - reset (like hitting undo many times)
                    self.gameHistory.head = None
                    self.lineSeg.end = None
                else:
                    # 'r' - redo
                    self.gameHistory.redo()
            case pygame.K_s:
                if kmod & pygame.KMOD_CTRL:
                    logger.debug("Save game (WIP)")
                    self.save('game_state.json')
            case pygame.K_l:
                if kmod & pygame.KMOD_CTRL:
                    logger.debug("Load game (WIP)")
                    self.load('game_state.json')
            case pygame.K_SPACE:
                logger.debug("Perform next iteration of game")
                # Check if there is any history
                if self.gameHistory.head != None:
                    # Take the last line-seg
                    head = self.gameHistory.head
                    last_l = self.gameHistory.line_segments[head]
                    # Make a next line-seg
                    next_l = LineSeg(last_l.start,last_l.end)
                    # Translate next line-seg to head of last line-seg
                    next_l.start = (next_l.start[0] + last_l.vector[0],
                                    next_l.start[1] + last_l.vector[1])
                    next_l.end = (next_l.end[0] + last_l.vector[0],
                                    next_l.end[1] + last_l.vector[1])
                    ### Apply a force vector
                    # Add force to prev velocity to get new vector
                    next_l.end = (next_l.end[0] + self.forceVector[0],
                                  next_l.end[1] + self.forceVector[1])
                    # Record the next line seg
                    self.gameHistory.record(next_l, self.forceVector)

    def handle_mousebuttondown(self) -> None:
        if self.lineSeg.is_finished:
            return
        if not self.lineSeg.is_started:
            # Starting a line segment.
            # This mouse click is the start point.
            self.lineSeg.start = self.mouse.coords['grid']
        else:
            # Ending a line segment.
            # This mouse click is the end point.
            self.lineSeg.end = self.mouse.coords['grid']
            # Store this line segment.
            self.gameHistory.record(self.lineSeg, self.forceVector)
            CONTINUE_DRAWING = False
            if CONTINUE_DRAWING:
                # Reset the active line segment
                self.lineSeg = LineSeg()
                # Record this as the start
                self.lineSeg.start = self.mouse.coords['grid']
            else:
                # Store this line segment as the initial velocity vector
                self.cannons['cannon_initial_velocity'] = self.lineSeg.vector

    def handle_ui_events(self) -> None:
        for event in pygame.event.get():
            match event.type:
                case pygame.WINDOWRESIZED:
                    self.window.handle_WINDOWRESIZED(event)
                    self.surfs['surf_game_art'] = pygame.Surface(self.window.size, flags=0)
                    self.surfs['surf_draw'] = pygame.Surface(self.surfs['surf_game_art'].get_size(), flags=pygame.SRCALPHA)
                case pygame.QUIT: sys.exit()
                case pygame.KEYDOWN: self.handle_keydown(event)
                case pygame.KEYUP: pass
                case pygame.TEXTINPUT: pass
                case pygame.MOUSEMOTION:
                    # logger.debug(f"{pygame.mouse.get_pos()}")
                    pass
                case pygame.MOUSEBUTTONDOWN:
                    # logger.debug("LEFT CLICK PRESS")
                    self.handle_mousebuttondown()
                case pygame.MOUSEBUTTONUP:
                    # logger.debug("LEFT CLICK RELEASE")
                    pass
                case _:
                    logger.debug(f"Ignored event: {pygame.event.event_name(event.type)}")

    def draw_vector_xy_components(self, start:tuple, end:tuple, color:Color) -> None:
        """Draw from start to end as a vector with x and y components.

        start -- (x,y) in grid coordinates
        end -- (x,y) in grid coordinates
        color -- color for line art work
        """
        lineSeg = LineSeg(start,end)
        # Xfm to pixel coordinates
        pix_start = self.graphPaper.xfm_to_pix(start, self.surfs['surf_game_art'])
        pix_end = self.graphPaper.xfm_to_pix(end, self.surfs['surf_game_art'])

        # Define a line from start to end
        line = Line(pix_start, pix_end)

        # Draw the x component of the vector
        xline = Line(line.start, (line.end[0],line.start[1]))
        self.render_line(xline, color, width=1)

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
        # Render the xlabel only if the x-component is not zero
        if lineSeg.vector[0] != 0:
            xlabel.render(self.surfs['surf_game_art'], color)

        # Draw the y component of the vector
        yline = Line((line.end[0],line.start[1]), line.end)
        self.render_line(yline, color, width=1)
        # Label y component
        ylabel = Text((0,0), font_size=max(self.grid_size[0], self.grid_size[1]), sys_font="Roboto Mono")
        ylabel.update(f"{lineSeg.vector[1]}")
        ylabel_height = ylabel.font.get_linesize()*len(ylabel.text_lines)
        ylabel_width = ylabel.font.size(ylabel.text_lines[0])[0]
        if lineSeg.vector[0] < 0:
            # If x-component is NEGATIVE, align center LEFT of label to midpoint of the y-component
            ylabel.pos = (yline.midpoint[0] - ylabel_width - ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_height/2)
        else:
            # If x-component is POSITIVE, align center RIGHT of label to midpoint of the y-component
            ylabel.pos = (yline.midpoint[0] + ylabel.font.size("0")[0]/2, yline.midpoint[1] - ylabel_height/2)
        # Render the ylabel only if the y-component is not zero
        if lineSeg.vector[1] != 0:
            ylabel.render(self.surfs['surf_game_art'], color)

        ### Draw little tick marks along these lines to indicate measuring (like a ruler has tick marks)
        # Draw a tick mark at every grid intersection along the x-component
        tick_len = int(0.5*0.5*0.5*self.grid_size[0])
        xrange_stop = abs(lineSeg.vector[0])
        for i in range(1, xrange_stop):
            x = start[0] + signum(lineSeg.vector[0])*i
            y = start[1]
            pix_start = xfm_grid_to_pix((x,y), self.graphPaper, self.surfs['surf_game_art'])
            line = Line((pix_start[0],pix_start[1]-tick_len),
                        (pix_start[0],pix_start[1]+tick_len))
            self.render_line(line, color, width=1)
        # Draw a tick mark at every grid intersection along the y-component
        for i in range(abs(lineSeg.vector[1])):
            x = end[0]
            y = end[1] - signum(lineSeg.vector[1])*i
            pix_start = xfm_grid_to_pix((x,y), self.graphPaper, self.surfs['surf_game_art'])
            line = Line((pix_start[0]-tick_len,pix_start[1]),
                        (pix_start[0]+tick_len,pix_start[1]))
            self.render_line(line, color, width=1)

    def render_line_as_vector(self, line:Line, color:Color, width:int) -> None:
        """Render a line on the game art with an arrow head at the end point.
        line -- Line(start, end)
        color -- pygame.Color(R,G,B,A)
        width -- line thickness in pixels
        """
        # Find the minimum dimension of one grid box and scale it by s
        s = 2/5
        a = int(round(min(self.grid_size[0], self.grid_size[1])*s))
        # Use 'a' to calculate a scaling factor for the line.vector
        if line.start != line.end:
            k = math.sqrt((a**2)/(line.vector[0]**2 + line.vector[1]**2))
        else:
            # If the vector is zero, scaling factor is 0 (avoid divide by zero)
            k = 0
        # Start the arrow head back from the end of the line by a distance of 1/2 the min grid dimension
        arrow_head_base = (line.end[0] - k*line.vector[0], line.end[1] - k*line.vector[1])
        # Get the perpendicular vector
        pvec = (-1*line.vector[1], line.vector[0])
        # Form the arrow head with the tip at the end of the line and the
        # other two points of the triangle calc from pvec and arrow_head_base
        arrow_head_points = [ line.end,     # Arrow head tip
                              (arrow_head_base[0] - k*pvec[0]/2, arrow_head_base[1] - k*pvec[1]/2),
                              (arrow_head_base[0] + k*pvec[0]/2, arrow_head_base[1] + k*pvec[1]/2)
                              ]
        arrow_rect = pygame.draw.polygon(self.surfs['surf_draw'], color, arrow_head_points)
        self.render_rect_area(arrow_rect)
        # Draw the line segment
        arrow_shaft = Line(line.start, arrow_head_base)
        self.render_line(arrow_shaft, color, width)

    def draw_mouse_as_snapped_dot(self, color:Color) -> None:
        # Set dot radii based on the grid_size
        big_radius = int(0.5*0.5*self.grid_size[0])
        # Draw a dot at the grid intersection closest to the mouse
        self.mouse.render_snap_dot(radius=big_radius, color=color)

    def draw_started_lineSeg(self, draw_as_vector:bool) -> None:
        # Set colors based on paper background on/off
        if self.graphPaper.show_paper:
            # Set color of x and y components
            xy_commponent_color = self.colors['color_debug_hud_dark']
            # Set color of the line drawn with the mouse
            line_color = self.colors['color_line_started_dark']
        else:
            # Set color of x and y components
            xy_commponent_color = self.colors['color_debug_hud_light']
            # Set color of the line drawn with the mouse
            line_color = self.colors['color_line_started_light']

        self.draw_vector_xy_components(
                start=self.lineSeg.start,
                end=self.mouse.coords['grid'],
                color=xy_commponent_color)

        # Create a line from the start to the current mouse position
        pix_start = self.graphPaper.xfm_to_pix(self.lineSeg.start, self.surfs['surf_game_art'])
        started_line = Line(pix_start, self.mouse.coords['pixel'])
        if draw_as_vector:
            # Draw the line segment as a vector
            self.render_line_as_vector(started_line, line_color, width=5)
        else:
            # Draw the line segment
            self.render_line(started_line, line_color, width=5)
            # Draw a big dot at the grid intersection closest to the mouse
            self.draw_mouse_as_snapped_dot(Color(0,200,255,150))

        # Draw a dot at the start of the vector
        small_radius = int(0.5*0.5*0.5*self.grid_size[0])
        self.render_dot(started_line.start, radius=small_radius, color=Color(255,0,0,150))

    def game_loop(self) -> None:
        # Create the debug HUD (create this first so everything after can add debug text)
        self.debugHud = DebugHud(self)
        self.debugHud.is_visible = self.settings['setting_show_debugHud']
        if self.settings['setting_gravity_on']:
            self.debugHud.add_text("GRAVITY: ON")
            self.forceVector = (0,-1)
        else:
            self.debugHud.add_text("GRAVITY: OFF")
            self.forceVector = (0,0)
        if self.settings['setting_show_future']:
            self.debugHud.add_text("FUTURE: ON")
        else:
            self.debugHud.add_text("FUTURE: OFF")
        self.debugHud.add_text(f"Initial velocity: {self.cannons['cannon_initial_velocity']}")

        # Get user input
        self.handle_ui_events()
        self.mouse.update()

        # Clear screen
        # self.surfs['surf_os_window'].fill(self.colors['color_os_window_bgnd'])
        self.surfs['surf_game_art'].fill(self.colors['color_game_art_bgnd'])

        # Fill game art area with graph paper
        self.graphPaper.render(self.surfs['surf_game_art'])

        # Find the size of one grid box
        self.grid_size = self.graphPaper.get_box_size(self.surfs['surf_game_art'])

        if self.lineSeg.is_started:
            # Draw a vector from start to the mouse and show the xy components
            self.draw_started_lineSeg(draw_as_vector=True)
        if self.lineSeg.is_finished:
            # Only draw the xy components of the initial velocity vector (don't draw the vector itself)
            if self.graphPaper.show_paper:
                xy_commponent_color = self.colors['color_debug_hud_dark']
            else:
                xy_commponent_color = self.colors['color_debug_hud_light']
            self.draw_vector_xy_components(self.lineSeg.start,
                                           self.lineSeg.end,
                                           xy_commponent_color)
            # Draw the mouse location
            self.draw_mouse_as_snapped_dot(Color(255,0,0,150))

        if self.settings['setting_show_future']:
            ### Draw all the future velocity vectors based on the initial velocity vector
            # Set up colors (TODO: move this to an @property)
            if self.graphPaper.show_paper:
                # Brown if paper is visible
                velocity_line_color = Color(60,30,0,120)
                force_line_color = Color(200,30,0,120)
            else:
                # Yellow if paper is invisible
                velocity_line_color = Color(210,200,0,120)
                force_line_color = Color(200,30,0,120)
            # Get the initial velocity vector
            init_vel = LineSeg()
            init_vel.start = self.lineSeg.start
            if self.lineSeg.is_started:
                init_vel.end = self.mouse.coords['grid']
            if self.lineSeg.is_finished:
                init_vel.end = self.lineSeg.end
            # Convert initial velocity vector to pixel coordinates
            l = init_vel
            pix_start = xfm_grid_to_pix(l.start, self.graphPaper, self.surfs['surf_game_art'])
            pix_end = xfm_grid_to_pix(l.end, self.graphPaper, self.surfs['surf_game_art'])
            line = Line(pix_start, pix_end)
            # Draw the initial velocity
            self.render_line_as_vector(line, velocity_line_color, width=5)
            # Translate force vector to end of initial velocity
            f = self.forceVector
            l = LineSeg(start=l.end, end=(l.end[0]+f[0], l.end[1]+f[1]))
            # Convert (translated) force vector to pixel coordinates
            pix_start = xfm_grid_to_pix(l.start, self.graphPaper, self.surfs['surf_game_art'])
            pix_end = xfm_grid_to_pix(l.end, self.graphPaper, self.surfs['surf_game_art'])
            line = Line(pix_start, pix_end)
            # Draw the force vector
            self.render_line_as_vector(line, force_line_color, width=5)

        else: # Only show the past
            # Draw the vectors
            for i,(l,f) in enumerate(zip(self.gameHistory.line_segments, self.gameHistory.force_vectors)):
                # Draw nothing if play-head points to nothing
                if self.gameHistory.head == None: break
                # Only draw lines up until the play-head
                if i > self.gameHistory.head: break
                # Set color of the lines in the history
                if self.graphPaper.show_paper:
                    # Brown if paper is visible
                    velocity_line_color = Color(60,30,0,120)
                    force_line_color = Color(200,30,0,120)
                else:
                    # Yellow if paper is invisible
                    velocity_line_color = Color(210,200,0,120)
                    force_line_color = Color(200,30,0,120)
                # Convert velocity vector line segment to a line in pixel coordinates
                pix_start = xfm_grid_to_pix(l.start, self.graphPaper, self.surfs['surf_game_art'])
                pix_end = xfm_grid_to_pix(l.end, self.graphPaper, self.surfs['surf_game_art'])
                line = Line(pix_start, pix_end)
                # Draw the line segment
                # self.render_line(line, line_color, width=5)
                self.render_line_as_vector(line, velocity_line_color, width=5)
                # Convert force vector line segment to a line in pixel coordinates
                l = LineSeg(start=l.end, end=(l.end[0]+f[0],l.end[1]+f[1]))
                pix_start = xfm_grid_to_pix(l.start, self.graphPaper, self.surfs['surf_game_art'])
                pix_end = xfm_grid_to_pix(l.end, self.graphPaper, self.surfs['surf_game_art'])
                line = Line(pix_start, pix_end)
                # Draw the line segment
                # self.render_line(line, line_color, width=5)
                self.render_line_as_vector(line, force_line_color, width=5)

        # Draw game art to OS window
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        self.surfs['surf_os_window'].blit(self.surfs['surf_game_art'], (0,0))

        # List vector velocities and forces as strings as they are added by the user:
        vectors_str_list = ["Velocity vector: " + str(l.vector) + ", Force vector: " + str(f) for l,f in zip(self.gameHistory.line_segments,self.gameHistory.force_vectors)]
        vectors_str = "\n".join(vectors_str_list)
        self.debugHud.add_text(f"Mouse: {self.mouse.coords['grid']} | gameHistory.head: {self.gameHistory.head}")
        self.debugHud.add_text(f"N: {self.graphPaper.N}, grid_size: {self.grid_size} pixels")
        self.debugHud.add_text(f"{vectors_str}")

        if self.debugHud.is_visible:
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
