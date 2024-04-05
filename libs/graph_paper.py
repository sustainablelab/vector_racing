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

    def draw(self, surf, color, width) -> pygame.Rect:
        ### line(surface, color, start_pos, end_pos, width=1) -> Rect
        return pygame.draw.line(surf, color, self.start_pos, self.end_pos, width)

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

        # Set defaults in case update() is never called
        self.N = 20
        self.margin = 10

    def update(self, N:int, margin:int) -> None:
        """Set N vertical and N horizontal grid lines.

        N -- graph paper has N vertical lines and N horizontal lines
        margin -- margin in pixels around the graph paper
        """
        self.N = N
        self.margin = margin

    def calculate_graph_lines(self, surf:pygame.Surface, N:int, margin:int) -> list:
        """Return list of Lines: N vertical and N horizontal grid lines.

        N -- number of lines for each dimension
        surf -- fill this surface with the lines
        margin -- space in pixels between edge of screen and edge of graph paper

        Generate lines from the affine combination:

            (1-λ)A + λB = C

        See scale_data().
        """
        # Set A=min(x,y) and B=max(x,y) in grid-coordinate space
        A=(0,0); B = (N,N)
        # Generate Cs (intermediate points) between A and B
        Cxs = list(range(A[0],B[0]+1))
        Cys = list(range(A[1],B[1]+1))
        # Set a=min(x,y) and b=max(x,y) in game-art space
        ax = 0 + margin;
        ay = surf.get_size()[1] - margin
        bx = surf.get_size()[0] - margin;
        by = 0 + margin
        # Generate cs (intermediate points) between a and b
        cxs = scale_data(Cxs, ax, bx)
        cys = scale_data(Cys, ay, by)
        # Make vertical lines
        graph_lines = []
        for cx in cxs:
            line = Line((cx,ay),(cx,by))
            graph_lines.append(line)
        # Make horizontal lines
        for cy in cys:
            line = Line((ax,cy),(bx,cy))
            graph_lines.append(line)
        return graph_lines

    def render(self, surf):
        """Render graph paper on the surface.

        surf -- render on this surface

        - Make a grid that fills the surface (see calculate_graph_lines).
        - Use Line.draw() to draw lines to a temporary surface.
        - Blit each line from the temporary surface to the actual render
          surface.
            - This way, where the lines overlap, I get dark spots.
            - Since the area of each line is small, I can blit each line
              without taking a performance hit.
        """
        # Color the background "graph paper blue"
        surf.fill(self.colors['color_graph_paper'])

        graph_lines = self.calculate_graph_lines(surf, self.N, self.margin)

        # Draw graph lines
        line_width = 3
        # Draw the lines on a temporary surface
        ### Surface((width, height), flags=0, Surface) -> Surface
        self.surfs['surf_draw'] = pygame.Surface(
                (self.game.window.size),
                flags=pygame.SRCALPHA
                )

        BLIT_EACH_LINE = True
        for line in graph_lines:
            # Draw a graph line on the temporary surface
            ### line(surface, color, start_pos, end_pos, width=1) -> Rect
            line_rect = line.draw(
                    self.surfs['surf_draw'],
                    self.colors['color_graph_lines'],
                    width=line_width
                    )
            if BLIT_EACH_LINE:
                # Copy each line from the temporary surface to the actual surface.
                ### Blit lines individually to get the dark spot from alpha blend
                ### where lines intersect.
                surf.blit(
                        self.surfs['surf_draw'],            # From this surface
                        line_rect,                          # Go to this x,y coordinate
                        line_rect,                          # Grab only this area
                        special_flags=pygame.BLEND_ALPHA_SDL2 # Use alpha blending
                        )
        if not BLIT_EACH_LINE:
            ### Blit the whole temporary surface in one shot to avoid those dark spots
            ### blit(source, dest, area=None, special_flags=0) -> Rect
            surf.blit(self.surfs['surf_draw'],(0,0))

if __name__ == '__main__':
    from pathlib import Path
    print(f"Run doctests in {Path(__file__).name}")
    import doctest
    doctest.testmod()
