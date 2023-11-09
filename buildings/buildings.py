#!/usr/bin/env python
from __future__ import annotations

import random
from collections import deque
from functools import partial
from pathlib import Path
from typing import Deque, List, Optional, Set, Tuple, Dict, Union, Iterable

from arcade import load_texture, MOUSE_BUTTON_RIGHT
from arcade.arcade_types import Point

from units.units import Soldier, Unit
from effects.sound import UNIT_PRODUCTION_FINISHED
from user_interface.user_interface import (
    ProgressButton, UiElementsBundle, UiElement, Button, UiTextLabel, UnitProductionCostsHint
)
from campaigns.research import Technology
from map.map import IsometricMap, normalize_position, position_to_map_grid
from players_and_factions.player import (
    Player, PlayerEntity
)
from utils.views import ProgressBar
from utils.colors import GREEN, RED, BLACK, CONSTRUCTION_BAR_COLOR
from utils.functions import (
    add_player_color_to_name, get_texture_size,
    get_path_to_file, ignore_in_editor_mode, add_extension
)
from utils.geometry import generate_2d_grid
from utils.constants import CURSOR_ENTER_TEXTURE, TILE_WIDTH, TILE_HEIGHT, FUEL, AMMUNITION, ENERGY, STEEL, ELECTRONICS, \
    CONSCRIPTS, UI_BUILDINGS_PANEL, UI_UNITS_CONSTRUCTION_PANEL, CONSTRUCTION_SITE

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!
from utils.game_logging import log_this_call


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
        self.player.units_possible_to_build.extend(produced_units)
        # Queue of Units to be produced
        self.production_queue: Deque[str] = deque()
        # Name of the Unit, which is currently in production, if any:
        self.currently_produced: Optional[str] = None
        self.production_progress: int = 0
        self.production_time: int = 0
        # Where finished Unit would spawn:
        self.spawn_point = self.center_x, self.bottom
        # Point on the Map for finished Units to go after being spawned:
        self.deployment_point = None
        # used to decide if this building should be default producer of units if player has more such factories:
        self.default_producer = sum(1 for b in self.player.buildings if b.produced_units is produced_units) < 2

    def build_units_productions_costs_dict(self, produced_units: Tuple[str]) -> Dict[str, Dict[str: int]]:
        return {
            unit: {resource: self.game.configs[unit][resource]
                   for resource in (STEEL, ELECTRONICS, AMMUNITION, FUEL, CONSCRIPTS)}
            for unit in produced_units
        }

    @log_this_call()
    def start_production(self, unit_name: str):
        costs = self.produced_units[unit_name]
        if self.player.enough_resources_for(expense=unit_name, costs=costs):
            self.consume_resources_from_the_pool(unit_name)
            if self.currently_produced is None:
                self._start_production(unit_name, confirmation=True)
            self.production_queue.appendleft(unit_name)

    def _start_production(self, unit_name: str, confirmation=False):
        self.set_production_progress_and_speed(unit_name)
        self._set_currently_produced_to(unit_name)
        if self.player.is_local_human_player:
            self.update_ui_units_construction_section()
            if confirmation:
                self.game.window.sound_player.play_sound('production_started.wav')

    def consume_resources_from_the_pool(self, unit_name: str):
        for resource in (STEEL, ELECTRONICS, AMMUNITION, CONSCRIPTS):
            required_amount = self.produced_units[unit_name][resource]
            self.player.consume_resource(resource, required_amount)

    def cancel_production(self, unit_name: str):
        if unit_name in (queue := self.production_queue):
            self.return_resources_to_the_pool(unit_name)
            self.production_queue.remove(unit_name)
            if unit_name == self.currently_produced and unit_name not in queue:
                self._set_currently_produced_to(None)
                self.production_progress = 0.0
        if self.player.is_local_human_player:
            self.update_ui_units_construction_section()

    def return_resources_to_the_pool(self, unit_name: str):
        """
        If production was already started, some resources would be lost. Only
        resources 'reserved' for enqueued production are fully returned.
        """
        if unit_name in self.production_queue:
            returned = 1
        else:
            returned = self.production_time - self.production_progress
        for resource in (STEEL, ELECTRONICS, AMMUNITION, FUEL, CONSCRIPTS):
            required_amount = self.produced_units[unit_name][resource]
            self.player.add_resource(resource, required_amount * returned)

    def set_production_progress_and_speed(self, unit_name: str):
        self.production_progress = 0
        production_time = self.game.configs[unit_name]['production_time']
        self.production_time = self.instant_production or production_time

    @property
    def instant_production(self) -> bool:
        return self.game.settings.instant_production_time and self.is_controlled_by_player

    def _set_currently_produced_to(self, produced: Optional[str]):
        self.currently_produced = produced

    def update_units_production(self, delta_time: float):
        if self.currently_produced is not None and self.is_powered:
            self.production_progress += (self.health_ratio * self.power_ratio * delta_time)
            if self.player.is_local_human_player:
                self.update_ui_units_construction_section()
            if self.production_progress >= self.production_time:
                self.finish_production(self.production_queue.pop())
        elif self.production_queue:
            self._start_production(unit_name=self.production_queue[-1])

    def update_ui_units_construction_section(self):
        if (ui_panel := self.game.get_bundle(UI_UNITS_CONSTRUCTION_PANEL)).elements:
            self.update_production_buttons(ui_panel)

    def update_production_buttons(self, ui_panel: UiElementsBundle):
        for produced in self.produced_units:
            if (button := ui_panel.find_by_name(produced)) is not None:
                self.update_single_button(button, produced)

    def update_single_button(self, button: ProgressButton, produced: str):
        button.counter = self.production_queue.count(produced)
        if produced == self.currently_produced:
            button.progress = (self.production_progress / self.production_time) * 100
        else:
            button.progress = 0

    @log_this_call()
    def finish_production(self, finished_unit_name: str):
        self.production_progress = 0
        self._set_currently_produced_to(None)
        self.clear_spawning_point_for_new_unit()
        self.spawn_finished_unit(finished_unit_name)
        if self.player.is_local_human_player:
            self.update_ui_units_construction_section()
            self.game.window.sound_player.play_random_sound(UNIT_PRODUCTION_FINISHED)

    def clear_spawning_point_for_new_unit(self):
        if (unit := self.game.map.position_to_node(*self.spawn_point).unit) is not None:
            node = self.game.pathfinder.get_closest_walkable_node(*self.spawn_point)
            unit.move_to(node.grid)

    def spawn_finished_unit(self, finished_unit_name: str):
        new_unit = self.game.spawn(finished_unit_name, self.player, self.spawn_point)
        if self.deployment_point is not None:
            new_unit.move_to(self.deployment_point)

    def create_production_buttons(self, x, y) -> List[ProgressButton]:
        production_buttons = []
        positions = generate_2d_grid(x - 135, y - 120, 4, 4, 75, 75)
        for i, unit_name in enumerate(self.produced_units):
            column, row = positions[i]
            hint = UnitProductionCostsHint(self.player, self.produced_units[unit_name], delay=0.5)
            b = ProgressButton(f'{unit_name}_icon.png', column, row, unit_name,
                               functions=partial(self.start_production, unit_name)).add_hint(hint)
            b.bind_function(partial(self.cancel_production, unit_name), MOUSE_BUTTON_RIGHT)
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


class ResourceProducer:
    def __init__(self, produced_resource: str):
        self.produced_resource = produced_resource
        self.yield_per_second = 0.5
        self.reserves = 0.0
        self.stockpile = 0.0
        self.max_stockpile = 500

    @property
    def energy_production(self) -> float:
        # I decided that energy-production formula should be simple, and it is: bigger the power plant, more energy it
        # produces, and 'health' also allows us to consider current damage the power plant took, which lowers yield
        return self.health

    def update_resource_production(self, delta_time: float):
        produced_amount = self.yield_per_second * delta_time * self.power_ratio
        self.player.add_resource(self.produced_resource, produced_amount)
        self.reserves -= min(produced_amount, self.reserves)

    def save(self) -> Dict:
        return {}

    def after_respawn(self, state):
        ...


class ResearchFacility:
    optimal_scientists_per_technology = 6

    def __init__(self):
        self.scientists = 3
        self.max_scientists = 12
        self.scientists_per_technology = 0
        self.funding = 0
        self.required_funding = 0
        self.researched_technologies: Dict[Technology, float] = {}
        self.researched_technology = None

    def start_research(self, technology: Technology):
        if self.player.knows_all_required(technology.required):
            self.researched_technologies[technology] = 0
            self.required_funding += technology.funding_cost
            self.update_scientists_efficiency()

    def update_scientists_efficiency(self):
        self.scientists_per_technology = (self.scientists / len(
            self.researched_technologies)) / self.optimal_scientists_per_technology

    def change_funding(self, value: int):
        self.funding += value

    def update_research(self, delta_time: float):
        if not self.researched_technologies:
            return
        finished_technologies = []
        for technology in self.researched_technologies:
            funding_factor = (self.funding / self.required_funding)
            power_factor = 1
            progress = (self.scientists_per_technology * funding_factor * power_factor) / technology.difficulty
            total_progress = self.researched_technologies.get(technology, 0) + (progress * delta_time)
            if total_progress >= 100:
                finished_technologies.append(technology)
            else:
                self.researched_technologies[technology] = total_progress
        self.finish_research(finished_technologies)

    def finish_research(self, finished_technologies: Iterable[Technology]):
        for technology in finished_technologies:
            del self.researched_technologies[technology]
            self.required_funding -= technology.funding_cost
            self.owner.update_known_technologies(technology)
        self.update_scientists_efficiency()

    def save(self) -> Dict:
        if self.researched_technology is None:
            return {'funding': self.funding, 'researched_technology': None}
        return {
            'funding': self.funding,
            'researched_technology': self.researched_technology.name
        }

    def after_respawn(self, state: Dict):
        self.__dict__.update(state)
        if (tech_name := state['researched_technology']) is not None:
            self.researched_technology = self.owner.game.window.configs[tech_name]


class Building(PlayerEntity, UnitsProducer, ResourceProducer, ResearchFacility):
    game: Optional[Game] = None

    def __init__(self,
                 building_name: str,
                 player: Player,
                 position: Point,
                 object_id: Optional[int] = None,
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
        PlayerEntity.__init__(self, building_name, player, position, object_id)
        self.produced_units = produced_units
        self.produced_resource = produced_resource
        self.research_facility = research_facility

        if produced_units is not None:
            UnitsProducer.__init__(self, produced_units)
        if produced_resource is not None:
            ResourceProducer.__init__(self, produced_resource)
        if research_facility:
            ResearchFacility(building=self)

        if object_id is None:
            self.place_building_properly_on_the_grid()

        self.occupied_nodes: Set[IsometricMap] = self.find_occupied_nodes()
        self.block_map_nodes(self.occupied_nodes)

        self.garrisoned_soldiers: List[Union[Soldier, int]] = []
        self.garrison_size: int = self.configs['garrison_size']

        self.energy_consumption = self.configs['energy_consumption']
        self.power_ratio = 0

        self.autodestruction_progress = 0

        # if garrison:
        #     self.spawn_soldiers_for_garrison(garrison)

        if (buildings := self.configs.get('allows_construction')) is not None:
            self.player.buildings_possible_to_build.extend(buildings)

        self.layered_spritelist.swap_rendering_layers(
            self, 0, position_to_map_grid(*self.position)[1]
        )

        self.player.recalculate_energy_balance()

    @property
    def is_selected(self) -> bool:
        return self.game.units_manager.selected_building is self

    @property
    def is_powered(self) -> bool:
        return self.power_ratio > 0 or self.player.unlimited_resources

    @property
    def is_power_plant(self) -> bool:
        return self.produced_resource == ENERGY

    def place_building_properly_on_the_grid(self) -> Point:
        """
        Buildings positions must be adjusted accordingly to their texture
        width and height, so they occupy minimum MapNodes.
        """
        return self.position

    def find_occupied_nodes(self) -> Set[IsometricMap]:
        min_x_grid = int(self.left // TILE_WIDTH)
        min_y_grid = int(self.bottom // TILE_HEIGHT)
        width, height = self.configs.get('size')
        max_x_grid = min_x_grid + width
        max_y_grid = min_y_grid + height
        return {
            self.game.map.grid_to_node((x, y))
            for x in range(min_x_grid, max_x_grid)
            for y in range(min_y_grid, max_y_grid)
        }

    def block_map_nodes(self, occupied_nodes: Set[IsometricMap]):
        for node in occupied_nodes:
            node.remove_tree()
            self.block_map_node(node)

    def spawn_soldiers_for_garrison(self, number_of_soldiers: int):
        """Called when Building is spawned with garrisoned Soldiers inside."""
        for _ in range(min(number_of_soldiers, self.garrison_size)):
            soldier: Soldier = self.game.spawn('soldier', self.player, self.map.get_random_walkable_tile().position)
            soldier.enter_building(self)

    @property
    def is_moving(self) -> bool:
        return False  # this is rather obvious, since this is a Building

    @staticmethod
    def unblock_map_node(node: IsometricMap):
        node.building = None

    def block_map_node(self, node: IsometricMap):
        node.building = self

    def update_observed_area(self, *args, **kwargs):
        if not self.observed_nodes:  # Building need calculate it only once
            self.observed_grids = grids = self.calculate_observed_area()
            self.observed_nodes = {self.map[grid] for grid in grids}

    @ignore_in_editor_mode
    def update_battle_behaviour(self):
        pass

    def on_mouse_enter(self):
        if self.selection_marker is None:
            self.game.units_manager.create_building_selection_marker(self)
            if self.game.units_manager.only_soldiers_selected:
                self.check_soldiers_garrisoning_possibility()

    def check_soldiers_garrisoning_possibility(self):
        friendly_building = self.is_controlled_by_local_human_player
        free_space = len(self.garrisoned_soldiers) < self.garrison_size
        if (friendly_building and free_space) or not friendly_building:
            self.game.mouse.force_cursor(index=CURSOR_ENTER_TEXTURE)

    def on_mouse_exit(self):
        selected_building = self.game.units_manager.selected_building
        if self.selection_marker is not None and self is not selected_building:
            self.game.units_manager.remove_from_selection_markers(self.selection_marker)
        if self.game.mouse.forced_cursor == CURSOR_ENTER_TEXTURE:
            self.game.mouse.force_cursor(index=None)

    def on_update(self, delta_time: float = 1 / 60):
        super().on_update(delta_time)
        self.update_production(delta_time)
        self.update_observed_area()
        self.update_ui_buildings_panel()
        if self.autodestruction_progress:
            self.update_autodestruction()

    def update_autodestruction(self):
        self.autodestruction_progress += 0.25
        if self.autodestruction_progress >= 100:
            self.kill()
        # TODO: gradually remove garrisoned Soldiers from Building

    def draw(self):
        ...

    def update_production(self, delta_time):
        if self.produced_units is not None:
            self.update_units_production(delta_time)
        if self.produced_resource not in (None, ENERGY):
            self.update_resource_production(delta_time)
        if self.research_facility:
            self.update_research(delta_time)

    @ignore_in_editor_mode
    def update_ui_buildings_panel(self):
        if self.is_selected:
            panel = self.game.get_bundle(UI_BUILDINGS_PANEL)
            panel.find_by_name('health').text = f'HP: {round(self.health)} / {self.max_health}'

            if self.autodestruction_progress:
                self.update_demolish_button(panel)

            if self.is_controlled_by_local_human_player and self.produced_units is not None:
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
        if self.is_controlled_by_local_human_player:
            buttons = self.create_building_ui_buttons(x, y)
            ui_elements.extend(buttons)
        return ui_elements

    def create_building_ui_information(self, x, y) -> List[UiElement]:
        text_color = GREEN if self.is_controlled_by_local_human_player else RED
        return [
            UiTextLabel(x, y + 50, self.object_name.replace('_', ' ').title(), 15, text_color, name='building_name'),
            UiTextLabel(x, y + 15, f'HP: {round(self.health)} / {self.max_health}', 12, text_color, name='health')
        ]

    def create_building_ui_buttons(self, x, y) -> List[Button]:
        buttons = [
            self.create_garrison_button(x, y),
            self.create_demolish_button(x, y)
        ]

        if self.produced_units is not None:
            buttons.extend(self.create_production_buttons(x, y))

        return buttons

    def create_garrison_button(self, x, y) -> ProgressButton:
        return ProgressButton(
            'ui_leave_building_btn.png', x - 135, y - 45, 'leave',
            active=len(self.garrisoned_soldiers) > 0,
            functions=self.on_soldier_exit,
            counter=len(self.garrisoned_soldiers)
        )

    def create_demolish_button(self, x, y) -> Button:
        demolish_button = ProgressButton(
            'game_button_destroy.png', x - 55, y - 45, 'demolish',
            functions=self.start_autodestruction,
        )
        demolish_button.bind_function(self.cancel_autodestruction, MOUSE_BUTTON_RIGHT)
        return demolish_button

    def start_autodestruction(self):
        if not self.autodestruction_progress:
            self.autodestruction_progress += 1
            self.game.sound_player.play_sound('preparing_to_autodestruction.wav')

    def cancel_autodestruction(self):
        self.autodestruction_progress = 0
        self.update_demolish_button(ui_panel=self.game.get_bundle(UI_BUILDINGS_PANEL))
        self.game.sound_player.play_sound('autodestruction_cancelled.wav')

    def update_demolish_button(self, ui_panel: UiElementsBundle):
        demolish_button = ui_panel.find_by_name('demolish')
        demolish_button.progress = self.autodestruction_progress

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
        self.reconfigure_building(soldier.player)

    def reconfigure_building(self, player: Player):
        self.clear_known_enemies()
        self.remove_from_map_quadtree()
        self.change_player(player)
        self.insert_to_map_quadtree()
        self.change_building_texture(player)

    def change_building_texture(self, player: Player):
        path_and_texture, size = self.find_proper_texture(player)
        self.textures = [load_texture(path_and_texture, 0, 0, *size)]
        self.set_texture(0)

    def find_proper_texture(self, player) -> Tuple[Path, Tuple]:
        recolored = add_player_color_to_name(self.object_name, player.color)
        texture_name = add_extension(recolored)
        size = get_texture_size(texture_name)
        path_and_texture = get_path_to_file(texture_name)
        return path_and_texture, size

    def clear_known_enemies(self):
        self.known_enemies.clear()

    def change_player(self, new_player: Player):
        self.detach(self.player)
        self.attach(new_player)
        self.player.recalculate_energy_balance()

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

    def on_being_hit(self, damage: float, penetration: float = 0) -> bool:
        # TODO: killing personnel inside Building
        return super().on_being_hit(damage)

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
    """
    When Player decides where to build a nwe Building, the ConstructionSite is raised there for the construction time.
    When Building construction is completed, ConstructionSite disappears and actual Building is spawned in its place.
    """

    def __init__(self, building_name: str, player: Player, position):
        self.size = self.game.configs[building_name]['size']
        super().__init__(f'{CONSTRUCTION_SITE}_{self.size[0]}x{self.size[1]}', player, position)
        self.constructed_building_position = position
        self.constructed_building_name = building_name

        # TODO: create construction textures for each Building with stages of construction
        #  https://github.com/akapkotel/python_real_time_strategy_game/issues/8

        self.maximum_construction_progress = self.game.configs[building_name]['max_health']
        self.construction_progress = 0

        self.construction_progress_bar = ProgressBar(
            self.center_x, self.top, self.width, 20, 0, self.maximum_construction_progress, 1, BLACK,
            CONSTRUCTION_BAR_COLOR
        )
        self.object_name = CONSTRUCTION_SITE

    def on_update(self, delta_time: float = 1 / 60):
        super().on_update(delta_time)
        self.construction_progress += 1
        if self.construction_progress >= self.maximum_construction_progress:
            self.finish_construction()
        elif self.is_controlled_by_local_human_player:
            self.construction_progress_bar.update()

    def draw(self):
        if self.is_controlled_by_local_human_player:
            self.construction_progress_bar.draw()

    def finish_construction(self):
        self.stop_rendering()
        self.construction_progress_bar = None
        self.kill()
        self.game.spawn(self.constructed_building_name, self.player, self.constructed_building_position)
        if self.player.is_local_human_player:
            self.game.sound_player.play_sound('construction_complete.wav')

    def save(self):
        saved_construction_site = super().save()
        saved_construction_site['constructed_building_name'] = self.constructed_building_name
        saved_construction_site['construction_progress'] = self.construction_progress
        saved_construction_site['maximum_construction_progress'] = self.maximum_construction_progress
        return saved_construction_site

    def after_respawn(self, loaded_data: Dict):
        super().after_respawn(loaded_data)
        self.construction_progress_bar.total_progress = self.construction_progress


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from game import Game
