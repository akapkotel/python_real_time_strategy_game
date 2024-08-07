#!/usr/bin/env python

from typing import Dict
from functools import lru_cache
from math import atan2, degrees, radians, sin, cos, dist
from typing import Optional, Sequence, Tuple, List, Set

from numba import njit

from utils.data_types import Point, Number

ROTATIONS = 16  # how many directions our Sprites can rotate toward
CIRCLE_SLICE = 360 / ROTATIONS  # angular width of a single rotation step
ROTATION_STEP = CIRCLE_SLICE / 2  # center of each rotation step


matrix = [(-8, -4), (-8, -3), (-8, -2), (-8, -1), (-8, 0), (-8, 1), (-8, 2),
          (-8, 3), (-8, 4), (-7, -5), (-7, -4), (-7, -3), (-7, -2), (-7, -1),
          (-7, 0), (-7, 1), (-7, 2), (-7, 3), (-7, 4), (-7, 5), (-6, -6),
          (-6, -5), (-6, -4), (-6, -3), (-6, -2), (-6, -1), (-6, 0), (-6, 1),
          (-6, 2), (-6, 3), (-6, 4), (-6, 5), (-6, 6), (-5, -7), (-5, -6),
          (-5, -5), (-5, -4), (-5, -3), (-5, -2), (-5, -1), (-5, 0), (-5, 1),
          (-5, 2), (-5, 3), (-5, 4), (-5, 5), (-5, 6), (-5, 7), (-4, -8),
          (-4, -7), (-4, -6), (-4, -5), (-4, -4), (-4, -3), (-4, -2), (-4, -1),
          (-4, 0), (-4, 1), (-4, 2), (-4, 3), (-4, 4), (-4, 5), (-4, 6),
          (-4, 7), (-4, 8), (-3, -8), (-3, -7), (-3, -6), (-3, -5), (-3, -4),
          (-3, -3), (-3, -2), (-3, -1), (-3, 0), (-3, 1), (-3, 2), (-3, 3),
          (-3, 4), (-3, 5), (-3, 6), (-3, 7), (-3, 8), (-2, -8), (-2, -7),
          (-2, -6), (-2, -5), (-2, -4), (-2, -3), (-2, -2), (-2, -1), (-2, 0),
          (-2, 1), (-2, 2), (-2, 3), (-2, 4), (-2, 5), (-2, 6), (-2, 7),
          (-2, 8), (-1, -8), (-1, -7), (-1, -6), (-1, -5), (-1, -4), (-1, -3),
          (-1, -2), (-1, -1), (-1, 0), (-1, 1), (-1, 2), (-1, 3), (-1, 4),
          (-1, 5), (-1, 6), (-1, 7), (-1, 8), (0, -8), (0, -7), (0, -6),
          (0, -5), (0, -4), (0, -3), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
          (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (1, -8), (1, -7),
          (1, -6), (1, -5), (1, -4), (1, -3), (1, -2), (1, -1), (1, 0), (1, 1),
          (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (2, -8),
          (2, -7), (2, -6), (2, -5), (2, -4), (2, -3), (2, -2), (2, -1),
          (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7),
          (2, 8), (3, -8), (3, -7), (3, -6), (3, -5), (3, -4), (3, -3),
          (3, -2), (3, -1), (3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5),
          (3, 6), (3, 7), (3, 8), (4, -8), (4, -7), (4, -6), (4, -5), (4, -4),
          (4, -3), (4, -2), (4, -1), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4),
          (4, 5), (4, 6), (4, 7), (4, 8), (5, -7), (5, -6), (5, -5), (5, -4),
          (5, -3), (5, -2), (5, -1), (5, 0), (5, 1), (5, 2), (5, 3), (5, 4),
          (5, 5), (5, 6), (5, 7), (6, -6), (6, -5), (6, -4), (6, -3), (6, -2),
          (6, -1), (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5), (6, 6),
          (7, -5), (7, -4), (7, -3), (7, -2), (7, -1), (7, 0), (7, 1), (7, 2),
          (7, 3), (7, 4), (7, 5), (8, -4), (8, -3), (8, -2), (8, -1), (8, 0),
          (8, 1), (8, 2), (8, 3), (8, 4)]


def precalculate_possible_sprites_angles(rotations: int = ROTATIONS,
                                   circle_slice: float = CIRCLE_SLICE,
                                   rotation_step: float = ROTATION_STEP) -> Dict[int, int]:
    """
    Build dict of int angles. We chop 360 degrees circle by 16 slices
    each of 22.5 degrees. First slice has its center at 0/360 degrees,
    second slice has its center at 22.5 degrees etc. This dict allows
    for fast replacing angle of range 0-359 to one of 16 pre-calculated
    angles.
    """
    return {
        i: j if j < rotations else 0 for j in range(0, rotations + 1)
        for i in range(361) if (j * circle_slice) - i < rotation_step
    }


@njit(nogil=True, fastmath=True, cache=True)
def calculate_angle(sx: float, sy: float, ex: float, ey: float) -> float:
    """
    Calculate angle in direction from 'start' to the 'end' point in degrees.

    :param:sx float -- x coordinate of start point
    :param:sy float -- y coordinate of start point
    :param:ex float -- x coordinate of end point
    :param:ey float -- y coordinate of end point
    :return: float -- degrees in range 0-360.
    """
    rads = atan2(ex - sx, ey - sy)
    return -degrees(rads) % 360


@njit(nogil=True, fastmath=True, cache=True)
def close_enough(coord_a: Point, coord_b: Point, distance: float) -> bool:
    """
    Calculate distance between two points in 2D space and find if distance
    is less than minimum distance.

    :param coord_a: Point -- (x, y) coords of first point
    :param coord_b: Point -- (x, y) coords of second point
    :param distance: float -- minimal distance to check against
    :return: bool -- if distance is less than
    """
    return dist(coord_a, coord_b) <= distance


# @njit(nogil=True, fastmath=True)
@njit(['float64, float64'], nogil=True, fastmath=True, cache=True)
def vector_2d(angle: float, scalar: float) -> Point:
    """
    Calculate x and y parts of the current vector.

    :param angle: float -- angle of the vector
    :param scalar: float -- scalar difference of the vector (e.g. max_speed)
    :return: Point -- x and y parts of the vector in format: (float, float)
    """
    rad = -radians(angle)
    return sin(rad) * scalar, cos(rad) * scalar


def move_along_vector(start: Point,
                      velocity: float,
                      target: Optional[Point] = None,
                      angle: Optional[float] = None) -> Point:
    """
    Create movement vector starting at 'start' point angled in direction of
    'target' point with scalar velocity 'velocity'. Optionally, instead of
    'target' position, you can pass starting 'angle' of the vector.

    Use 'current_waypoint' position only, when you now the point and do not know the
    angle between two points, but want quickly calculate position of the
    another point lying on the line connecting two, known points.

    :param start: tuple -- point from vector starts
    :param target: tuple -- current_waypoint that vector 'looks at'
    :param velocity: float -- scalar length of the vector
    :param angle: float -- angle of the vector direction
    :return: tuple -- (optional)position of the vector end
    """
    if target is None and angle is None:
        raise ValueError("You MUST pass current_waypoint position or vector angle!")
    p1 = (start[0], start[1])
    if target:
        p2 = (target[0], target[1])
        angle = calculate_angle(*p1, *p2)
    vector = vector_2d(angle, velocity)
    return p1[0] + vector[0], p1[1] + vector[1]


@lru_cache(maxsize=None)
def calculate_circular_area(grid_x, grid_y, max_distance):
    radius = max_distance * 1.6
    observable_area = []
    for x in range(-max_distance, max_distance + 1):
        dist_x = abs(x)
        for y in range(-max_distance, max_distance + 1):
            dist_y = abs(y)
            total_distance = dist_x + dist_y
            if total_distance < radius:
                grid = (grid_x + x, grid_y + y)
                observable_area.append(grid)
    return observable_area


@lru_cache
def precalculate_circular_area_matrix(max_distance: int) -> Tuple[Tuple[int, int], ...]:
    radius = max_distance * 1.6
    observable_area = []
    for x in range(-max_distance, max_distance + 1):
        dist_x = abs(x)
        for y in range(-max_distance, max_distance + 1):
            dist_y = abs(y)
            total_distance = dist_x + dist_y
            if total_distance < radius:
                observable_area.append((x, y))
    return tuple(observable_area)


@lru_cache(maxsize=None)
def find_area(x: int, y: int, matrix_: Tuple[Tuple[int, int]] = None) -> Set[Tuple[int, int]]:
    return {(pos[0] + x, pos[1] + y) for pos in matrix_}


def clamp(value: Number, maximum: Number, minimum: Number = 0) -> Number:
    """Guarantee that number will be larger than min and less than max."""
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def average_position_of_points_group(positions: Sequence[Point]) -> Point:
    """
    :param positions: Sequence -- array of Points (x, y)
    :return: Point -- two-dimensional tuple (x, y) representing point
    """
    if (positions_count := len(positions)) == 1:
        return positions[0]
    return sum(p[0] for p in positions) / positions_count, sum(p[1] for p in positions) / positions_count


def generate_2d_grid(start_x: float, start_y: float, rows: int, columns: int, item_width: float, item_height: float, padding=0) -> List[Tuple[Number, Number]]:
    """
    Create 2-dimensional grid ordering items in rows and columns. This function automatically distributes items among
    rows and columns starting at first column on the left side and filling it from the top to bottom.
    """
    grid = []
    for column in range(columns):
        shifted_x = start_x + column * (item_width + padding)
        for row in range(rows):
            shift_y = (row % rows) * (item_height + padding)
            grid.append((shifted_x, start_y - shift_y))
    return grid


def find_grid_center(grid: Tuple[int, int], size: Tuple[int, int]) -> Tuple[int, int]:
    return tuple(center_coordinate(c, size) for (c, size) in zip(grid, size))


def center_coordinate(coordinate: int, size: int) -> int:
    if size == 1:
        return coordinate
    elif size % 2 == 0:
        return coordinate + (size // 2)
    else:
        return coordinate + (size // 2)
