#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Make graph paper.
"""

import sys
import logging
from dataclasses import dataclass
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
from libs.utils import scale_data

logger = logging.getLogger(__name__)


@dataclass
class Line:
    start_pos:tuple
    end_pos:tuple

class GraphPaper:
    def __init__(self, game):
        self.game = game

        # Set up colors
        self.colors = {}
        self.colors['color_graph_paper'] = Color(180,200,255,255)
        self.colors['color_graph_lines'] = Color(100,100,255,50)
        # self.colors['color_graph_lines'] = Color(100,100,255)

        # Set up surfaces
        self.surfs = {}

        # logger.debug("Created GraphPaper!")

    def render(self, surf):
        # Color the background "graph paper blue"
        surf.fill(self.colors['color_graph_paper'])

        # Calculate graph lines
        # Create N vertical and N horizontal grid lines
        N = 20
        # Set min (A) and max (B) in grid-coordinate space
        A=(0,0); B = (N,N) # Ax = 0; Ay = 0; Bx = N; By = N
        Cxs = list(range(A[0],B[0]+1))
        Cys = list(range(A[1],B[1]+1))
        # Set min (a) and max (b) in game-art space
        margin = 10
        ax = 0 + margin;
        # TODO: Change this to reference graph art size, not os window size
        ay = self.game.window.size[1] - margin
        bx = self.game.window.size[0] - margin;
        by = 0 + margin
        cxs = scale_data(Cxs, ax, bx)
        cys = scale_data(Cys, ay, by)

        # Draw graph lines
        ### Surface((width, height), flags=0, Surface) -> Surface
        self.surfs['surf_graph'] = pygame.Surface(
                (self.game.window.size),
                flags=pygame.SRCALPHA
                )
        line_width = 3

        # Make vertical lines
        # self.surfs['surf_graph2'] = pygame.Surface(
        #         (self.game.window.size),
        #         flags=pygame.SRCALPHA
        #         )
        graph_lines = []
        for cx in cxs:
            line = Line((cx,ay),(cx,by))
            graph_lines.append(line)
        for line in graph_lines:
            # Draw a graph line
            ### line(surface, color, start_pos, end_pos, width=1) -> Rect
            pygame.draw.line(self.surfs['surf_graph'], self.colors['color_graph_lines'],
                             line.start_pos, line.end_pos, width=line_width)
        # surf.blit(self.surfs['surf_graph'],(0,0))

        # Make horizontal lines
        # self.surfs['surf_graph2'] = pygame.Surface(
        #         (self.game.window.size),
        #         flags=pygame.SRCALPHA
        #         )
        graph_lines = []
        for cy in cys:
            line = Line((ax,cy),(bx,cy))
            graph_lines.append(line)
        for line in graph_lines:
            # Draw a graph line
            ### line(surface, color, start_pos, end_pos, width=1) -> Rect
            pygame.draw.line(self.surfs['surf_graph'], self.colors['color_graph_lines'],
                             line.start_pos, line.end_pos, width=line_width)
            # Clear graph paper surface
            # self.surfs['surf_graph'].fill(self.game.colors['color_clear'])
        ### blit(source, dest, area=None, special_flags=0) -> Rect
        surf.blit(self.surfs['surf_graph'],(0,0))

if __name__ == '__main__':
    from pathlib import Path
    print(f"Run doctests in {Path(__file__).name}")
    import doctest
    doctest.testmod()
