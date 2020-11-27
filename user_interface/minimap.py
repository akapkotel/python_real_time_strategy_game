#!/usr/bin/env python

from typing import Optional, Set, Dict, List

from arcade import draw_rectangle_filled, draw_rectangle_outline, draw_point
from arcade.arcade_types import Color

from game import (
    Game, SCREEN_WIDTH, SCREEN_HEIGHT, MINIMAP_WIDTH, MINIMAP_HEIGHT,
    SECTOR_SIZE, TILE_WIDTH, TILE_HEIGHT
)
from utils.colors import WHITE
from utils.data_types import GridPosition


class MiniMap:
    game: Optional[Game] = None

    def __init__(self):
        self.width = MINIMAP_WIDTH
        self.height = MINIMAP_HEIGHT
        self.position = (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 100)

        if self.height < self.width:
            self.ratio = self.height / self.game.map.height
        else:
            self.ratio = self.width / self.game.map.width

        x, y = self.game.window.screen_center
        self.viewport = [
            self.position[0] - (self.width // 2) + x * self.ratio,
            self.position[1] - (self.height // 2) + y * self.ratio,
            (SCREEN_WIDTH - 400) * self.ratio,
            SCREEN_HEIGHT * self.ratio
        ]

        self.drawn_area: Dict[GridPosition, List] = {}
        self.drawn_entities: List[List[float, float, Color, int]] = []

    def update(self):
        self.update_position()
        self.update_viewport()
        self.update_drawn_units()
        self.update_revealed_areas()

    def update_position(self):
        _, right, _, top = self.game.viewport
        x, y = [p for p in self.position]
        self.position = (right - 195, top - 95)
        dx, dy = self.position[0] - x, self.position[1] - y
        self.update_drawn_areas_positions(dx, dy)

    def update_viewport(self):
        x, y = self.game.window.screen_center
        self.viewport = [
            self.position[0] - (self.width // 2) + x * self.ratio,
            self.position[1] - (self.height // 2) + y * self.ratio,
            (SCREEN_WIDTH - 400) * self.ratio,
            SCREEN_HEIGHT * self.ratio
        ]

    def update_drawn_units(self):
        self.drawn_entities.clear()
        left = self.position[0] - self.width // 2
        bottom = self.position[1] - self.height // 2
        for entity in self.game.local_drawn_units_and_buildings:
            x = left + entity.center_x * self.ratio
            y = bottom + entity.center_y * self.ratio
            size = 4 if entity.is_building else 2
            self.drawn_entities.append([x, y, entity.player.color, size])

    def update_revealed_areas(self):
        for grid, sector in self.game.map.sectors.items():
            if grid not in self.drawn_area:
                if any(p for p in sector.units_and_buildings):
                    self.reveal_minimap_area(grid)

    def update_drawn_areas_positions(self, dx, dy):
        for element in self.drawn_area.values():
            element[0] += dx
            element[1] += dy

    def reveal_minimap_area(self, grid):
        left = self.position[0] - self.width // 2
        bottom = self.position[1] - self.height // 2
        offset_x = 240 * self.ratio
        offset_y = 160 * self.ratio
        width = SECTOR_SIZE * TILE_WIDTH * self.ratio
        height = SECTOR_SIZE * TILE_HEIGHT * self.ratio
        self.drawn_area[grid] = [
            left + offset_x + grid[0] * width,
            bottom + offset_y + grid[1] * height,
            width,
            height,
            WHITE
        ]

    def draw(self):
        # draw revealed map areas:
        for area in self.drawn_area.values():
            draw_rectangle_filled(*area)
        for entity in self.drawn_entities:
            draw_point(*entity)
        # draw current viewport position on the game map:
        draw_rectangle_outline(*self.viewport, color=WHITE)
