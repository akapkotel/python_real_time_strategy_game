#!/usr/bin/env python
from __future__ import annotations

from typing import (
    Optional, Sequence, Set, Dict, Iterator, Union, Collection, List, Callable, Iterable
)

from arcade import Sprite, SpriteSolidColor, load_textures, load_texture
from arcade.arcade_types import Color, Point

from buildings.buildings import Building
from effects.sound import (
    UNITS_SELECTION_CONFIRMATIONS, UNITS_MOVE_ORDERS_CONFIRMATIONS
)
from units.units_tasking import UnitTask, TaskEnterBuilding, TaskAttackMove
from utils.colors import GREEN, RED, YELLOW
from game import Game, UI_WIDTH
from players_and_factions.player import PlayerEntity
from units.units import Unit, Vehicle, Soldier
from utils.functions import get_path_to_file, ignore_in_menu
from utils.geometry import average_position_of_points_group
from utils.scheduling import EventsCreator


UNIT_HEALTH_BARS_HEIGHT = 5
SOLDIER_HEALTH_BARS_HEIGHT = 3
BUILDING_HEALTH_BARS_HEIGHT = 10

UNIT_SELECTION_MARKER_SIZE = 60
SOLDIER_SELECTION_MARKER_SIZE = 40
BUILDING_SELECTION_MARKER_SIZE = 180

UNIT_SINGLE_BAR_WIDTH = 4
SOLDIER_SINGLE_BAR_WIDTH = 3
BUILDING_SINGLE_BAR_WIDTH = 8

UNIT_BARS_DISTANCE = 2
SOLDIER_BARS_DISTANCE = 1
BUILDING_BARS_DISTANCE = 1

UNIT_BARS_COUNT = 10
BUILDING_BARS_COUNT = 20


selection_textures = load_textures(
    get_path_to_file('unit_selection_marker.png'),
    [(i * UNIT_SELECTION_MARKER_SIZE, 0, UNIT_SELECTION_MARKER_SIZE, UNIT_SELECTION_MARKER_SIZE) for i in range(10)]
)
soldier_selection_textures = load_textures(
    get_path_to_file('soldier_selection_marker.png'),
    [(i * SOLDIER_SELECTION_MARKER_SIZE, 0, SOLDIER_SELECTION_MARKER_SIZE, SOLDIER_SELECTION_MARKER_SIZE) for i in range(10)]
)
building_selection_texture = load_texture(
    get_path_to_file('building_selection_marker.png'), 0, 0, BUILDING_SELECTION_MARKER_SIZE, BUILDING_SELECTION_MARKER_SIZE
)


class SelectedEntityMarker:
    """
    This class produces rectangle-unit-or-building-selection markers showing
    that a particular Unit or Building is selected by player and displaying
    some info about selected, like health level or lack of fuel icon. Each
    marker can contain many Sprites which are dynamically created, updated and
    destroyed. You must cache SelectionMarker instances and their Sprites in
    distinct data-structures. Markers are stored in ordinary list and
    Sprites in SpriteLists.
    """
    game: Optional[Game] = None
    health_bar_height = 0
    health_bar_length = 0
    single_bar_width = 0
    bars_distance = 0
    bars_count = 10

    def __init__(self, selected: PlayerEntity):
        self.selected = selected
        self.position = x, y = selected.position
        self.health_ratio = selected.health_ratio
        self.bars_ratio = 100 // self.bars_count
        self.borders = Sprite(center_x=x, center_y=y)
        self.health_bars = self.generate_health_bars(color=self.health_to_color())
        # store our own references to Sprites to kill them when marker is
        # killed after it's Entity was unselected:
        self.sprites = sprites = [self.borders] + self.health_bars
        self.game.selection_markers_sprites.extend(sprites)
        selected.selection_marker = self

    def generate_health_bars(self, color: Color) -> list[SpriteSolidColor]:
        if self.game.settings.simplified_health_bars:
            return [SpriteSolidColor(int(self.health_bar_length * self.health_ratio), self.health_bar_height, color)]
        return [
            SpriteSolidColor(self.single_bar_width, self.health_bar_height, color)
            for _ in range(int(self.health_ratio * 100 / self.bars_ratio))
        ]

    def health_to_color(self) -> Color:
        if self.health_ratio > 0.6:
            return GREEN
        return YELLOW if self.health_ratio > 0.3 else RED

    def update(self):
        self.position = x, y = self.selected.position
        for sprite in (s for s in self.sprites if s not in self.health_bars):
            sprite.position = x, y
        if self.health_bars:
            self.update_health_bars()

    def update_health_percentage(self, new_health_percentage: int):
        self.health_ratio = new_health_percentage
        if self.health_bars and self.health_bars[0].color != (color := self.health_to_color()):
            self.replace_health_bar_with_new_color(color)

    def update_health_bars(self):
        if self.game.settings.simplified_health_bars:
            shift = self.health_bar_length * (1 - self.health_ratio)
            self.health_bars[0].position = self.borders.left + (self.borders.width - shift) * 0.5, self.borders.top
        else:
            left = self.borders.left + (self.single_bar_width / 2)
            width = self.single_bar_width
            distance = self.bars_distance
            y = self.borders.top
            for i, bar in enumerate(self.health_bars):
                bar.position = left + (width * i) + (distance * (i + 1)), y

    def replace_health_bar_with_new_color(self, color: Color):
        for bar in self.health_bars:
            bar.kill()
        self.health_bars = self.generate_health_bars(color)
        self.sprites.extend(self.health_bars)
        self.game.selection_markers_sprites.extend(self.health_bars)

    def kill(self):
        self.selected.selection_marker = None
        for sprite in self.sprites:
            sprite.kill()
        self.sprites.clear()
        self.selected = None


class SelectedUnitMarker(SelectedEntityMarker):
    health_bar_height = UNIT_HEALTH_BARS_HEIGHT
    health_bar_length = UNIT_SELECTION_MARKER_SIZE
    single_bar_width = UNIT_SINGLE_BAR_WIDTH
    bars_distance = UNIT_BARS_DISTANCE
    bars_count = UNIT_BARS_COUNT

    def __init__(self, selected: Unit):
        super().__init__(selected)
        # units selection marker has 10 versions, blank + 9 different numbers
        # to show which PermanentUnitsGroup a Unit belongs to:
        group_index = selected.permanent_units_group
        self.borders.texture = selection_textures[group_index]


class SelectedSoldierMarker(SelectedUnitMarker):
    health_bar_height = SOLDIER_HEALTH_BARS_HEIGHT
    health_bar_length = SOLDIER_SELECTION_MARKER_SIZE
    single_bar_width = SOLDIER_SINGLE_BAR_WIDTH
    bars_distance = SOLDIER_BARS_DISTANCE
    bars_count = UNIT_BARS_COUNT

    def __init__(self, selected: Unit):
        super().__init__(selected)
        # units selection marker has 10 versions, blank + 9 different numbers
        # to show which PermanentUnitsGroup a Unit belongs to:
        group_index = selected.permanent_units_group
        self.borders.texture = soldier_selection_textures[group_index]
        self.update_health_bars()


class SelectedVehicleMarker(SelectedUnitMarker):

    def __init__(self, selected: Vehicle):
        super().__init__(selected)
        self.fuel = selected.fuel
        self.fuel_bar = None
        
    def update(self):
        super().update()
        self.position = x, y = self.selected.position
        self.update_fuel_bar(x)

    def update_fuel_bar(self, x):
        ...


class SelectedBuildingMarker(SelectedEntityMarker):
    health_bar_height = BUILDING_HEALTH_BARS_HEIGHT
    health_bar_length = BUILDING_SELECTION_MARKER_SIZE
    single_bar_width = BUILDING_SINGLE_BAR_WIDTH
    bars_distance = BUILDING_BARS_DISTANCE
    bars_count = BUILDING_BARS_COUNT

    def __init__(self, building: PlayerEntity):
        super().__init__(building)
        self.borders.texture = building_selection_texture


class PermanentUnitsGroup:
    """
    Player can group units by selecting them with mouse and pressing CTRL +
    numeric keys (1-9). Such groups could be then quickly selected by pressing
    their numbers.
    """
    game: Optional[Game] = None

    def __init__(self, group_id: int, units: Sequence[Unit]):
        self.group_id = group_id
        self.units: Set[Unit] = set(units)
        self.game.units_manager.permanent_units_groups[group_id] = self
        for unit in units:
            unit.set_permanent_units_group(group_id)

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units

    def __iter__(self) -> Iterator:
        return iter(self.units)

    @property
    def position(self) -> Point:
        positions = [(u.center_x, u.center_y) for u in self.units]
        return average_position_of_points_group(positions)

    def discard(self, unit: Unit):
        self.units.discard(unit)
        if not self.units:
            del self.game.units_manager.permanent_units_groups[self.group_id]

    def __getstate__(self) -> Dict:
        return {'group_id': self.group_id, 'units': [u.id for u in self.units]}

    def __setstate__(self, state: Dict):
        self.__dict__.update(state)
        self.units = {self.game.units.get(u_id) for u_id in self.units}

    def __del__(self):
        for unit in self.units:
            unit.permanent_units_group = 0
        del self


class UnitsManager(EventsCreator):
    """
    This class is an intermediary between Cursor class and PlayerEntities. It
    allows player to interact with units, buildings etc. by the mouse-cursor.
    It keeps track of the currently selected units and provides a way for the
    player to give them orders by the mouse-clicks. UnitsManager should be an
    attribute of Cursor class. Game should also have its reference.
    """
    game: Optional[Game] = None

    def __init__(self, mouse, keyboard):
        """
        :param mouse: MouseCursor -- reference to the cursor used in game
        """
        super().__init__()
        self.mouse = mouse
        self.keyboard = keyboard
        self.window = self.game.window
        self.mouse.bind_units_manager(manager=self)
        # after left button is released, Units from drag-selection are selected
        # permanently, and will be cleared after new selection or deselecting
        # them with right-button click:
        self.selected_units: HashedUnitsList[Unit] = HashedUnitsList()
        self.selected_building: Optional[Building] = None

        self.selected_units_types: Dict[str, int] = {}

        # for each selected Unit create SelectedUnitMarker, a Sprite showing
        # that this unit is currently selected and will react for player's
        # actions. Sprites are actually drawn and updated in Game class, but
        # here we keep them cashed to easily manipulate them:
        self.selection_markers: Set[SelectedEntityMarker] = set()

        # Player can create group of Units by CTRL + 0-9 keys, and then
        # select those groups quickly with 0-9 keys, or even move screen tp
        # the position of the group by pressing numeric key twice. See the
        # PermanentUnitsGroup class in units_management.py
        self.permanent_units_groups: Dict[int, PermanentUnitsGroup] = {}

        # Units could be assigned with tasks to do, which n-require to be
        # updated to check the task status, if Unit finished its task etc.
        self.units_tasks: List[UnitTask] = []

        self.waypoints_mode = False

    def __contains__(self, unit) -> bool:
        return unit in self.selected_units or unit is self.selected_building

    @property
    def selected_units_count(self) -> int:
        return len(self.selected_units)

    @property
    def units_or_building_selected(self) -> bool:
        return self.selected_units or self.selected_building is not None

    def kill_selected(self):
        """Remove Units and Buildings in scenario editor."""
        for unit in self.selected_units[::]:
            unit.kill()
        if self.selected_building is not None:
            self.selected_building.kill()

    def toggle_waypoint_mode(self, forced_mode: Optional[bool] = None):
        if self.waypoints_mode and self.game.pathfinder.created_waypoints_queue is not None:
            self.game.pathfinder.finish_waypoints_queue()
        self.waypoints_mode = not self.waypoints_mode if forced_mode is None else forced_mode

    @ignore_in_menu
    def on_left_click_no_selection(self, x, y):
        pointed = self.mouse.pointed_unit or self.mouse.pointed_building
        if pointed is not None:
            self.on_player_entity_clicked(pointed)
        elif units := self.selected_units:
            self.on_terrain_click_with_units(x, y, units)

    @ignore_in_menu
    def on_terrain_click_with_units(self, x, y, units):
        if self.game.editor_mode:
            self.teleport_units_to_location(x, y, units)
        else:
            self.clear_units_assigned_enemies()
            x, y = self.game.pathfinder.get_closest_walkable_position(x, y)
            self.create_movement_order(units, x, y)

    def clear_units_assigned_enemies(self):
        for unit in self.selected_units:
            unit.assign_enemy(None)

    def teleport_units_to_location(self, x, y, units: List[Unit]):
        positions = self.game.pathfinder.get_group_of_waypoints(x, y, len(units))
        for position, unit in zip(positions, units):
            new_map_node = self.game.map.node(position)
            unit.swap_blocked_nodes(unit.current_node, new_map_node)
            unit.position = new_map_node.position

    def create_movement_order(self, units, x, y):
        if self.waypoints_mode:
            self.game.pathfinder.enqueue_waypoint(units, x, y)
        else:
            self.send_units_to_pointed_location(units, x, y)
            # self.units_tasks.append(TaskAttackMove(self, units, x, y))
        self.window.sound_player.play_random_sound(UNITS_MOVE_ORDERS_CONFIRMATIONS)

    def send_units_to_pointed_location(self, units, x, y):
        self.game.pathfinder.navigate_units_to_destination(units, x, y, True)

    def on_player_entity_clicked(self, clicked: PlayerEntity):
        if self.game.editor_mode or clicked.is_controlled_by_human_player:
            self.on_friendly_player_entity_clicked(clicked)
        else:
            self.on_hostile_player_entity_clicked(clicked)

    def on_friendly_player_entity_clicked(self, clicked: PlayerEntity):
        clicked: Union[Unit, Building]
        if clicked.is_building:
            self.on_building_clicked(clicked)
        else:
            self.on_unit_clicked(clicked)

    def on_hostile_player_entity_clicked(self, clicked: PlayerEntity):
        units = self.selected_units
        if clicked.is_building:
            clicked: Building
            if self.only_soldiers_selected and clicked.count_empty_garrison_slots:
                self.send_soldiers_to_building(clicked)
            elif units:
                self.send_units_to_attack_target(clicked, units)
            else:
                self.on_building_clicked(clicked)
        elif units:
            self.send_units_to_attack_target(clicked, units)

    def send_units_to_attack_target(self, target, units):
        self.clear_units_assigned_enemies()
        for unit in units:
            unit._enemy_assigned_by_player = target
        self.send_units_to_pointed_location(units, *target.position)

    def on_unit_clicked(self, clicked_unit: Unit):
        self.select_units(clicked_unit)

    def on_building_clicked(self, clicked_building: Building):
        if self.only_soldiers_selected and clicked_building.count_empty_garrison_slots:
            self.send_soldiers_to_building(clicked_building)
        else:
            self.select_building(clicked_building)

    @property
    def only_soldiers_selected(self) -> bool:
        if not self.selected_units:
            return False
        return all(s.is_infantry for s in self.selected_units)

    def get_selected_soldiers(self, amount: int = -1) -> List[Soldier]:
        s: Soldier
        soldiers = [s for s in self.selected_units if s.is_infantry]
        return soldiers[0:amount]

    def send_soldiers_to_building(self, building: Building):
        soldiers = self.get_selected_soldiers(amount=building.count_empty_garrison_slots)
        self.send_units_to_pointed_location(soldiers, *building.position)
        self.units_tasks.append(TaskEnterBuilding(self, soldiers, building))

    def select_building(self, building: Building):
        self.unselect_all_selected()
        self.selected_building = building
        self.create_building_selection_marker(building=building)
        self.game.change_interface_content(context_gameobjects=building)

    def update_selection_markers_set(self, new: Collection[Unit], lost: Collection[Unit]):
        discarded = {m for m in self.selection_markers if m.selected in lost}
        self.clear_selection_markers(discarded)
        self.create_units_selection_markers(new)

    @ignore_in_menu
    def select_units(self, *units: Unit):
        self.unselect_all_selected()
        self.selected_units.extend(units)
        self.create_units_selection_markers(units)
        self.update_types_of_selected_units(units)
        self.game.change_interface_content(context_gameobjects=units)
        if not self.game.editor_mode:
            self.window.sound_player.play_random_sound(UNITS_SELECTION_CONFIRMATIONS)

    def select_units_of_type(self, units_type: str):
        self.select_units(*[u for u in self.selected_units if u.object_name == units_type])

    def update_types_of_selected_units(self, units: Collection[Unit]):
        for unit in units:
            self.selected_units_types[unit.object_name] = self.selected_units_types.setdefault(unit.object_name, 0) + 1

    def create_units_selection_markers(self, units: Collection[Unit]):
        self.selection_markers.update(
            SelectedSoldierMarker(unit) if unit.is_infantry
            else SelectedUnitMarker(unit) for unit in units
        )

    def create_building_selection_marker(self, building: Building):
        marker = SelectedBuildingMarker(building)
        self.selection_markers.add(marker)

    def remove_from_selection_markers(self, selection_marker: SelectedEntityMarker):
        self.selection_markers.discard(selection_marker)
        selection_marker.kill()

    def unselect(self, entity: Unit | Building):
        if entity.is_building:
            self.selected_building = None
        else:
            self.selected_units.remove(entity)
            self.selected_units_types[entity.object_name] -= 1  # TODO: #1 fix KeyError when Unit is killed during selection
        self.remove_from_selection_markers(entity.selection_marker)
        self.update_interface_on_selection_change()

    def update_interface_on_selection_change(self):
        if self.selected_units:
            self.game.change_interface_content(context_gameobjects=self.selected_units)
        elif self.selected_building is not None:
            self.game.change_interface_content(context_gameobjects=self.selected_building)
        else:
            self.game.change_interface_content(context_gameobjects=None)

    @ignore_in_menu
    def unselect_all_selected(self):
        self.selected_units.clear()
        self.selected_building = None
        self.clear_selection_markers()
        self.selected_units_types.clear()
        self.game.change_interface_content(context_gameobjects=None)

    def clear_selection_markers(self, killed_markers: Set[SelectedUnitMarker] = None):
        killed_markers = self.selection_markers.copy() if killed_markers is None else killed_markers
        for selection_marker in killed_markers:
            self.remove_from_selection_markers(selection_marker)

    def update(self):
        for marker in self.selection_markers:
            marker.update()
        if len(self.selected_units) == 1:
            self.selected_units.first.update_ui_information_about_unit()

    def create_new_permanent_units_group(self, digit: int):
        units = self.selected_units.copy()
        new_group = PermanentUnitsGroup(group_id=digit, units=units)
        self.permanent_units_groups[digit] = new_group
        self.select_units(*units)

    @ignore_in_menu
    def select_permanent_units_group(self, group_id: int):
        try:
            group = self.permanent_units_groups[group_id]
            if set(self.selected_units) == group.units:
                x, y = group.position
                self.game.window.move_viewport_to_the_position(x + UI_WIDTH / 2, y)
            else:
                self.select_units(*group.units)
        except KeyError:
            pass

    def stop_all_units(self):
        for unit in self.selected_units:
            unit.stop_completely()


class HashedUnitsList(list):
    """
    Wrapper for a list of currently selected Units. Adds fast look-up by using
    of set containing triggers id's.
    To work, it requires added triggers to have a unique 'id' attribute.
    """

    def __init__(self, iterable: Optional[Iterable[Unit]] = None):
        super().__init__()
        self.units_ids = set()
        if iterable is not None:
            self.extend(iterable)

    def __contains__(self, unit: Unit) -> bool:
        return unit.id in self.units_ids

    @property
    def first(self) -> Unit:
        return self[0]

    def append(self, unit: Unit):
        try:
            self.units_ids.add(unit.id)
            super().append(unit)
        except AttributeError:
            print("Item must have 'id' attribute which is hashable.")

    def remove(self, unit: Unit):
        self.units_ids.discard(unit.id)
        try:
            super().remove(unit)
        except ValueError:
            pass

    def pop(self, index=-1) -> Unit:
        popped = super().pop(index)
        self.units_ids.discard(popped.id)
        return popped

    def extend(self, iterable: Iterable[Unit]) -> None:
        self.units_ids.update(i.id for i in iterable)
        super().extend(iterable)

    def insert(self, index: int, unit: Unit) -> None:
        self.units_ids.add(unit.id)
        super().insert(index, unit)

    def clear(self) -> None:
        self.units_ids.clear()
        super().clear()

    def where(self, condition: Callable) -> HashedUnitsList:
        return HashedUnitsList([e for e in self if condition(e)])
