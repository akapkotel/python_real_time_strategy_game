from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional

from arcade import (
    Window,
    Sprite,
    SpriteList,
    ShapeElementList,
    run,
    load_texture,
    draw_polygon_filled,
    create_line_strip, Texture
)

from map.quadtree import IsometricQuadTree
from utils.colors import WHITE, GREEN


ADJACENCY_MATRIX = ((-1, -1), (-1, 0), (0, -1), (0, 1), (1, 1), (1, 0), (1, -1), (-1, 1))


def invert_matrix(a, b, c, d):
    det = (1 / (a * d - b * c))
    return det * d, det * -b, det * -c, det * a


def pos_to_iso_grid(pos_x: int, pos_y: int) -> Tuple[int, int] | None:
    """Use this, function from other scripts to convert positions to iso grid coordinates."""
    isometric_map = IsometricMap.instance
    return isometric_map.pos_to_iso_grid(isometric_map, pos_x, pos_y)


class IsometricMap:
    game = None
    instance = None

    def __init__(self, window: Window, map_width: int, map_height: int, tile_width: int):
        self.window = window
        self.tiles: Dict[Tuple[int, int], IsometricTile] = {}
        self.tile_width = tile_width
        self.tile_height = tile_width // 2
        self.map_width = map_width
        self.map_height = map_height
        self.first_tile = map_width // 2, map_height - self.tile_height // 2
        self.rows = 60
        self.columns = 60
        self.grid_gizmo = ShapeElementList()
        self.tiles_sprites = SpriteList(use_spatial_hash=True, is_static=True)
        self.terrains = self.find_terrains()
        self.tiles = self.generate_tiles()
        self.quadtree = self.generate_quadtree()
        IsometricMap.instance = self

    def find_terrains(self) -> Dict[str, Texture]:
        return {
            name: load_texture(f'{name}.png', 0, 0, self.tile_width, self.tile_height)
            for name in ('grass', 'sand', 'water')
        }

    def generate_quadtree(self) -> IsometricQuadTree:
        quad_iso_x, quad_iso_y = self.iso_grid_to_position(self.rows // 2, self.columns // 2)
        quad_width, quad_height = self.columns * self.tile_width, self.rows * self.tile_height
        return IsometricQuadTree(quad_iso_x, quad_iso_y + self.tile_height // 2, quad_width, quad_height)

    def adjacent_grids(self, gx: int, gy: int) -> List[Tuple[int, int]]:
        return [adj for adj in [(gx + x, gy + y) for (x, y) in ADJACENCY_MATRIX] if adj in self.tiles]

    def generate_tiles(self) -> Dict[Tuple[int, int], IsometricTile]:
        tiles = {}
        for row in range(self.rows):
            for col in range(self.columns):
                idx = row * self.columns + col + 1
                tile_x, tile_y = self.iso_grid_to_position(col, row)
                sprite = Sprite(center_x=tile_x, center_y=tile_y, hit_box_algorithm='None')
                sprite.texture = random.choice(list(self.terrains.values()))
                tile = IsometricTile(idx, col, row, tile_x, tile_y, 0, self.tile_width, sprite=sprite)
                gizmo = create_line_strip(tile.points, WHITE)
                tiles[(col, row)] = tile
                self.grid_gizmo.append(gizmo)
                self.tiles_sprites.append(sprite)
        return tiles

    def iso_grid_to_position(self, gx: int, gy: int, gz: int = 0) -> Tuple[int, int]:
        """Convert isometric grid coordinates (gx, gy) to cartesian coordinates (e.g. mouse cursor position)."""
        x, y = self.first_tile
        pos_x = int(x + (gx - gy) * (self.tile_width * 0.5))
        pos_y = int(y - (gx + gy) * (self.tile_height * 0.5) + gz)
        return pos_x, pos_y

    def pos_to_iso_grid(self, pos_x: int, pos_y: int) -> Tuple[int, int] | None:
        """Convert (x, y) position (e.g. mouse cursor position) to isometric grid coordinates."""
        left, _, bottom, _ = self.window.get_viewport()
        iso_x = pos_x - (self.window.width * 0.5 - left)
        iso_y = -pos_y - bottom + self.window.height
        width = self.tile_width * 0.5
        a, b, c, d = invert_matrix(width, -width, width * 0.5, width * 0.5)
        grid = int(iso_x * a + iso_y * b), int(iso_x * c + iso_y * d)
        return grid if grid in self.tiles else None

    def draw(self, editor_mode: bool = False):
        if editor_mode:
            self.grid_gizmo.draw()
            self.quadtree.draw()
        else:
            self.tiles_sprites.draw()
        for tile in list(self.tiles.values())[:]:
            tile.draw()


class IsometricTile:

    def __init__(self, idx: int, gx: int, gy: int, x: int, y: int, z: int, width: int, sprite: Sprite = None):
        self.idx = idx
        self.gx = gx
        self.gy = gy
        self.x = x
        self.y = y
        self.z = z
        self.width = width
        self._position = x, y = self.x, self.y
        hh, hw = self.width // 4, self.width // 2
        self.points = ((x - hw, y + z), (x, y + hh + z), (x + hw, y + z), (x, y - hh + z), (x - hw, y + z))
        self.width = width
        self.pointed = False
        self._sprite = sprite
        self._adjacent_ids: Optional[List[Tuple[int, int]]] = None
        self._adjacent_tiles: Optional[List[IsometricTile]] = None

    def __str__(self) -> str:
        return f'IsometricTile(idx:{self.idx}, grid:{self.gx},{self.gy}, position:{self.x},{self.y})'

    @property
    def position(self) -> Tuple[int, int]:
        return self.x, self.y

    @position.setter
    def position(self, new_position: Tuple[int, int]):
        self.x, self.y = new_position

    @property
    def adjacent_ids(self) -> List[Tuple[int, int]]:
        if self._adjacent_ids is None:
            self._adjacent_ids = IsometricMap.instance.adjacent_grids(self.gx, self.gy)
        return self._adjacent_ids

    @property
    def adjacent_tiles(self) -> List[IsometricTile]:
        if self._adjacent_tiles is None:
            self._adjacent_tiles = [IsometricMap.instance.tiles[gx, gy] for (gx, gy) in self.adjacent_ids]
        return self._adjacent_tiles

    def draw(self):
        color = GREEN if self.pointed else WHITE
        if self.pointed:
            draw_polygon_filled(self.points, color)


class IsometricWindow(Window):

    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        self.map = IsometricMap(self, width, height, 100)
        self.current_tile = None

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)

    def on_draw(self):
        self.clear()
        self.map.draw(editor_mode=True)

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        if self.current_tile is not None:
            self.current_tile.pointed = False
            self.current_tile = None
        if (grid := self.map.pos_to_iso_grid(x, y)) is not None:
            tile = self.map.tiles.get(grid)
            tile.pointed = True
            self.current_tile = tile

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if self.current_tile is not None:
            print(self.current_tile)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int):
        old_left, _, old_bottom, _ = self.get_viewport()
        new_left = old_left - dx
        new_right = new_left + self.width
        new_bottom = old_bottom - dy
        new_top = new_bottom + self.height
        self.set_viewport(new_left, new_right, new_bottom, new_top)


@dataclass
class Coordinate:
    __slots__ = ['position',]
    position: Tuple[float, float]


if __name__ == '__main__':
    window = IsometricWindow(2000, 1200, "Isometric map")
    run()
