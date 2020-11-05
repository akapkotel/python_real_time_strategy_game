#!/usr/bin/env python

from typing import Optional, Set, List, Union
from arcade import (
    Window, AnimatedTimeBasedSprite, SpriteList, draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline, get_sprites_at_point, load_texture, Sprite,
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE, draw_text,
    Texture
)

from user_interface import ToggledElement, UiElement, CursorInteractive
from utils.functions import log, get_path_to_file
from data_containers import DividedSpriteList
from colors import GREEN, CLEAR_GREEN
from scheduling import EventsCreator
from gameobject import GameObject
from player import PlayerEntity
from buildings import Building
from data_types import Point
from game import Game, Menu
from units import Unit, Vehicle, UnitTask


DrawnAndUpdated = Union[SpriteList, DividedSpriteList, 'MouseCursor']


CURSOR_NORMAL_TEXTURE = 0
CURSOR_FORBIDDEN_TEXTURE = 1
CURSOR_ATTACK_TEXTURE = 2
CURSOR_SELECTION_TEXTURE = 3
CURSOR_REPAIR_TEXTURE = 4


class MouseCursor(AnimatedTimeBasedSprite, ToggledElement, EventsCreator):
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
        super().__init__(texture_name)
        ToggledElement.__init__(self, active=False, visible=False)
        EventsCreator.__init__(self)
        self.window = window

        self.load_textures()

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
        self.selected_building: Optional[Building] = None

        self.attached_task: Optional[UnitTask] = None

        self.menu = self.window.menu_view
        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def load_textures(self):
        self.textures.extend([
            load_texture(get_path_to_file('forbidden.png')),
            load_texture(get_path_to_file('attack.png')),
            load_texture(get_path_to_file('select.png')),
        ])

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
            self.on_left_button_click(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_click(x, y, modifiers)
        elif button is MOUSE_BUTTON_MIDDLE:
            self.on_middle_button_click(x, y, modifiers)
        else:
            log(f'Unassigned mouse-button clicked: {button}')

    def on_left_button_click(self, x: float, y: float, modifiers: int):
        log(f'Left-clicked at x:{x}, y: {y}')

    def on_right_button_click(self, x: float, y: float, modifiers: int):
        log(f'Right-clicked at x:{x}, y: {y}')
        self.selected_units.clear()
        # TODO: clearing selections, context menu?

    def on_middle_button_click(self, x: float, y: float, modifiers: int):
        log(f'Middle-clicked at x:{x}, y: {y}')

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_release(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_release(x, y, modifiers)

    def on_left_button_release(self, x: float, y: float, modifiers: int):
        log(f'MouseCursor.on_left_button_release, position: {x, y}')
        if self.mouse_drag_selection is None:
            units = self.selected_units
            pointed = self.pointed_unit or self.pointed_building
            if units:
                self.on_click_with_selected_units(x, y, modifiers, units, pointed)
            elif pointed is not None:
                self.on_player_entity_clicked(pointed)
        else:
            self.close_drag_selection()

    def close_drag_selection(self):
        self.select_units(*[u for u in self.mouse_drag_selection.units])
        self.mouse_drag_selection = None

    def on_right_button_release(self, x: float, y: float, modifiers: int):
        if self.selected_units:
            self.unselect_units()

    def on_player_entity_clicked(self, clicked: PlayerEntity):
        log(f'Clicked PlayerEntity: {clicked}')
        clicked: Union[Unit, Building]
        if clicked.selectable:
            if isinstance(clicked, Unit):
                self.on_unit_clicked(clicked)
            else:
                self.on_building_clicked(clicked)

    def on_click_with_selected_units(self, x, y, modifiers, units, pointed):
        log(f'Called: on_click_with_selected_units')
        pointed: Union[PlayerEntity, None]
        if pointed is not None:
            return self.on_player_entity_clicked(pointed)
        waypoints = self.game.map.group_of_waypoints(x, y, len(units))
        for i, unit in enumerate(units):
            unit.move_to(waypoints[i])

    def on_unit_clicked(self, clicked_unit: Unit):
        self.select_units(clicked_unit)

    def select_units(self, *units: Unit):
        self.selected_units.clear()
        for unit in units:
            self.selected_units.add(unit)

    def unselect_units(self):
        self.selected_units.clear()

    def on_building_clicked(self, clicked_building: Building):
        if clicked_building.selectable:
            self.selected_building = clicked_building

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.game.map.on_map_area(x, y):
            self.on_mouse_motion(x, y, dx, dy)
            if self.mouse_drag_selection is not None:
                self.mouse_drag_selection.update(x, y)
            else:
                self.mouse_drag_selection = MouseDragSelection(self.game, x, y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        # TODO
        raise NotImplementedError

    def update(self):
        super().update()
        self.update_cursor_pointed()
        self.update_cursor_texture()

    def update_cursor_pointed(self):
        """
        Search all Spritelists and DividedSpriteLists for any UiElements or
        GameObjects placed at the MouseCursor position.
        """
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
            for drawn in reversed(self._updated_spritelists):
                if pointed_sprite := self.cursor_points(drawn, x, y):
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

    def update_cursor_texture(self):
        if self.is_game_loaded_and_running:
            if self.selected_units:
                self.cursor_with_units_selected()
            elif entity := (self.pointed_unit or self.pointed_building):
                self.cursor_on_pointing_at_entity(entity)

    def cursor_with_units_selected(self):
        if entity := (self.pointed_unit or self.pointed_building):
            if entity.selectable:
                self.show_selecting_texture()
            else:
                self.show_attack_texture()
        elif not self.game.map.position_to_node(*self.position).walkable:
            self.set_texture(CURSOR_FORBIDDEN_TEXTURE)
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def cursor_on_pointing_at_entity(self, entity: PlayerEntity):
        if entity.selectable:
            self.show_selecting_texture()
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def show_attack_texture(self):
        self.set_texture(CURSOR_ATTACK_TEXTURE)

    def show_selecting_texture(self):
        self.set_texture(CURSOR_SELECTION_TEXTURE)

    @property
    def is_game_loaded_and_running(self) -> bool:
        return self.game is not None and self.game.is_running

    @property
    def pointed_unit(self) -> Optional[Unit]:
        if isinstance(pointed_gameobject := self.pointed_gameobject, Unit):
            return pointed_gameobject

    @property
    def pointed_building(self) -> Optional[Building]:
        if isinstance(pointed_gameobject := self.pointed_gameobject, Building):
            return pointed_gameobject

    def draw(self):
        if (selection := self.mouse_drag_selection) is not None:
            selection.draw()
        super().draw()


class MouseDragSelection:
    """Class for mouse-selected_units rectangle-areas."""

    __slots__ = ["game", "start", "end", "left", "right", "top", "bottom", "units"]

    def __init__(self, game: Game, x: float, y: float):
        """
        Initialize new Selection with empty list of selected_units Units.

        :param x: float -- x coordinate of selection starting corner
        :param y: float -- y coordinate of selection starting corner
        """
        self.game = game
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
        draw_text(str(len(self.units)), left, bottom, GREEN)


class SelectionMarker:
    """
    This class produces rectangle-unit-selection markers showing that a
    particular Unit or Building is selected by player and displaying some
    info about selected, like health level or lack of fuel icon. Each marker
    can contain many Sprites which are dynamically created, updated and
    destroyed. You must cache SelectionMarker instances and their Sprites in
    distinct data-structures. Markers are stored in ordinary list and
    Sprites in SpriteLists.
    """
    rectangle_texture = "selection_rectangle.png"
    health_green_texture = "health_bar_green.png"
    health_yellow_texture = "health_bar_yellow.png"
    health_red_texture = "health_bar_red.png"
    commanding_star_texture = "commander_star.png"
    numbers_texture = "group_numbers.png"
    no_munitions_texture = "no_munitions.png"
    no_fuel_texture = "no_fuel.png"

    selection_markers_sprites = None  # for faster lookups, avoid .

    def __init__(self, selected_object):
        selected_object.selected = True
        self.selected = selected_object
        self.scale = max(selected_object.width, selected_object.height) / 25
        self.rectangle = self.create_selection_rectangle(selected_object, self.scale)
        self.health_bar_height = selected_object.height * 0.625
        self.health_bar_width = (30 * self.scale)
        self.health_bar_color = None
        self.health_bar = self.create_health_bar(selected_object, self.scale)
        self.index = 0
        self.optionals: List = []
        self.in_selection_markers_sprites = False

    def __str__(self):
        return f'SelectionMarker for {self.selected}'

    def create_selection_rectangle(self,
                                   selected: Union[Unit, Building],
                                   scale: float) -> Sprite:
        x, y = selected.position
        return Sprite(self.rectangle_texture, scale, center_x=x, center_y=y)

    def create_health_bar(self, selected, scale):
        x, y = selected.center_x, selected.center_y + self.health_bar_height
        # add textures in order: red, yellow, green to set their indexes to
        # 0, 1, 2 what allows us to toggle them by dividing health_ratio by
        # fixed number and cheaply decide which color of health bar to show
        hb = Sprite(self.health_red_texture, scale, center_x=x, center_y=y)
        hb.append_texture(load_texture(self.health_yellow_texture))
        hb.append_texture(load_texture(self.health_green_texture))
        return hb

    def append_marker_to_selection_markers_sprites(self):
        self.selection_markers_sprites.append(self.rectangle)
        self.selection_markers_sprites.append(self.health_bar)
        for optional in (o for o in self.optionals if o is not None):
            self.selection_markers_sprites.append(optional)

    def update(self) -> Union[Unit, Building]:
        if not self.in_selection_markers_sprites:
            self.append_marker_to_selection_markers_sprites()
            self.in_selection_markers_sprites = True
        selected = self.selected
        self.rectangle.position = selected.position
        self.update_health_bar(selected)
        self.index = 0
        return selected

    def set_health_bar_color(self, health_ratio: float) -> Texture:
        if health_ratio > 0.7:
            return self.health_green_texture
        return self.health_yellow_texture if health_ratio > 0.3 else self.health_red_texture

    def update_health_bar(self, selected: Union[Unit, Building]):
        health_ratio = selected.health / selected.max_health
        width = self.health_bar_width * health_ratio
        x = selected.center_x - (self.health_bar_width / 2) + width / 2
        y = selected.center_y + self.health_bar_height
        color = int(health_ratio // 0.4)
        if color != self.health_bar_color:
            self.change_health_bar_color(color)
        self.health_bar.width = width
        self.health_bar.set_position(x, y)

    def change_health_bar_color(self, color: int):
        # color is a index of Texture to be picked from self.textures
        self.health_bar_color = color
        self.health_bar.set_texture(color)

    def get_marker_position(self, selected: Union[Unit, Building]) -> Point:
        x = selected.center_x - selected.width + 14 * self.index
        y = selected.center_y + self.health_bar_height * 0.6
        self.index += 1
        return x, y

    def kill(self):
        log(f'Killed {self}')
        self.selected.selected = False
        self.rectangle.kill()
        self.health_bar.kill()
        self.kill_optionals()

    def kill_optionals(self):
        for optional in self.optionals:
            try:
                optional.kill()
            except AttributeError:
                pass


class UnitSelectionMarker(SelectionMarker):

    def __init__(self, selected_unit: Unit):
        super().__init__(selected_unit)
        self.number = None
        self.commander_star = None
        self.no_munitions_icon = None
        self.no_fuel_icon = None

    def update(self):
        selected = super().update()
        self.update_commanding_star(selected)
        self.update_group_number(selected)
        self.update_munitions_icon(selected)
        if isinstance(selected, Vehicle):
            self.update_fuel_icon(selected)

    def update_commanding_star(self, selected: Unit):
        if selected.commander:
            x, y = self.get_marker_position(selected)
            if self.commander_star is None:
                self.create_commander_star(x, y)
            else:
                self.commander_star.position = x, y
        elif self.commander_star is not None:
            self.commander_star.kill()
            self.commander_star = None

    def create_commander_star(self, x, y):
        self.commander_star = Sprite(
            self.commanding_star_texture, center_x=x, center_y=y)
        self.selection_markers_sprites.append(self.commander_star)
        self.optionals.append(self.commander_star)

    def update_group_number(self, selected: Unit):
        if selected.permanent_group_id is not None:
            cx = selected.center_x + selected.width
            cy = selected.center_y + self.health_bar_height * 0.6
            if self.number is None:
                self.create_group_number(selected, cx, cy)
            else:
                self.number.position = cx, cy
        elif self.number is not None:
            self.number.kill()
            self.number = None

    def create_group_number(self, selected: Unit, cx: float, cy: float):
        number = chr(selected.permanent_group_id)
        x, y, w, h = (int(number) - 1) * 14, 0, 14, 12
        self.number = Sprite(self.numbers_texture, 1, x, y, w, h, cx, cy)
        self.selection_markers_sprites.append(self.number)
        self.optionals.append(self.number)

    def update_munitions_icon(self, selected: Unit):
        if not selected.munitions:
            x, y = self.get_marker_position(selected)
            if self.no_munitions_icon is None:
                self.create_no_munitions_icon(x, y)
            else:
                self.no_munitions_icon.position = x, y
        elif self.no_munitions_icon is not None:
            self.no_munitions_icon.kill()
            self.no_munitions_icon = None

    def create_no_munitions_icon(self, x: float, y: float):
        self.no_munitions_icon = Sprite(self.no_munitions_texture,
                                              center_x=x, center_y=y)
        self.selection_markers_sprites.append(self.no_munitions_icon)
        self.optionals.append(self.no_munitions_icon)

    def update_fuel_icon(self, selected: Vehicle):
        if selected.fuel <= 0:
            x, y = self.get_marker_position(selected)
            if self.no_fuel_icon is None:
                self.create_fuel_icon(x, y)
            else:
                self.no_fuel_icon.position = x, y
        elif self.no_fuel_icon is not None:
            self.no_fuel_icon.kill()
            self.no_fuel_icon = None

    def create_fuel_icon(self, x: float, y: float):
        self.no_fuel_icon = Sprite(self.no_fuel_texture, center_x=x, center_y=y)
        self.selection_markers_sprites.append(self.no_fuel_icon)
        self.optionals.append(self.no_fuel_icon)


class BuildingSelectionMarker(SelectionMarker):

    def __init__(self, selected_building: Building):
        super().__init__(selected_building)

    def create_health_bar(self, selected, scale):
        health_bar = super().create_health_bar(selected, scale)
        health_bar.height *= 0.1
        return health_bar

    def update_health_bar(self, selected: Building):
        health_ratio = selected.health / selected.max_health
        width = self.health_bar_width * health_ratio
        x = selected.center_x - (self.health_bar_width / 2) + width / 2
        y = selected.center_y + self.health_bar_height
        color = int(health_ratio // 0.4)
        if color != self.health_bar_color:
            self.change_health_bar_color(color)
        self.health_bar.height = 10
        self.health_bar.width = width
        self.health_bar.set_position(x, y)
