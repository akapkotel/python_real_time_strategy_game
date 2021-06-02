#!/usr/bin/env python

from typing import Optional, Dict, List

from arcade import draw_rectangle_filled, draw_rectangle_outline, draw_point
from arcade.arcade_types import Color

from game import (
    Game, SCREEN_WIDTH, SCREEN_HEIGHT, MINIMAP_WIDTH, MINIMAP_HEIGHT,
    SECTOR_SIZE, TILE_WIDTH, TILE_HEIGHT
)
from utils.colors import WHITE, SAND
from utils.data_types import GridPosition


class MiniMap:
    game: Optional[Game] = None

    def __init__(self):
        self.width = MINIMAP_WIDTH
        self.height = MINIMAP_HEIGHT
        self.position = (SCREEN_WIDTH - MINIMAP_WIDTH // 2, SCREEN_HEIGHT - MINIMAP_HEIGHT // 2)

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
        self.update_drawn_units()
        self.update_revealed_areas()

    def update_position(self, dx, dy):
        _, right, _, top = self.game.viewport
        self.position = (right - 195, top - 95)
        self.update_drawn_areas_positions(dx, dy)
        self.update_viewport()

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
        left = self.position[0] - self.width // 2
        bottom = self.position[1] - self.height // 2
        offset_x = 240 * self.ratio
        offset_y = 160 * self.ratio
        width = SECTOR_SIZE * TILE_WIDTH * self.ratio
        height = SECTOR_SIZE * TILE_HEIGHT * self.ratio
        data = left, bottom, offset_x, offset_y, width, height
        for grid, sector in self.game.map.sectors.items():
            if grid not in self.drawn_area:
                if any(p for p in sector.units_and_buildings):
                    self.reveal_minimap_area(grid, data)

    def update_drawn_areas_positions(self, dx, dy):
        for element in self.drawn_area.values():
            element[0] += dx
            element[1] += dy

    def reveal_minimap_area(self, grid, data):
        left, bottom, offset_x, offset_y, width, height = data
        self.drawn_area[grid] = [
            left + offset_x + grid[0] * width,
            bottom + offset_y + grid[1] * height,
            width,
            height,
            SAND
        ]

    def draw(self):
        # draw revealed map areas:
        for area in self.drawn_area.values():
            draw_rectangle_filled(*area)
        for entity in self.drawn_entities:
            draw_point(*entity)
        # draw current viewport position on the game map:
        draw_rectangle_outline(*self.viewport, color=WHITE)

    def __getstate__(self) -> Dict:
        return {
            'width': self.width,
            'height': self.height,
            'ratio': self.ratio,
            'position': self.position,
            'viewport': self.viewport,
            'drawn_area': self.drawn_area,
            'drawn_entities': self.drawn_entities
        }

    def __setstate__(self, state: Dict):
        self.__dict__.update(state)
