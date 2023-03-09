#!/usr/bin/env python
from __future__ import annotations

import random
from collections import deque
from functools import partial
from typing import Deque, List, Optional, Set, Tuple, Dict, Union

from arcade import load_texture, MOUSE_BUTTON_RIGHT
from arcade.arcade_types import Point

from gameobjects.constants import UNITS
from units.units import Soldier, Unit
from effects.sound import UNIT_PRODUCTION_FINISHED
from user_interface.user_interface import (
    ProgressButton, UiElementsBundle, UiElement, Hint, Button, UiTextLabel
)
from campaigns.research import Technology
from map.map import MapNode, normalize_position, position_to_map_grid
from players_and_factions.player import (
    Player, PlayerEntity, STEEL, ELECTRONICS, AMMUNITION, CONSCRIPTS
)
from utils.colors import GREEN, RED
from utils.functions import (
    add_player_color_to_name, get_texture_size, name_to_texture_name,
    get_path_to_file, ignore_in_editor_mode
)
from utils.geometry import find_area, generate_2d_grid
from controllers.constants import CURSOR_ENTER_TEXTURE


# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!
from utils.game_logging import logger


class UnitsProducer:
    """
    An interface for all Buildings which can produce Units in game. Ignore 'Unresolved attribute reference' warnings for
    Player, Game, center_x and center_y attributes - this class would be inherited by Building instance and inheritor
    would provide these attributes for UnitsProducer instance.
    """
    game: Game
    player: Player
    center_x: float
    center_y: float

    def __init__(self, produced_units: Tuple[str]):
        # Units which are available to produce in this Building and their costs in resources:
        self.produced_units: Dict[str, Dict[str: int]] = self.build_units_productions_costs_dict(produced_units)
        self.player.units_possible_to_build.update(produced_units)
        # Queue of Units to be produced
        self.production_queue: Deque[str] = deque()
        # Name of the Unit, which is currently in production, if any:
        self.currently_produced: Optional[str] = None
        self.production_progress: int = 0
        self.production_time: int = 0
        # Where finished Unit would spawn:
        self.spawn_point = self.center_x, self.center_y - 3 * TILE_HEIGHT
        # Point on the Map for finished Units to go after being spawned:
        self.deployment_point = None
        # used to pick one building to produce new units if player has more such factories:
        self.default_producer = sum(1 for b in self.player.buildings if b.produced_units is produced_units) < 2

        if self.player.is_local_human_player:
            self.recreate_ui_units_construction_section()

    def recreate_ui_units_construction_section(self):
        """
        Each time a new UnitsProducer enters the game, UI panel with Units-available for plaer to build must be
        refreshed to contain any new Unit this new Building produces.
        """
        units_construction_bundle = self.game.get_bundle(UI_BUILDINGS_CONSTRUCTION_PANEL)
        self.game.create_units_constructions_options(units_construction_bundle)

    @logger()
    def start_production(self, unit: str):
        if self.player.enough_resources_for(expense=unit):
            self.consume_resources_from_the_pool(unit)
            if self.currently_produced is None:
                self._start_production(unit, confirmation=True)
            self.production_queue.appendleft(unit)

    def _start_production(self, unit: str, confirmation=False):
        self.set_production_progress_and_speed(unit)
        self._toggle_production(produced=unit)
        if self.player.is_local_human_player and confirmation:
            self.game.window.sound_player.play_sound('production_started.wav')

    def consume_resources_from_the_pool(self, unit: str):
        for resource in (STEEL, ELECTRONICS, AMMUNITION, CONSCRIPTS):
            required_amount = self.produced_units[unit][resource]
            self.player.consume_resource(resource, required_amount)

    def cancel_production(self, unit: str):
        """
        First remove scheduled production, if more than 1 Unit is in queue.
        Then, if onl one is produced, cancel current production. Return to the
        pool resources supposed to be used in Unit production.
        """
        if unit in (queue := self.production_queue):
            self.remove_unit_from_production_queue(unit)
            self.return_resources_to_the_pool(unit)
            if unit == self.currently_produced and unit not in queue:
                self._toggle_production(produced=None)
                self.production_progress = 0.0

    def remove_unit_from_production_queue(self, unit):
        self.production_queue.reverse()
        self.production_queue.remove(unit)
        self.production_queue.reverse()

    def return_resources_to_the_pool(self, unit):
        """
        If production was already started, some resources would be lost. Only
        resources 'reserved' for enqueued production are fully returned.
        """
        returned = 1
        if unit not in self.production_queue:
            returned = self.production_progress / self.production_time
        for resource in (STEEL, ELECTRONICS, CONSCRIPTS):
            # required_amount = self.game.configs[UNITS][unit][resource]
            required_amount = self.game.configs[unit][resource]
            self.player.add_resource(resource, required_amount * returned)

    def set_production_progress_and_speed(self, unit: str):
        self.production_progress = 0
        # production_time = self.game.configs[UNITS][unit]['production_time']
        production_time = self.game.configs[unit]['production_time']
        self.production_time = production_time * self.game.settings.fps

    def _toggle_production(self, produced: Optional[str]):
        self.currently_produced = produced

    def update_units_production(self):
        if self.currently_produced is not None:
            self.production_progress += 0.01 * self.health_percentage
            self.update_ui_units_construction_section()
            if int(self.production_progress) == self.production_time:
                self.finish_production(self.production_queue.pop())
        elif self.production_queue:
            self._start_production(unit=self.production_queue[-1])

    def update_ui_units_construction_section(self):
        if  (ui_panel := self.game.get_bundle(UI_BUILDINGS_CONSTRUCTION_PANEL)).elements:
            self.update_production_buttons(ui_panel)

    def update_production_buttons(self, ui_panel: UiElementsBundle):
        for produced in self.produced_units:
            button = ui_panel.find_by_name(produced)
            self.update_single_button(button, produced)

    def update_single_button(self, button: ProgressButton, produced: str):
        button.counter = self.production_queue.count(produced)
        if produced == self.currently_produced:
            button.progress = (self.production_progress / self.production_time) * 100
        else:
            button.progress = 0

    @logger()
    def finish_production(self, finished_unit: str):
        self.production_progress = 0
        self._toggle_production(produced=None)
        self.spawn_finished_unit(finished_unit)
        self.update_ui_units_construction_section()
        if self.player.is_local_human_player:
            self.game.window.sound_player.play_random(UNIT_PRODUCTION_FINISHED)

    def spawn_finished_unit(self, finished_unit: str):
        if (unit := self.game.map.position_to_node(*self.spawn_point).unit) is not None:
            node = self.game.pathfinder.get_closest_walkable_node(*self.spawn_point)
            unit.move_to(node.grid)

        new_unit = self.game.spawn(finished_unit, self.player, self.spawn_point)
        if self.deployment_point is not None:
            new_unit.move_to(self.deployment_point)

    def create_production_buttons(self, x, y) -> List[ProgressButton]:
        production_buttons = []
        positions = generate_2d_grid(x - 135, y - 120, 4, 4, 75, 75)
        for i, unit in enumerate(self.produced_units):
            column, row = positions[i]
            b = ProgressButton(unit + '_icon.png', column, row, unit,
                               functions=partial(self.start_production, unit)).\
                add_hint(Hint(unit + '_production_hint.png', required_delay=0.5))
            b.bind_function(partial(self.cancel_production, unit), MOUSE_BUTTON_RIGHT)
            production_buttons.append(b)
        return production_buttons

    def save(self) -> Dict:
        return {
            'production_progress': self.production_progress,
            'currently_produced': self.currently_produced,
            'production_time': self.production_time,
        }

    def after_respawn(self, state: Dict):
        self.production_progress = state['production_progress']
        self.currently_produced = state['currently_produced']
        self.production_time = state['production_time']

    def build_units_productions_costs_dict(self, produced_units: Tuple[str]) -> Dict[str, Dict[str: int]]:
        # configs = self.game.configs[UNITS]
        configs = self.game.configs
        resources = (STEEL, ELECTRONICS, AMMUNITION, CONSCRIPTS)
        units_production_costs = {
            unit: {resource: configs[unit][resource] for resource in resources} for unit in produced_units
        }
        return units_production_costs


class ResourceProducer:
    def __init__(self,
                 extracted_resource: str,
                 require_transport: bool = False,
                 recipient: Optional[Player] = None):
        self.resource: str = extracted_resource
        self.require_transport = require_transport
        self.yield_per_frame = value = 0.033
        self.reserves = 0.0
        self.stockpile = 0.0
        self.recipient: Optional[Player] = recipient
        self.recipient.change_resource_yield_per_second(self.resource, value)

    def update_resource_production(self):
        self.reserves -= self.yield_per_frame
        if self.recipient is None:
            self.stockpile += self.yield_per_frame

    def save(self) -> Dict:
        return {}

    def after_respawn(self, state):
        print('resource extractor __setstate__')
        # TODO


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

    def save(self) -> Dict:
        if self.researched_technology is None:
            return {'funding': self.funding, 'researched_technology': None}
        return {
            'funding': self.funding,
            'researched_technology': self.researched_technology.name
        }

    def after_respawn(self, state: Dict):
        print('research facility __setstate__')
        self.__dict__.update(state)
        if (tech_name := state['researched_technology']) is not None:
            self.researched_technology = self.owner.game.window.configs[tech_name]


class Building(PlayerEntity, UnitsProducer, ResourceProducer, ResearchFacility):
    game: Optional[Game] = None

    def __init__(self,
                 building_name: str,
                 player: Player,
                 position: Point,
                 id: Optional[int] = None,
                 produced_units: Optional[Tuple[str]] = None,
                 produced_resource: Optional[str] = None,
                 research_facility: bool = False,
                 garrison: int = 0):
        """
        :param building_name: str -- texture name
        :param player: Player -- which player controlls this building
        :param position: Point -- coordinates of the center (x, y)
        :param produces:
        """
        PlayerEntity.__init__(self, building_name, player, position, 4, id)
        self.produced_units = produced_units
        self.produced_resource = produced_resource
        self.research_facility = research_facility

        if produced_units is not None:
            UnitsProducer.__init__(self, produced_units)
        elif produced_resource is not None:
            ResourceProducer.__init__(self, produced_resource, False, self.player)
        elif research_facility:
            ResearchFacility.__init__(self, self.player)

        self.energy_consumption = self.configs['energy_consumption']

        self.position = self.place_building_properly_on_the_grid()
        self.occupied_nodes: Set[MapNode] = self.block_map_nodes()

        self.garrisoned_soldiers: List[Union[Soldier, int]] = []
        self.garrison_size: int = self.configs['garrison_size']

        if garrison:
            self.spawn_soldiers_for_garrison(garrison)

        self.layered_spritelist.swap_rendering_layers(
            self, 0, position_to_map_grid(*self.position)[1]
        )

    @property
    def is_selected(self) -> bool:
        return self.game.units_manager.selected_building is self

    def place_building_properly_on_the_grid(self) -> Point:
        """
        Buildings positions must be adjusted accordingly to their texture
        width and height so they occupy minimum MapNodes.
        """
        self.position = normalize_position(*self.position)
        offset_x = 0 if not (self.width // TILE_WIDTH) % 3 else TILE_WIDTH // 2
        offset_y = 0 if not (self.height // TILE_HEIGHT) % 3 else TILE_HEIGHT // 2
        return self.center_x + offset_x, self.center_y + offset_y

    def block_map_nodes(self) -> Set[MapNode]:
        min_x_grid = int(self.left // TILE_WIDTH)
        min_y_grid = int(self.bottom // TILE_HEIGHT)
        max_x_grid = int(self.right // TILE_WIDTH)
        max_y_grid = int(self.top // TILE_HEIGHT)
        occupied_nodes = {
            self.game.map.grid_to_node((x, y)) for x in
            range(min_x_grid, max_x_grid) for y in
            range(min_y_grid, max_y_grid - 1)
        }
        for node in occupied_nodes:
            node.remove_tree()
            self.block_map_node(node)
        return set(occupied_nodes)

    def spawn_soldiers_for_garrison(self, number_of_soldiers: int):
        """Called when Building is spawned with garrisoned Soldiers inside."""
        for _ in range(min(number_of_soldiers, self.garrison_size)):
            soldier: Soldier = self.game.spawn('soldier', self.player, self.map.random_walkable_node.position)
            soldier.enter_building(self)

    @property
    def moving(self) -> bool:
        return False  # this is rather obvious, this is a Building

    @staticmethod
    def unblock_map_node(node: MapNode):
        node.building = None

    def block_map_node(self, node: MapNode):
        node.building = self

    def update_observed_area(self, *args, **kwargs):
        if not self.observed_nodes:  # Building need calculate it only once
            self.observed_grids = grids = self.calculate_observed_area()
            self.observed_nodes = {self.map[grid] for grid in grids}
            # if self.weapons:
            #     self.update_fire_covered_area()

    def update_fire_covered_area(self):
        x, y = position_to_map_grid(*self.position)
        area = find_area(x, y, self.attack_range_matrix)
        self.fire_covered = {self.map[grid] for grid in area}

    @ignore_in_editor_mode
    def update_battle_behaviour(self):
        pass

    def on_mouse_enter(self):
        if self.selection_marker is None:
            self.game.units_manager.create_building_selection_marker(self)
            if self.game.units_manager.only_soldiers_selected:
                self.check_soldiers_garrisoning_possibility()

    def check_soldiers_garrisoning_possibility(self):
        friendly_building = self.is_controlled_by_player
        free_space = len(self.garrisoned_soldiers) < self.garrison_size
        if (friendly_building and free_space) or not friendly_building:
            self.game.cursor.force_cursor(index=CURSOR_ENTER_TEXTURE)

    def on_mouse_exit(self):
        selected_building = self.game.units_manager.selected_building
        if self.selection_marker is not None and self is not selected_building:
            self.game.units_manager.remove_from_selection_markers(entity=self)
        if self.game.cursor.forced_cursor == CURSOR_ENTER_TEXTURE:
            self.game.cursor.force_cursor(index=None)

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        self.update_production()
        self.update_observed_area()
        self.update_ui_buildings_panel()

    def update_production(self):
        if self.produced_units is not None:
            self.update_units_production()
        elif self.produced_resource is not None:
            self.update_resource_production()
        elif self.research_facility:
            self.update_research()

    @ignore_in_editor_mode
    def update_ui_buildings_panel(self):
        if self.is_selected:
            panel = self.game.get_bundle(UI_BUILDINGS_PANEL)
            panel.find_by_name('health').text = f'HP: {round(self.health)} / {self.max_health}'

            if self.is_controlled_by_player and self.produced_units is not None:
                self.update_production_buttons(panel)

    def create_ui_elements(self, x, y) -> List[UiElement]:
        """
         Each time Building is clicked by the player, this method generates all icons and buttons required for player
         to inspect and manage his Building.

        :param x: float -- x component of user interface position
        :param y: float -- y component of user interface position
        :return: List[uiElement] -- buttons, icons and widgets available for this Building
        """
        ui_elements = self.create_building_ui_information(x, y)
        if self.is_controlled_by_player:
            buttons = self.create_ui_buttons(x, y)
            ui_elements.extend(buttons)
        return ui_elements

    def create_building_ui_information(self, x, y) -> List[UiElement]:
        text_color = GREEN if self.is_controlled_by_player else RED
        return [
            UiTextLabel(x + 25, y + 50, self.object_name.replace('_', ' ').title(), 15, text_color, name='building_name'),
            UiTextLabel(x + 5, y + 15, f'HP: {round(self.health)} / {self.max_health}', 12, text_color, name='health')
        ]

    def create_ui_buttons(self, x, y) -> List[Button]:
        buttons = [self.create_garrison_button(x, y)]
        if self.produced_units is not None:
            buttons.extend(self.create_production_buttons(x, y))
        return buttons

    def create_garrison_button(self, x, y) -> ProgressButton:
        button = ProgressButton(
            'ui_leave_building_btn.png', x - 135, y - 45, 'leave',
            active=len(self.garrisoned_soldiers) > 0,
            functions=self.on_soldier_exit
        )
        button.counter = len(self.garrisoned_soldiers)
        return button

    @property
    def count_empty_garrison_slots(self) -> int:
        """Check if more Soldiers can enter this building."""
        return self.garrison_size - len(self.garrisoned_soldiers)

    def on_soldier_enter(self, soldier: Soldier):
        if self.is_enemy(soldier):
            self.on_enemy_soldier_breach(soldier)
        else:
            self.put_soldier_into_garrison(soldier)
        self.update_garrison_button()

    def on_enemy_soldier_breach(self, soldier: Soldier):
        if garrison := self.garrisoned_soldiers:
            soldier.kill()
            if random.random() > len(garrison) / self.garrison_size:
                garrison.pop().kill()
        else:
            self.takeover_building(soldier=soldier)

    def put_soldier_into_garrison(self, soldier: Soldier):
        soldier.remove_from_map_quadtree()
        self.garrisoned_soldiers.append(soldier)
        soldier.position = self.position

    def takeover_building(self, soldier: Soldier):
        if soldier.player.is_local_human_player:
            self.game.sound_player.play_sound('enemy_building_captured.vaw')
        self.put_soldier_into_garrison(soldier=soldier)
        path_and_texture, size = self.find_proper_texture(soldier.player)
        self.change_building_texture(path_and_texture, size)
        self.reconfigure_building(soldier.player)

    def find_proper_texture(self, player) -> Tuple[str, Tuple]:
        recolored = add_player_color_to_name(self.object_name, player.color)
        texture_name = name_to_texture_name(recolored)
        size = get_texture_size(texture_name)
        path_and_texture = get_path_to_file(texture_name)
        return path_and_texture, size

    def change_building_texture(self, path_and_texture, size):
        self.textures = [load_texture(path_and_texture, 0, 0, *size)]
        self.set_texture(0)

    def reconfigure_building(self, player: Player):
        self.clear_known_enemies()
        self.remove_from_map_quadtree()
        self.change_player(player)
        self.refresh_occupied_nodes()
        self.insert_to_map_quadtree()

    def clear_known_enemies(self):
        # self.player.remove_known_enemies(self.id, self.known_enemies)
        self.known_enemies.clear()

    def change_player(self, player):
        self.detach(self.player)
        self.attach(player)

    def refresh_occupied_nodes(self):
        self.unblock_occupied_nodes()
        self.occupied_nodes = self.block_map_nodes()

    def update_garrison_button(self):
        if self.player.is_local_human_player and self.is_selected:
            button = self.game.get_bundle(UI_BUILDINGS_PANEL).find_by_name('leave')
            button.counter = soldiers_count = len(self.garrisoned_soldiers)
            button.toggle(state=soldiers_count > 0)

    def on_soldier_exit(self):
        try:
            soldier = self.garrisoned_soldiers.pop()
            soldier.leave_building(self)
        except IndexError:
            pass
        finally:
            self.update_garrison_button()

    def on_being_damaged(self, damage: float, penetration: float = 0) -> bool:
        # TODO: killing personnel inside Building
        return super().on_being_damaged(damage)

    def kill(self):
        if self.garrisoned_soldiers:
            self.kill_garrisoned_soldiers()
        self.unblock_occupied_nodes()
        super().kill()

    def unblock_occupied_nodes(self):
        for node in self.occupied_nodes:
            self.unblock_map_node(node)

    def kill_garrisoned_soldiers(self):
        for soldier in self.garrisoned_soldiers:
            soldier.kill()
        self.garrisoned_soldiers.clear()

    def save(self) -> Dict:
        saved_building = super().save()

        if self.produced_units is not None:
            saved_building.update(UnitsProducer.save(self))
        elif self.produced_resource is not None:
            saved_building.update(ResourceProducer.save(self))
        elif self.research_facility:
            saved_building.update(ResearchFacility.save(self))
        if self.garrisoned_soldiers:
            saved_building.update(self.save_garrison())
        return saved_building

    def save_garrison(self) -> Dict:
        return {'garrisoned_soldiers': [s.id for s in self.garrisoned_soldiers]}

    def after_respawn(self, loaded_data: Dict):
        super().after_respawn(loaded_data)
        if self.produced_units is not None:
            UnitsProducer.after_respawn(self, loaded_data)
        if self.produced_resource is not None:
            ResourceProducer.after_respawn(self, loaded_data)
        if self.research_facility:
            ResearchFacility.after_respawn(self, loaded_data)
        if self.garrisoned_soldiers:
            self.load_garrison()

    def load_garrison(self):
        identifiers: List[int] = [s for s in self.garrisoned_soldiers]
        self.garrisoned_soldiers.clear()
        soldier: Soldier
        for soldier in (self.game.find_gameobject(Unit, s) for s in identifiers):
            soldier.enter_building(self)


class ConstructionSite(Building):

        def __init__(self, x, y, building_name: str, player: Player, position: Point):
            super().__init__('construction_site', player, position)
            self.constructed_building = building_name


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from game import Game
    from map.constants import TILE_WIDTH, TILE_HEIGHT
    from user_interface.constants import UI_BUILDINGS_PANEL, UI_BUILDINGS_CONSTRUCTION_PANEL
