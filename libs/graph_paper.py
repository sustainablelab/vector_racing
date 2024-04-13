#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Make graph paper, xfm between pixel and grid coordinates.

Define surfaces in the game.
Do not define surfaces in 'graph_paper.py'. Not even temporary ones.
"""

import sys
import logging
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"          # Set pygame env var to hide "Hello" msg
import pygame
from pygame import Color
if __name__ == '__main__':
    from utils import scale_data
    from geometry import Line
else:
    from libs.utils import scale_data
    from libs.geometry import Line

logger = logging.getLogger(__name__)


class GraphPaper:
    def __init__(self, game):
        self.game = game

        # Set up colors
        self.colors = {}
        self.colors['color_graph_paper'] = Color(180,200,255,255)
        self.colors['color_graph_lines'] = Color(100,100,255,50)

        # Set defaults in case update() is never called
        self.N = 20
        self.margin = 10

    def get_box_size(self, surf:pygame.Surface) -> tuple:
        """Return the size of one grid box in pixel coordinates as (w,h)

        surf -- the surface the graph paper is rendered on
        """
        return xfm_grid_to_pix((1,self.N-1), self, surf)

    def xfm_to_pix(self, point:tuple, surf:pygame.Surface) -> tuple:
        """Return point on grid transformed to pixel coordinates.

        surf -- the surface the graph paper is rendered on
        """
        return xfm_grid_to_pix(point, self, surf)

    def update(self, N:int, margin:int, show_paper:bool) -> None:
        """Set N vertical and N horizontal grid lines.

        N -- graph paper has N vertical lines and N horizontal lines
        margin -- margin in pixels around the graph paper
        """
        self.N = N
        self.margin = margin
        self.show_paper = show_paper

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
        - Draw lines to a temporary surface.
        - Blit each line from the temporary surface to the actual render
          surface.
            - This way, where the lines overlap, I get dark spots.
            - Since the area of each line is small, I can blit each line
              without taking a performance hit.
        """
        # Set a graph paper background
        if self.show_paper:
            # Color the background "graph paper blue"
            surf.fill(self.colors['color_graph_paper'])

        # Calculate graph lines
        graph_lines = self.calculate_graph_lines(surf, self.N, self.margin)

        # Draw graph lines
        line_width = 3
        for line in graph_lines:
            self.game.render_line(line, self.colors['color_graph_lines'], line_width)

        # Clean up
        self.game.render_clean()

def xfm_pix_to_grid(point:tuple, graphPaper:GraphPaper, surf:pygame.Surface) -> tuple:
    """Return the point in grid coordinates.

    point -- x,y in pixel coordinates
    surf -- surface the graph paper is rendered on
    graphPaper -- the graph paper

    General coordinate transformation:

        y1,y2 = [a,b;c,d]*(x1,x2)

    Or:
        y1 = ax1 + bx2
        y2 = cx1 + dx2

    But in my case, grid coordinate system y1,y2 is just a scaled version of
    pixel coordinate system x1,x2.

    So b=0 and c=0 and we have:
        y1 = ax1
        y2 = dx2

    Then I can just use scale_data() from libs.utils.

    Pass a list of three values: [min,mouse,max] and, from the scaled
    data, extract the middle value.
    """
    size = surf.get_size()
    return (round(scale_data(
                    [0+graphPaper.margin, point[0], size[0]-graphPaper.margin],
                    0, graphPaper.N)[1]
                 ),
             round(scale_data(
                    [0+graphPaper.margin, point[1], size[1]-graphPaper.margin],
                    graphPaper.N, 0)[1]
                 ))

def xfm_grid_to_pix(point:tuple, graphPaper:GraphPaper, surf:pygame.Surface) -> tuple:
    """Return the point in pixel coordinates.

    point -- x,y in grid coordinates
    surf -- surface the graph paper is rendered on
    graphPaper -- the graph paper

    Use scale_data() from libs.utils.
    Pass a list of three values: [min,mouse,max] and, from the scaled
    data, extract the middle value.
    """
    size = surf.get_size()
    return (round(scale_data(
                    [0, point[0], graphPaper.N],
                    0+graphPaper.margin, size[0]-graphPaper.margin)[1]
                 ),
             round(scale_data(
                    [0, point[1], graphPaper.N],
                    size[1]-graphPaper.margin, 0+graphPaper.margin)[1]
                 ))

if __name__ == '__main__':
    from pathlib import Path
    print(f"Run doctests in {Path(__file__).name}")
    import doctest
    doctest.testmod()
