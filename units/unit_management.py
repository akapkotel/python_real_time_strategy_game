#!/usr/bin/env python
from __future__ import annotations

from typing import (
    Optional, Sequence, Set, Tuple, Dict, Iterator, Union, Collection, List, Callable
)

from arcade import Sprite, SpriteSolidColor, load_textures, load_texture
from arcade.arcade_types import Color, Point
from arcade.key import LCTRL

from buildings.buildings import Building
from effects.sound import (
    UNITS_SELECTION_CONFIRMATIONS, UNITS_MOVE_ORDERS_CONFIRMATIONS
)
from units.units_tasking import UnitTask, TaskEnterBuilding
from utils.colors import GREEN, RED, YELLOW
from game import Game
from players_and_factions.player import PlayerEntity
from units.units import Unit, Vehicle, Soldier
from utils.functions import get_path_to_file, ignore_in_menu
from utils.geometry import average_position_of_points_group
from utils.scheduling import EventsCreator

UNIT_HEALTH_BAR_WIDTH = 5
SOLDIER_HEALTH_BAR_WIDTH = 4
BUILDING_HEALTH_BAR_WIDTH = 10
UNIT_HEALTH_BAR_LENGTH_RATIO = 0.6
SOLDIER_HEALTH_BAR_LENGTH_RATIO = 0.4
BUILDING_HEALTH_BAR_LENGTH_RATIO = 1.8

selection_textures = load_textures(
    get_path_to_file('unit_selection_marker.png'),
    [(i * 60, 0, 60, 60) for i in range(10)]
)
soldier_selection_textures = load_textures(
    get_path_to_file('soldier_selection_marker.png'),
    [(i * 40, 0, 40, 40) for i in range(10)]
    # get_path_to_file('soldier_selection_marker.png'), 0, 0, 40, 40
)
building_selection_texture = load_texture(
    get_path_to_file('building_selection_marker.png'), 0, 0, 180, 180
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
    health_bar_width = 0
    health_bar_length_ratio = 1

    def __init__(self, selected: PlayerEntity):
        selected.selection_marker = self
        self.position = x, y = selected.position
        self.selected = selected
        self.borders = Sprite(center_x=x, center_y=y)
        # store our own references to Sprites to kill them when marker is
        # killed after it's Entity was unselected:
        self.sprites = []

        self.health = health = selected.health_percentage
        width, height, color = self.health_to_color_and_size(health)
        self.health_bar = health_bar = SpriteSolidColor(width, height, color)

        self.sprites = sprites = [self.borders, health_bar]
        self.game.selection_markers_sprites.extend(sprites)

    def health_to_color_and_size(self, health: float) -> Tuple[int, int, Color]:
        length = int(self.health_bar_length_ratio * health)
        if health > 66:
            return length, self.health_bar_width, GREEN
        elif health > 33:
            return length, self.health_bar_width, YELLOW
        return length, self.health_bar_width, RED

    def update(self):
        self.position = x, y = self.selected.position
        for sprite in self.sprites[:-1]:
            sprite.position = x, y
        self.update_health_bar(x)

    def update_health_bar(self, x):
        if (health := self.selected.health_percentage) != self.health:
            width, height, color = self.health_to_color_and_size(health)
            if color != self.health_bar.color:
                self.replace_health_bar_with_new_color(color, height, width)
            else:
                self.health_bar.width = width
            self.health = health
        ratio = self.health_bar_length_ratio * 0.5
        self.health_bar.position = x - (100 - health) * ratio, self.borders.top

    def replace_health_bar_with_new_color(self, color, height, width):
        self.health_bar.kill()
        self.health_bar = bar = SpriteSolidColor(width, height, color)
        self.sprites.append(self.health_bar)
        self.game.selection_markers_sprites.append(bar)

    def kill(self):
        self.selected.selection_marker = None
        for sprite in self.sprites:
            sprite.kill()
        self.sprites.clear()


class SelectedUnitMarker(SelectedEntityMarker):
    health_bar_width = UNIT_HEALTH_BAR_WIDTH
    health_bar_length_ratio = UNIT_HEALTH_BAR_LENGTH_RATIO

    def __init__(self, selected: Unit):
        super().__init__(selected)
        # units selection marker has 10 versions, blank + 9 different numbers
        # to show which PermanentUnitsGroup a Unit belongs to:
        group_index = selected.permanent_units_group
        self.borders.texture = selection_textures[group_index]


class SelectedSoldierMarker(SelectedEntityMarker):
    health_bar_width = SOLDIER_HEALTH_BAR_WIDTH
    health_bar_length_ratio = SOLDIER_HEALTH_BAR_LENGTH_RATIO

    def __init__(self, selected: Unit):
        super().__init__(selected)
        # units selection marker has 10 versions, blank + 9 different numbers
        # to show which PermanentUnitsGroup a Unit belongs to:
        group_index = selected.permanent_units_group
        self.borders.texture = soldier_selection_textures[group_index]
        self.update_health_bar(self.position[0])


class SelectedVehicleMarker(SelectedUnitMarker):

    def __init__(self, selected: Vehicle):
        super().__init__(selected)
        self.fuel = selected.fuel
        self.fuel_bar = None
        
    def update(self):
        self.position = x, y = self.selected.position
        self.update_health_bar(x)
        self.update_fuel_bar(x)
        for sprite in self.sprites[:-1]:
            sprite.position = x, y

    def update_fuel_bar(self, x):
        pass


class SelectedBuildingMarker(SelectedEntityMarker):
    health_bar_width = BUILDING_HEALTH_BAR_WIDTH
    health_bar_length_ratio = BUILDING_HEALTH_BAR_LENGTH_RATIO

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
        self.units = {self.game.units.get_by_id(u_id) for u_id in self.units}

    def __del__(self):
        for unit in self.units:
            unit.permanent_units_group = 0


class UnitsManager(EventsCreator):
    """
    This class is an intermediary between Cursor class and PlayerEntities. It
    allows player to interact with units, buildings etc. by the mouse-cursor.
    It keeps track of the currently selected units and provides a way for the
    player to give them orders by the mouse-clicks. UnitsManager should be an
    attribute of Cursor class. Game should also have it's reference.
    """
    game: Optional[Game] = None

    def __init__(self, cursor):
        """
        :param cursor: MouseCursor -- reference to the cursor used in game
        """
        super().__init__()
        self.cursor = cursor
        self.window = self.game.window
        self.cursor.bind_units_manager(manager=self)
        # after left button is released, Units from drag-selection are selected
        # permanently, and will be cleared after new selection or deselecting
        # them with right-button click:
        self.selected_units: HashedList[Unit] = HashedList()
        self.selected_building: Optional[Building] = None

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
        # updated to check the task status, if Unit finished it's task etc.
        self.units_tasks: List[UnitTask] = []

    def __contains__(self, unit) -> bool:
        return unit in self.selected_units or unit is self.selected_building

    @property
    def units_or_building_selected(self) -> bool:
        return self.selected_units or self.selected_building is not None

    @ignore_in_menu
    def on_left_click_no_selection(self, x, y):
        pointed = self.cursor.pointed_unit or self.cursor.pointed_building
        if pointed is not None:
            self.on_player_entity_clicked(pointed)
        elif units := self.selected_units:
            self.on_terrain_click_with_units(x, y, units)

    @ignore_in_menu
    def on_terrain_click_with_units(self, x, y, units):
        self.clear_units_assigned_enemies(units)
        x, y = self.game.pathfinder.get_closest_walkable_position(x, y)
        self.create_movement_order(units, x, y)

    def clear_units_assigned_enemies(self, units):
        for unit in units:
            unit.assign_enemy(None)

    def create_movement_order(self, units, x, y):
        if LCTRL in self.game.window.keyboard.keys_pressed:
            self.game.pathfinder.enqueue_waypoint(units, x, y)
        else:
            self.send_units_to_pointed_location(units, x, y)
        self.window.sound_player.play_random(UNITS_MOVE_ORDERS_CONFIRMATIONS)

    def send_units_to_pointed_location(self, units, x, y):
        self.game.pathfinder.navigate_units_to_destination(units, x, y)

    def on_player_entity_clicked(self, clicked: PlayerEntity):
        if clicked.selectable:
            self.on_friendly_player_entity_clicked(clicked)
        elif units := self.selected_units:
            self.on_hostile_player_entity_clicked(clicked, units)

    def on_friendly_player_entity_clicked(self, clicked: PlayerEntity):
        clicked: Union[Unit, Building]
        if clicked.is_building:
            self.on_building_clicked(clicked)
        else:
            self.on_unit_clicked(clicked)

    def on_hostile_player_entity_clicked(self, clicked: PlayerEntity, units):
        if clicked.is_building and self.only_soldiers_selected:
            clicked: Building
            self.on_building_clicked(clicked)
        else:
            self.clear_units_assigned_enemies(units)
            self.send_units_to_attack_target(clicked, units)


    def send_units_to_attack_target(self, target, units):
        for unit in units:
            unit._enemy_assigned_by_player = target
        self.send_units_to_pointed_location(units, *target.position)

    def on_unit_clicked(self, clicked_unit: Unit):
        self.unselect_all_selected()
        self.select_units(clicked_unit)

    def on_building_clicked(self, clicked_building: Building):
        if self.only_soldiers_selected and clicked_building.count_empty_garrison_slots:
            soldiers = self.get_selected_soldiers()
            self.send_soldiers_to_building(clicked_building, soldiers)
        else:
            self.select_building(clicked_building)

    @property
    def only_soldiers_selected(self) -> bool:
        if not self.selected_units:
            return False
        return all(s.is_infantry for s in self.selected_units)

    def get_selected_soldiers(self) -> List[Soldier]:
        s: Soldier
        return [s for s in self.selected_units if s.is_infantry]

    def send_soldiers_to_building(self, building: Building, soldiers: List[Soldier]):
        self.send_units_to_pointed_location(soldiers, *building.position)
        self.units_tasks.append(TaskEnterBuilding(self, soldiers, building))

    def select_building(self, building: Building):
        self.unselect_all_selected()
        self.selected_building = building
        self.create_selection_markers(building=building)
        self.game.change_interface_content(context=building)

    def update_selection_markers_set(self, new, lost):
        discarded = {m for m in self.selection_markers if m.selected in lost}
        self.clear_selection_markers(discarded)
        self.create_selection_markers(new)

    @ignore_in_menu
    def select_units(self, *units: Unit):
        self.selected_units.extend(units)
        self.create_selection_markers(units)
        self.game.change_interface_content(context=units)
        self.window.sound_player.play_random(UNITS_SELECTION_CONFIRMATIONS)

    def create_selection_markers(self, units=None, building=None):
        if units is not None:
            self.create_units_selection_markers(units)
        if building is not None:
            self.create_building_selection_marker(building)

    def create_units_selection_markers(self, units: Collection[Unit]):
        self.selection_markers.update(
            SelectedSoldierMarker(unit) if unit.is_infantry
            else SelectedUnitMarker(unit) for unit in units
        )

    def create_building_selection_marker(self, building: Building):
        marker = SelectedBuildingMarker(building)
        self.selection_markers.add(marker)

    def remove_from_selection_markers(self, entity: PlayerEntity):
        for marker in self.selection_markers.copy():
            if marker.selected is entity:
                self.kill_selection_marker(marker)

    def kill_selection_marker(self, marker):
        self.selection_markers.discard(marker)
        marker.kill()

    def unselect(self, entity: PlayerEntity):
        if entity.is_building:
            self.selected_building = None
        else:
            self.selected_units.remove(entity)
        self.remove_from_selection_markers(entity)
        self.update_interface_on_selection_change()

    def update_interface_on_selection_change(self):
        if not self.selected_units and self.selected_building is None:
            self.game.change_interface_content(context=None)

    @ignore_in_menu
    def unselect_all_selected(self):
        self.selected_units.clear()
        self.selected_building = None
        self.clear_selection_markers()
        self.game.change_interface_content(context=None)

    def clear_selection_markers(self,
                                killed: Set[SelectedUnitMarker] = None):
        killed = self.selection_markers.copy() if killed is None else killed
        for marker in killed:
            self.kill_selection_marker(marker)

    def update(self):
        self.update_selection_markers()

    def update_selection_markers(self):
        for marker in self.selection_markers:
            marker.update() if marker.selected.alive else marker.kill()

    def create_new_permanent_units_group(self, digit: int):
        units = self.selected_units.copy()
        new_group = PermanentUnitsGroup(group_id=digit, units=units)
        self.permanent_units_groups[digit] = new_group
        self.unselect_all_selected()
        self.select_units(*units)

    @ignore_in_menu
    def select_permanent_units_group(self, group_id: int):
        try:
            group = self.permanent_units_groups[group_id]
            selected = self.selected_units
            if selected and set(selected) == group.units:
                self.game.window.move_viewport_to_the_position(*group.position)
            else:
                self.unselect_all_selected()
                self.select_units(*group.units)
        except KeyError:
            pass


class HashedList(list):
    """
    Wrapper for a list of currently selected Units. Adds fast look-up by using
    of set containing triggers id's.
    To work, it requires added triggers to have an unique 'id' attribute.
    """

    def __init__(self, iterable=None):
        super().__init__()
        self.elements_ids = set()
        if iterable is not None:
            self.extend(iterable)

    def __contains__(self, item) -> bool:
        return item.id in self.elements_ids

    def append(self, item):
        try:
            self.elements_ids.add(item.id)
            super().append(item)
        except AttributeError:
            print("Item must have 'id' attribute which is hashable.")

    def remove(self, item):
        self.elements_ids.discard(item.id)
        try:
            super().remove(item)
        except ValueError:
            pass

    def pop(self, index=-1):
        popped = super().pop(index)
        self.elements_ids.discard(popped.id)
        return popped

    def extend(self, iterable) -> None:
        self.elements_ids.update(i.id for i in iterable)
        super().extend(iterable)

    def insert(self, index, item) -> None:
        self.elements_ids.add(item.id)
        super().insert(index, item)

    def clear(self) -> None:
        self.elements_ids.clear()
        super().clear()

    def where(self, condition: Callable):
        return HashedList([e for e in self if condition(e)])
