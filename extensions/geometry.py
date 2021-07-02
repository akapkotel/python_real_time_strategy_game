"""
Testing AOT compilation against JIT compilation of normal @njit.
"""

from functools import lru_cache

from numba.pycc import CC

cc = CC('geometry')
cc.verbose = True


@lru_cache(maxsize=None)
@cc.export('calculate_circular_area', '(i8, i8, i8)')
# @njit(['int64, int64, int64'], nogil=True, fastmath=True)
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


cc.compile()
