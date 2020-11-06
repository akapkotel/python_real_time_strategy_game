#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, List, Deque, Type
from collections import deque

from arcade.arcade_types import Point

from player import PlayerEntity, Player
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

    @property
    def needs_repair(self) -> bool:
        return self.health < self._max_health

    def update(self):
        super().update()
        if hasattr(self, 'update_production'):
            self.update_production()

    def visible_for(self, other: PlayerEntity) -> bool:
        obstacles = self.game.buildings
        if self.is_building:
            obstacles = [b for b in obstacles if b.id is not self.id]
        distance = self.detection_radius
        return is_visible(self.position, other.position, obstacles, distance)


if __name__:
    from game import Game
