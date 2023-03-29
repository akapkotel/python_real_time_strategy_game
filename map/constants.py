from typing import Tuple, Union, List

from utils.data_types import GridPosition

TILE_WIDTH = 60
TILE_HEIGHT = 50

PATH = 'PATH'
VERTICAL_DIST = 10
DIAGONAL_DIST = 14  # approx square root of 2

ADJACENT_OFFSETS = [
    (-1, -1), (-1, 0), (-1, +1), (0, +1), (0, -1), (+1, -1), (+1, 0), (+1, +1)
]
OPTIMAL_PATH_LENGTH = 50

# typing aliases:
NormalizedPoint = Tuple[int, int]
MapPath = Union[List[NormalizedPoint], List[GridPosition]]
PathRequest = Tuple['Unit', GridPosition, GridPosition]
TreeID = int
