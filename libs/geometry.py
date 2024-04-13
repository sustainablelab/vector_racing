#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Geometry
"""

from dataclasses import dataclass

@dataclass
class Line:
    start:tuple
    end:tuple

    @property
    def vector(self) -> tuple:
        if not self.start: return (None,None)
        if not self.end: return (None,None)
        return (self.end[0]-self.start[0], self.end[1]-self.start[1])

    @property
    def midpoint(self) -> tuple:
        if not self.start: return (None,None)
        if not self.end: return (None,None)
        return (self.start[0] + self.vector[0]*0.5, self.start[1] + self.vector[1]*0.5)

