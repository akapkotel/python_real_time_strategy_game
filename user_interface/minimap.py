#!/usr/bin/env python

from typing import Optional, Set

from arcade import draw_rectangle_filled, draw_rectangle_outline

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
        self.position = (SCREEN_WIDTH - 195, SCREEN_HEIGHT - 95)
        self.ratio = self.width / self.game.map.width, self.height / self.game.map.height

        x, y = self.game.window.screen_center
        self.viewport = [
            self.position[0] - (self.width // 2) + x * self.ratio[0],
            self.position[1] - (self.height // 2) + y * self.ratio[1],
            (SCREEN_WIDTH - 400) * self.ratio[0],
            SCREEN_HEIGHT * self.ratio[1]
        ]

        self.revealed: Set[GridPosition] = set()

    def update(self):
        self.update_position()
        self.update_viewport()
        self.update_revealed_areas()

    def update_position(self):
        _, right, _, top = self.game.viewport
        self.position = (right - 195, top - 95)

    def update_viewport(self):
        x, y = self.game.window.screen_center
        self.viewport = [
            self.position[0] - (self.width // 2) + x * self.ratio[0],
            self.position[1] - (self.height // 2) + y * self.ratio[1],
            (SCREEN_WIDTH - 400) * self.ratio[0],
            SCREEN_HEIGHT * self.ratio[1]
        ]

    def update_revealed_areas(self):
        for grid, sector in self.game.map.sectors.items():
            if any(p for p in sector.units_and_buildings):
                self.revealed.add(grid)

    def draw(self):
        # draw revealed map areas:
        left = self.position[0] - self.width // 2
        bottom = self.position[1] - self.height // 2
        size_x = 240 * self.ratio[0]
        size_y = 160 * self.ratio[1]
        width = SECTOR_SIZE * TILE_WIDTH * self.ratio[0]
        height = SECTOR_SIZE * TILE_HEIGHT * self.ratio[1]
        for grid in self.revealed:
            draw_rectangle_filled(
                left + size_x + grid[0] * width,
                bottom + size_y + grid[1] * height,
                width,
                height,
                WHITE,
            )

        # draw current viewport position on the game map:
        draw_rectangle_outline(*self.viewport, WHITE)
