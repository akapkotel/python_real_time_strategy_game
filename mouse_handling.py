#!/usr/bin/env python

from typing import Optional, Set, Union
from arcade import (
    Window, SpriteList, draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline, MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT
)

from gameobject import GameObject, get_gameobjects_at_position
from scheduling import EventsCreator, log
from data_containers import DividedSpriteList
from functions import first_object_of_type
from colors import GREEN, CLEAR_GREEN
from user_interface import UiElement
from player import PlayerEntity
from buildings import Building
from game import Game, Menu
from units import Unit


DrawnAndUpdated = Union[SpriteList, DividedSpriteList, 'MouseCursor']


class MouseCursor(UiElement, EventsCreator):
    # window: Optional[Window] = None
    # game: Optional[Game] = None
    menu: Optional[Menu] = None

    def __init__(self, window: Window, texture_name: str):
        UiElement.__init__(self, texture_name)
        EventsCreator.__init__(self)
        self.window = window

        self.pointed_objects: Set[GameObject] = set()
        self.pointed_ui_elements: Set[UiElement] = set()

        self.potentially_selected: Set[Unit] = set()  # drag-selection
        self.selected_units: Set[Unit] = set()  # after mouse released

        self.menu = self.window.menu_view

        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.position = x, y

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_click(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_click(x, y, modifiers)

    def on_left_click(self, x: float, y: float, modifiers: int):
        if self.pointed_objects:
            log(f'Left-clicked at x:{x}, y: {y}')
            log(f'Clicked at {self.pointed_objects}')

    def on_right_click(self, x: float, y: float, modifiers: int):
        log(f'Right-clicked at x:{x}, y: {y}')
        # TODO: clearing selections, context menu?

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        # TODO: closing MouseSelection
        pass

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        self.on_mouse_motion(x, y, dx, dy)
        # TODO: dragging selections logic

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        # TODO
        raise NotImplementedError

    def update(self):
        sprite_lists = self.window.updated
        self.update_pointed_gameobjects(sprite_lists)
        self.update_pointed_ui_elements(sprite_lists)

    def update_pointed_gameobjects(self, sprite_lists):
        self.pointed_objects = get_gameobjects_at_position(self.position,
                                                           sprite_lists)
        unit = self.pointed_unit()
        building = self.pointed_building()
        # print(f'Pointed unit: {unit}, pointed building: {building}')

    def update_pointed_ui_elements(self, sprite_lists):
        pass

    def pointed_unit(self) -> Optional[Unit]:
        return first_object_of_type(self.pointed_objects, Unit)

    def pointed_building(self) -> Optional[Building]:
        return first_object_of_type(self.pointed_objects, Building)


class MouseSelection:
    """Class for mouse-selected_units rectangle-areas."""
    game: Optional[Game] = None

    __slots__ = ["start", "end", "left", "right", "top", "bottom", "units"]

    def __init__(self, x: float, y: float):
        """
        Initialize new Selection with empty list of selected_units Units.

        :param x: float -- x coordinate of selection starting corner
        :param y: float -- y coordinate of selection starting corner
        :param game_instance: arcade.Window reference
        :type game_instance: Game
        """
        self.start = (x, y)
        self.end = (x, y)
        self.left = x
        self.right = x
        self.top = y
        self.bottom = y
        self.units: Set[PlayerEntity] = set()

    def __contains__(self, item: PlayerEntity) -> bool:
        return item in self.units

    def update(self, x: float, y: float):
        """
        Update current Selection setting new shape of a rectangle-marker.

        :param x: float -- x coordinate of current closing corner
        :param y: float -- y coordinate of current closing corner
        """
        self.end = (x, y)  # actual mouse-cursor position
        self.calculate_selection_rectangle_bounds()
        self.update_units()  # some units could get outside and some inside

    def calculate_selection_rectangle_bounds(self):
        corners = self.start, self.end
        self.left, self.right = sorted([x[0] for x in corners])
        self.bottom, self.top = sorted([x[1] for x in corners])

    def update_units(self):
        """
        Update list of currently selected_units accordingly to the shape of
        the selection rectangle: units inside the shape are considered as
        'selected' and units outside the shape are not selected.
        """
        selection_units = self.units
        player_units = self.game.local_player.units
        inside_selection = self.inside_selection_rect
        units_to_add = set()
        units_to_discard = set()
        # check units if they should be selected or not:
        for unit in (u for u in player_units if u.selectable):
            inside = inside_selection(*unit.position)
            if inside:
                if unit not in selection_units:
                    units_to_add.add(unit)
            elif unit in selection_units:
                units_to_discard.add(unit)
        # update selection units set:
        selection_units.difference_update(units_to_discard)
        self.add_units_to_selection(units_to_add)

    def inside_selection_rect(self, x: float, y: float) -> bool:
        return self.left < x < self.right and self.bottom < y < self.top

    def add_units_to_selection(self, units: Set[Unit]):
        self.units.update(units)
        self.game.create_selection_markers(*units)

    def draw(self):
        """Draw rectangle showing borders of current selection."""
        left, right, top, bottom = self.left, self.right, self.top, self.bottom
        draw_lrtb_rectangle_filled(left, right, top, bottom, CLEAR_GREEN)
        draw_lrtb_rectangle_outline(left, right, top, bottom, GREEN)
        selection_units = self.units
        player_units = self.game.local_player.units
        inside_selection = self.inside_selection_rect
        units_to_add = set()
        units_to_discard = set()
        # check units if they should be selected or not:
        for unit in (u for u in player_units if u.selectable):
            inside = inside_selection(*unit.position)
            if inside:
                if unit not in selection_units:
                    units_to_add.add(unit)
            elif unit in selection_units:
                units_to_discard.add(unit)
        # update selection units set:
        selection_units.difference_update(units_to_discard)
        self.add_units_to_selection(units_to_add)
