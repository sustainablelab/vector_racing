#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
"""Geometry
"""

from dataclasses import dataclass

@dataclass
class Line:
    start_pos:tuple
    end_pos:tuple

