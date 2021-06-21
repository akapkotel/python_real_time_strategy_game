#!/usr/bin/env python
from __future__ import annotations

from collections import deque
from functools import partial
from typing import Deque, List, Optional, Set, Tuple, Dict

from arcade.arcade_types import Point

from effects.sound import UNIT_PRODUCTION_FINISHED
from user_interface.user_interface import ProgressButton
from missions.research import Technology
from map.map import MapNode, Sector, normalize_position
from players_and_factions.player import (
    Player, PlayerEntity, ENERGY, STEEL, ELECTRONICS, CONSCRIPTS
)
from utils.functions import ignore_in_editor_mode
from utils.geometry import close_enough, is_visible


# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!
from utils.logging import logger


class UnitsProducer:
    """
    An interface for all Buildings which can produce Units in game.
    """

    def __init__(self, produced_units: Tuple[str]):
        self.produced_units = produced_units
        self.production_queue: Deque[str] = deque()
        self.currently_produced: Optional[str] = None
        self.production_progress: int = 0
        self.production_time: int = 0
        self.deployment_point = self.center_x, self.center_y - 120

    @logger(console=True)
    def start_production(self, unit: str):
        if unit in self.produced_units and self.enough_resources(unit):
            if self.currently_produced is None:
                self._start_production(unit, confirmation=True)
            self.production_queue.appendleft(unit)

    def enough_resources(self, unit: str) -> bool:
        for resource in (ENERGY, STEEL, ELECTRONICS, CONSCRIPTS):
            required_amount = self.game.configs['units'][unit][resource]
            if not self.player.has_resource(resource, required_amount):
                self.player.notify_player_of_resource_deficit(resource)
                return False
        return True

    def _start_production(self, unit: str, confirmation=False):
        self.set_production_progress_and_speed(unit)
        self.consume_resources(unit)
        self._toggle_production(produced=unit)
        if confirmation:
            self.game.window.sound_player.play_sound('production_started.wav')

    def consume_resources(self, unit: str):
        for resource in (ENERGY, STEEL, ELECTRONICS, CONSCRIPTS):
            required_amount = self.game.configs['units'][unit][resource]
            self.player.consume_resource(resource, required_amount)

    def cancel_production(self):
        if self.currently_produced:
            self._toggle_production(produced=None)
        self.production_progress = 0.0
        self.production_queue.clear()

    def set_production_progress_and_speed(self, product: str):
        self.production_progress = 0
        production_time = self.game.configs['units'][product]['production_time']
        self.production_time = production_time * self.game.settings.fps

    def _toggle_production(self, produced):
        self.currently_produced = produced

    def update_units_production(self):
        if self.currently_produced is not None:
            self.production_progress += 1
            self.update_production_button(progress=self.production_progress)
            if self.production_progress == self.production_time:
                self.finish_production(self.production_queue.pop())
        elif self.production_queue:
            self._start_production(unit=self.production_queue[-1])

    def update_production_button(self, progress):
        if (panel := self.game.get_bundle(BUILDINGS_PANEL)).displayed:
            production_button = panel.find_by_name(self.currently_produced)
            production_button.progress = (progress / self.production_time) * 100

    @logger(console=True)
    def finish_production(self, finished_unit: str):
        self.production_progress = progress = 0
        self.update_production_button(progress)
        self._toggle_production(produced=None)
        self.game.spawn(finished_unit, self.player, self.deployment_point)
        self.game.window.sound_player.play_random(UNIT_PRODUCTION_FINISHED)

    def create_production_buttons(self, x, y) -> List[ProgressButton]:
        production_buttons = []
        for i, unit in enumerate(self.produced_units):
            b = ProgressButton(unit + '_icon.png', x, y + 50 * i, unit,
                               functions=partial(self.start_production, unit))
            production_buttons.append(b)
        return production_buttons

    def __getstate__(self) -> Dict:
        return {}

    def __setstate__(self, state):
        self.__dict__.update(state)


class ResourceProducer:
    def __init__(self,
                 extracted_resource: str,
                 require_transport: bool = False,
                 recipient: Optional[Player] = None):
        self.resource: str = extracted_resource
        self.require_transport = require_transport
        self.yield_per_frame = 0.033
        self.reserves = 0.0
        self.stockpile = 0.0
        self.recipient: Optional[Player] = recipient
        self.recipient.change_resource_yield_per_frame()

    def update_resource_production(self):
        self.reserves -= self.yield_per_frame
        if self.recipient is None:
            self.stockpile += self.yield_per_frame

    def __getstate__(self) -> Dict:
        return {}

    def __setstate__(self, state):
        self.__dict__.update(state)


class ResearchFacility:

    def __init__(self, owner: Player):
        self.owner = owner
        self.funding = 0
        self.researched_technology: Optional[Technology] = None

    def start_research(self, technology: Technology):
        if self.owner.knows_all_required(technology.required):
            self.researched_technology = technology

    def update_research(self):
        if technology := self.researched_technology is None:
            return
        progress = self.funding / technology.difficulty if self.funding else 0
        tech_id = technology.id
        total_progress = self.owner.current_research.get(tech_id, 0) + progress
        self.owner.current_research[tech_id] = total_progress
        if total_progress > 100:
            self.finish_research(technology)

    def finish_research(self, technology: Technology):
        self.researched_technology = None
        self.owner.update_known_technologies(technology)

    def __getstate__(self) -> Dict:
        if self.researched_technology is None:
            return {'funding': self.funding, 'researched_technology': None}
        return {
            'funding': self.funding,
            'researched_technology': self.researched_technology.name
        }

    def __setstate__(self, state: Dict):
        self.__dict__.update(state)
        if (tech_name := state['researched_technology']) is not None:
            self.researched_technology = self.owner.game.window.configs[
                'technologies'][tech_name]


class Building(PlayerEntity, UnitsProducer, ResourceProducer, ResearchFacility):

    game: Optional[Game] = None

    def __init__(self,
                 building_name: str,
                 player: Player,
                 position: Point,
                 id: Optional[int] = None,
                 produced_units: Optional[Tuple[str]] = None,
                 produced_resource: Optional[str] = None,
                 research_facility: bool = False):
        """
        :param building_name: str -- texture name
        :param player: Player -- which player controlls this building
        :param position: Point -- coordinates of the center (x, y)
        :param produces:
        """
        PlayerEntity.__init__(self, building_name, player, position, 4, id)
        self.is_units_producer = produced_units is not None
        self.is_resource_producer = produced_resource is not None
        self.is_research_facility = research_facility

        if produced_units is not None:
            UnitsProducer.__init__(self, produced_units)
        elif produced_resource is not None:
            ResourceProducer.__init__(self, produced_resource, False, self.player)
        elif research_facility:
            ResearchFacility.__init__(self, self.player)

        # since buildings could be large, they must be visible for anyone
        # who can see their boundaries, not just the center_xy:
        self.detection_radius += self._get_collision_radius()

        self.position = self.place_building_properly_on_the_grid()
        self.occupied_nodes: List[MapNode] = self.block_map_nodes()
        self.occupied_sectors: Set[Sector] = self.update_current_sector()

    @property
    def configs(self):
        return self.game.configs['buildings'][self.object_name]

    def place_building_properly_on_the_grid(self) -> Point:
        """
        Buildings positions must be adjusted accordingly to their texture
        width and height so they occupy minimum MapNodes.
        """
        self.position = normalize_position(*self.position)
        offset_x = 0 if (self.width // TILE_WIDTH) % 3 == 0 else TILE_WIDTH // 2
        offset_y = 0 if (self.height // TILE_HEIGHT) % 3 == 0 else TILE_HEIGHT // 2
        return self.center_x + offset_x, self.center_y + offset_y

    def block_map_nodes(self) -> List[MapNode]:
        min_x_grid = int(self.left // TILE_WIDTH)
        min_y_grid = int(self.bottom // TILE_HEIGHT)
        max_x_grid = int(self.right // TILE_WIDTH)
        max_y_grid = int(self.top // TILE_HEIGHT)
        occupied_nodes = {
            self.game.map.grid_to_node((x, y)) for x in
            range(min_x_grid, max_x_grid + 1) for y in
            range(min_y_grid, max_y_grid)
        }
        [self.block_map_node(node) for node in occupied_nodes]
        return list(occupied_nodes)

    @property
    def moving(self) -> bool:
        return False

    @staticmethod
    def unblock_map_node(node: MapNode):
        node.building = None

    def block_map_node(self, node: MapNode):
        node.building = self

    def update_current_sector(self) -> Set[Sector]:
        distinct_sectors = {node.sector for node in self.occupied_nodes}
        for sector in distinct_sectors:
            sector.units_and_buildings[self.player.id].add(self)
        return distinct_sectors

    def update_observed_area(self, *args, **kwargs):
        self.observed_nodes = nodes = self.calculate_observed_area()
        self.game.fog_of_war.reveal_nodes({n.grid for n in nodes})

    @ignore_in_editor_mode
    def update_fighting(self):
        if self.weapons:
            # TODO: buildings with machine-guns and personnel fighting back
            raise NotImplementedError

    def on_mouse_enter(self):
        if self.selection_marker is None:
            self.game.units_manager.create_building_selection_marker(self)

    def on_mouse_exit(self):
        selected_building = self.game.units_manager.selected_building
        if self.selection_marker is not None and self is not selected_building:
            self.game.units_manager.remove_from_selection_markers(self)

    def on_update(self, delta_time: float = 1/60):
        if self.alive:
            super().on_update(delta_time)
            self.update_production()
            self.update_observed_area()
        else:
            self.kill()

    def update_production(self):
        if self.is_units_producer:
            self.update_units_production()
        elif self.is_resource_producer:
            self.update_resource_production()
        elif self.is_research_facility:
            self.update_research()

    def visible_for(self, other: PlayerEntity) -> bool:
        obstacles = [b for b in self.game.buildings if b.id is not self.id]
        if close_enough(self.position, other.position, self.detection_radius):
            return is_visible(self.position, other.position, obstacles)
        return False

    def get_nearby_friends(self) -> Set[PlayerEntity]:
        friends: Set[PlayerEntity] = set()
        for sector in self.occupied_sectors:
            friends.update(u for u in sector.units_and_buildings[self.player.id])
        return friends

    def get_sectors_to_scan_for_enemies(self) -> List[Sector]:
        sectors = set()
        for sector in self.occupied_sectors:
            sectors.update(sector.adjacent_sectors())
        return list(sectors)

    def on_soldier_enter(self, soldier):
        raise NotImplementedError

    def on_being_damaged(self, damage: float) -> bool:
        damage *= self.game.settings.buildings_damage_factor
        return super().on_being_damaged(damage)

    def kill(self):
        for node in self.occupied_nodes:
            self.unblock_map_node(node)
        for sector in self.occupied_sectors:
            sector.discard_entity(self)
        super().kill()

    def save(self) -> Dict:
        saved_building = super().save()
        if self.is_units_producer:
            saved_building.update(UnitsProducer.__getstate__(self))
        if self.is_resource_producer:
            saved_building.update(ResourceProducer.__getstate__(self))
        if self.is_research_facility:
            saved_building.update(ResearchFacility.__getstate__(self))
        return saved_building


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from game import Game, TILE_HEIGHT, TILE_WIDTH, BUILDINGS_PANEL
