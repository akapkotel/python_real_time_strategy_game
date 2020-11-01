#!/usr/bin/env python

from typing import Optional, Set, List, Union
from arcade import (
    Window, Sprite, SpriteList, draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline, MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT,
    get_sprites_at_point
)

from gameobject import GameObject, get_gameobjects_at_position
from scheduling import EventsCreator, log
from data_containers import DividedSpriteList
from functions import first_object_of_type
from colors import GREEN, CLEAR_GREEN
from user_interface import ToggledElement, UiElement, CursorInteractive
from player import PlayerEntity
from buildings import Building
from game import Game, Menu
from units import Unit


DrawnAndUpdated = Union[SpriteList, DividedSpriteList, 'MouseCursor']


class MouseCursor(Sprite, ToggledElement, EventsCreator):
    """
    MouseCursor replaces system-cursor with it's own Sprite and process all
    mouse-related calls from arcade.Window to call proper methods and functions
    when user operates with mouse.
    """
    window: Optional[Window] = None
    game: Optional[Game] = None
    menu: Optional[Menu] = None
    instance: Optional['MouseCursor'] = None

    def __init__(self, window: Window, texture_name: str):
        Sprite.__init__(self, texture_name)
        ToggledElement.__init__(self, active=False, visible=False)
        EventsCreator.__init__(self)
        self.window = window

        # cache currently updated and drawn spritelists of the active View:
        self._updated_spritelists: List[DrawnAndUpdated] = []

        self.dragged_ui_element: Optional[UiElement] = None
        self.pointed_ui_element: Optional[UiElement] = None
        self.pointed_gameobject: Optional[GameObject] = None

        # player can select Units by dragging mouse cursor with left-button
        # pressed: all Units inside selection-rectangle will be added to the
        # selection:
        self.mouse_drag_selection: Optional[MouseDragSelection] = None

        # after left button is released, Units from drag-selection are selected
        # permanently, and will be cleared after new selection or deselecting
        # them with right-button click:
        self.selected_units: Set[Unit] = set()

        self.menu = self.window.menu_view

        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    @property
    def updated_spritelists(self):
        return self._updated_spritelists

    @updated_spritelists.setter
    def updated_spritelists(self, value: List[SpriteList]):
        self._updated_spritelists = [
            v for v in value if isinstance(v, (SpriteList, DividedSpriteList))
        ]

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.position = x, y

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_click(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_click(x, y, modifiers)

    def on_left_click(self, x: float, y: float, modifiers: int):
        if self.pointed_gameobject or self.pointed_ui_element:
            log(f'Left-clicked at x:{x}, y: {y}')
            log(f'Clicked at {self.pointed_gameobject, self.pointed_ui_element}')

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
        if self.mouse_drag_selection is not None:
            self.mouse_drag_selection.update(x, y)
        else:
            self.mouse_drag_selection = MouseDragSelection(x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        # TODO
        raise NotImplementedError

    def update(self):
        """
        Search all Spritelists and DividedSpriteLists for any UiElements or
        GameObjects placed at the MouseCursor position.
        """
        if self.game is None:
            MouseDragSelection.game = self.game = self.window.game_view
        if pointed := self.get_pointed_sprite(*self.position):
            if isinstance(pointed, UiElement) and pointed.active:
                self.update_mouse_pointed(pointed)
            else:
                self.pointed_gameobject = pointed
        else:
            self.pointed_gameobject = self.pointed_ui_element = None

    def get_pointed_sprite(self, x, y) -> Optional[Union[GameObject, UiElement]]:
        # Since we have many spritelists which are drawn in some
        # hierarchical order, we must iterate over them catching
        # cursor-pointed elements in backward order: last draw, is first to
        # be mouse-pointed (it lies on the top)
        if (pointed_sprite := self.dragged_ui_element) is None:
            for drawn in reversed(self.updated_spritelists):
                if not (pointed_sprite := self.cursor_points(drawn, x, y)):
                    continue
                else:
                    break
            else:
                return
        return pointed_sprite

    @staticmethod
    def cursor_points(spritelist: SpriteList, x, y) -> Optional[Sprite]:
        # Since our Sprites can have 'children' e.g. Buttons, which should
        # be first to interact with cursor, we discard all parents and seek
        # for first child, which is pointed instead:
        if pointed := get_sprites_at_point((x, y), spritelist):
            s: CursorInteractive
            for sprite in (s for s in pointed if isinstance(s, GameObject) or not s.children):
                return sprite  # first pointed children
            else:
                return pointed[0]  # return pointed Sprite if no children found

    def update_mouse_pointed(self, pointed: Optional[CursorInteractive]):
        if self.pointed_ui_element not in (None, pointed):
            self.pointed_ui_element.on_mouse_exit()
        if pointed is not None:
            pointed.on_mouse_enter()
        self.pointed_ui_element = pointed

    @property
    def pointed_unit(self) -> Optional[Unit]:
        if isinstance(pointed_gameobject := self.pointed_gameobject, Unit):
            return pointed_gameobject

    @property
    def pointed_building(self) -> Optional[Building]:
        if isinstance(pointed_gameobject := self.pointed_gameobject, Building):
            return pointed_gameobject


class MouseDragSelection:
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
        player_units = self.game.local_human_player.units
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
        # self.game.create_selection_markers(*units)  # TODO: selection markers

    def draw(self):
        """Draw rectangle showing borders of current selection."""
        left, right, top, bottom = self.left, self.right, self.top, self.bottom
        draw_lrtb_rectangle_filled(left, right, top, bottom, CLEAR_GREEN)
        draw_lrtb_rectangle_outline(left, right, top, bottom, GREEN)
