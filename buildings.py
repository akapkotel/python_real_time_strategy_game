#!/usr/bin/env python
from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional, Set, Type

from arcade.arcade_types import Point

from data_types import SectorId
from map import MapNode, Sector, TILE_HEIGHT, TILE_WIDTH
from player import Player, PlayerEntity
from utils.functions import is_visible


class IProducer:
    """
    An interface for all Buildings which can produce Units in game.
    """
    produced_objects: Optional[List[Type[PlayerEntity]]] = []
    production_queue: Optional[Deque[PlayerEntity]] = None
    production_progress: float = 0.0
    production_per_frame: float = 0.0
    is_producing: bool = False

    def start_production(self, product: PlayerEntity):
        if product.__class__ not in self.produced_objects:
            return
        elif self.production_queue is None:
            self.production_queue = deque([product])
        else:
            self.production_queue.appendleft(product)
        self.set_production_progress_and_speed(product)

    def cancel_production(self):
        if self.is_producing:
            self.toggle_production()
        self.production_progress = 0.0
        self.production_queue.clear()

    def set_production_progress_and_speed(self, product: PlayerEntity):
        self.production_progress = 0.0
        self.production_per_frame = product.production_per_frame

    def toggle_production(self):
        self.is_producing = not self.is_producing

    def update_production(self):
        if self.is_producing:
            self.production_progress += self.production_per_frame
            if self.production_progress >= 100:
                self.finish_production()
        elif self.production_queue:
            self.start_production(product=self.production_queue[-1])

    def finish_production(self):
        self.toggle_production()
        self.production_progress = 0.0
        self.production_queue.pop()


class Building(PlayerEntity, IProducer):

    def get_sectors_to_scan_for_enemies(self) -> List[Sector]:
        sectors = []
        return sectors

    game: Optional[Game] = None

    def __init__(self,
                 building_name: str,
                 player: Player,
                 position: Point,
                 produces: Optional[PlayerEntity] = None):
        PlayerEntity.__init__(self, building_name, player, position, 4)

        if produces is not None:
            IProducer.__init__(self)
            self.produced_objects.append(produces)

        self.position = self.place_building_properly_on_the_grid()
        self.occupied_nodes: List[MapNode] = self.block_map_nodes()
        for node in self.occupied_nodes:
            self.block_map_node(node)
        self.occupied_sectors: Set[Sector] = self.update_current_sector()

    def place_building_properly_on_the_grid(self) -> Point:
        """
        Buildings positions must be adjusted accordingly to their texture
        width and height so they occupy minimum MapNodes.
        """
        self.position = self.game.map.normalize_position(*self.position)
        offset_x = 0 if (self.width // TILE_WIDTH) % 3 == 0 else TILE_WIDTH // 2
        offset_y = 0 if (self.height // TILE_WIDTH) % 3 == 0 else TILE_HEIGHT // 2
        return self.center_x + offset_x, self.center_y + offset_y

    def block_map_nodes(self) -> List[MapNode]:
        occupied_nodes = set()
        min_x_grid = int(self.left // TILE_WIDTH)
        min_y_grid = int(self.bottom // TILE_HEIGHT)
        max_x_grid = int(self.right // TILE_WIDTH)
        max_y_grid = int(self.top // TILE_HEIGHT)
        for x in range(min_x_grid, max_x_grid):
            for y in range(min_y_grid, max_y_grid):
                node = self.game.map.grid_to_node((x, y))
                occupied_nodes.add(node)
                self.block_map_node(node)
        return list(occupied_nodes)

    @staticmethod
    def unblock_map_node(node: MapNode):
        node.building_id = None

    def block_map_node(self, node: MapNode):
        node.building_id = self.id

    def update_current_sector(self):
        distinct_sectors = set()
        for node in self.occupied_nodes:
            distinct_sectors.add(node.sector)
        for sector in distinct_sectors:
            sector.units_and_buildings.add(self)
        return distinct_sectors

    def update_observed_area(self, *args, **kwargs):
        self.observed_nodes = self.calculate_observed_area()

    @property
    def needs_repair(self) -> bool:
        return self.health < self._max_health

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        if hasattr(self, 'update_production'):
            self.update_production()

    def draw(self):
        super().draw()

    def visible_for(self, other: PlayerEntity) -> bool:
        obstacles = [b for b in self.game.buildings if b.id is not self.id]
        distance = self.detection_radius
        return is_visible(self.position, other.position, obstacles, distance)

    def get_nearby_friends(self) -> Set[PlayerEntity]:
        friends: Set[PlayerEntity] = set()
        for sector in self.occupied_sectors:
            friends.update(
                u for u in sector.units_and_buildings if not
                u.is_enemy(self)
            )
        return friends

    def kill(self):
        for node in self.occupied_nodes:
            self.unblock_map_node(node)
        for sector in (self.game.map.sectors[id] for id in self.occupied_sectors):
            sector.units_and_buildings.discard(self)
        super().kill()


if __name__:
    from game import Game
