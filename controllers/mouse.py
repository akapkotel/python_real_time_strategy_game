#!/usr/bin/env python
from typing import List, Optional, Set, Tuple, Type, Union

from arcade import (
    AnimatedTimeBasedSprite, AnimationKeyframe, MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT, Sprite,
    SpriteList, Texture, Window, draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline, draw_text, get_sprites_at_point, load_texture,
    load_textures
)

from controllers.constants import *
from buildings.buildings import Building
from map.map import position_to_map_grid
from utils.colors import CLEAR_GREEN, GREEN, WHITE, RED, BLACK
from game import Game, UPDATE_RATE
from gameobjects.gameobject import GameObject, PlaceableGameobject
from utils.improved_spritelists import SelectiveSpriteList, UiSpriteList
from players_and_factions.player import PlayerEntity
from utils.scheduling import EventsCreator
from units.unit_management import UnitsManager
from units.units import Unit
from user_interface.user_interface import (
    CursorInteractive, ToggledElement, UiElement, ScrollableContainer,
    TextInputField
)

from utils.functions import get_path_to_file, ignore_in_menu
from utils.logging import logger

DrawnAndUpdated = Union[SpriteList, SelectiveSpriteList, 'MouseCursor']


class MouseCursor(AnimatedTimeBasedSprite, ToggledElement, EventsCreator):
    """
    MouseCursor replaces system-cursor with it's own Sprite and process all
    mouse-related calls from arcade.Window to call proper methods and functions
    when user operates with mouse.
    """
    window: Optional[Window] = None
    game: Optional[Game] = None
    instance: Optional['MouseCursor'] = None

    def __init__(self, window: Window, texture_name: str):
        super().__init__(texture_name)
        ToggledElement.__init__(self, active=False, visible=False)
        EventsCreator.__init__(self)
        self.window = window

        # textures-related:
        self.all_frames_lists: List[List[AnimationKeyframe]] = []
        self.load_textures()

        # cache currently updated and drawn spritelists of the active View:
        self._updated_spritelists: List[DrawnAndUpdated] = []

        self.mouse_dragging = False

        self.placeable_gameobject: Optional[PlaceableGameobject] = None

        self.dragged_ui_element: Optional[UiElement] = None
        self.pointed_ui_element: Optional[UiElement] = None
        self.pointed_gameobject: Optional[GameObject] = None
        self.pointed_scrollable: Optional[ScrollableContainer] = None
        self.bound_text_input_field: Optional[TextInputField] = None

        # player can select Units by dragging mouse cursor with left-button
        # pressed: all Units inside selection-rectangle will be added to the
        # selection:
        self.mouse_drag_selection: Optional[MouseDragSelection] = None

        # is set when new Game instance is created
        self.units_manager: Optional[UnitsManager] = None

        self.forced_cursor: Optional[int] = None

        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def load_textures(self):
        names = ('normal.png', 'forbidden.png', 'attack.png', 'select.png',
                 'move.png', 'enter.png')
        self.textures.extend(
            [load_texture(get_path_to_file(name)) for name in names[1:]]
        )  # without 'normal.png' since it is already loaded
        self.create_cursor_animations_frames(names)
        self.set_texture(CURSOR_NORMAL_TEXTURE)

    def create_cursor_animations_frames(self, names: Tuple[str, ...]):
        """
        For each is_loaded Texture we create a list of sub-textures which will
        be used to build lists of AnimationKeyframes utilised in
        on_animation_update method.
        """
        for i, texture in enumerate(self.textures):
            frames_count = texture.width // 60
            locations_list = [(60 * j, 0, 60, 60) for j in range(frames_count)]
            frames = load_textures(get_path_to_file(names[i]), locations_list)
            self.all_frames_lists.append(
                self.new_frames_list(frames)
            )

    @staticmethod
    def new_frames_list(frames: List[Texture]) -> List[AnimationKeyframe]:
        frames_count = len(frames)
        duration = (1 // frames_count)
        return [
            AnimationKeyframe(
                duration=duration, texture=frames[i], tile_id=i
            ) for i in range(frames_count)
        ]

    def bind_units_manager(self, manager: UnitsManager):
        self.units_manager = manager

    @property
    def updated_spritelists(self):
        return self._updated_spritelists

    @updated_spritelists.setter
    def updated_spritelists(self, value: List[SpriteList]):
        self._updated_spritelists = [
            v for v in value if isinstance(v, (SpriteList, SelectiveSpriteList))
        ]

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.position = x, y

    @logger()
    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_press(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_press(x, y, modifiers)
        elif button is MOUSE_BUTTON_MIDDLE:
            self.on_middle_button_press(x, y, modifiers)

    @logger()
    def on_left_button_press(self, x: float, y: float, modifiers: int):
        if (ui_element := self.pointed_ui_element) is not None:
            ui_element.on_mouse_press(MOUSE_BUTTON_LEFT)
            self.evaluate_mini_map_click(x, y)
        if self.bound_text_input_field not in (ui_element, None):
            self.unbind_text_input_field()

    @ignore_in_menu
    def evaluate_mini_map_click(self, x: float, y: float):
        left, _, bottom, _ = self.game.viewport
        x, y = x + left, y + bottom
        if (position := self.game.mini_map.cursor_inside(x, y)) is not None:
            if units := self.units_manager.selected_units:
                self.units_manager.on_terrain_click_with_units(*position, None, units)
            else:
                self.window.move_viewport_to_the_position(*position)

    @logger()
    def on_right_button_press(self, x: float, y: float, modifiers: int):
        self.placeable_gameobject = None
        if self.pointed_ui_element is not None:
            self.pointed_ui_element.on_mouse_press(MOUSE_BUTTON_RIGHT)

    @logger()
    def on_middle_button_press(self, x: float, y: float, modifiers: int):
        pass

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_release(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_release(x, y, modifiers)

    def on_left_button_release(self, x: float, y: float, modifiers: int):
        self.dragged_ui_element = None
        self.on_left_button_release_in_game(modifiers, x, y)

    @ignore_in_menu
    def on_left_button_release_in_game(self, modifiers, x, y):
        if self.mouse_drag_selection is None:
            if self.pointed_ui_element is None:
                self.units_manager.on_left_click_no_selection(modifiers, x, y)
        else:
            self.close_drag_selection()

    @ignore_in_menu
    def close_drag_selection(self):
        self.units_manager.unselect_all_selected()
        if units := [u for u in self.mouse_drag_selection.units]:
            self.units_manager.select_units(*units)
        self.mouse_drag_selection = None

    @ignore_in_menu
    def on_right_button_release(self, x: float, y: float, modifiers: int):
        if self.mouse_dragging:
            self.mouse_dragging = None
        elif self.pointed_ui_element is not None:
            pass
        elif self.units_manager.units_or_building_selected:
            self.units_manager.unselect_all_selected()
        else:
            self.units_manager.selected_building = None

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if buttons == MOUSE_BUTTON_LEFT:
            self.on_left_button_drag(dx, dy, x, y)
        elif buttons == MOUSE_BUTTON_RIGHT:
            self.move_viewport_with_mouse_drag(dx, dy)

    @ignore_in_menu
    def move_viewport_with_mouse_drag(self, dx, dy):
        self.mouse_dragging = True
        self.window.change_viewport(dx, dy)

    def on_left_button_drag(self, dx, dy, x, y):
        if self.window.is_game_running:
            self.left_mouse_drag_in_game(dx, dy, x, y)
        elif (ui_element := self.dragged_ui_element) is not None:
            ui_element.on_mouse_drag(x, y)

    def left_mouse_drag_in_game(self, dx, dy, x, y):
        if self.game.map.on_map_area(x, y):
            self.on_mouse_motion(x, y, dx, dy)
            if self.mouse_drag_selection is not None:
                self.update_drag_selection(x, y)
            else:
                self.mouse_drag_selection = MouseDragSelection(self.game, x, y)

    @ignore_in_menu
    def update_drag_selection(self, x, y):
        if self.pointed_ui_element is None:
            new, lost = self.mouse_drag_selection.update(x, y)
            self.units_manager.update_selection_markers_set(new, lost)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.pointed_scrollable is not None:
            self.pointed_scrollable.on_mouse_scroll(scroll_x, scroll_y)

    def update(self):
        super().update()
        if self.units_manager is not None:
            self.units_manager.update()
        self.update_cursor_pointed()
        self.update_cursor_texture()
        self.update_animation()

    def update_animation(self, delta_time: float = UPDATE_RATE):
        """
        Logic for selecting the proper texture to use.
        """
        self.cur_frame_idx += 1
        if self.cur_frame_idx >= len(self.frames):
            self.cur_frame_idx = 0
        self.texture = self.frames[self.cur_frame_idx].texture

    def update_cursor_pointed(self):
        """
        Search all Spritelists and DividedSpriteLists for any UiElements or
        GameObjects placed at the MouseCursor position.
        """
        pointed = self.get_pointed_sprite(*self.position)
        if isinstance(pointed, PlayerEntity):
            self.switch_selected_gameobject(pointed)
            self.update_mouse_pointed_ui_element(None)
        else:
            self.switch_selected_gameobject(None)
            self.update_mouse_pointed_ui_element(pointed)

    def switch_selected_gameobject(self, pointed: Optional[GameObject]):
        if self.pointed_gameobject is not pointed:
            if self.pointed_gameobject is not None:
                self.pointed_gameobject.on_mouse_exit()
            if pointed is not None and pointed.is_rendered:
                self.pointed_gameobject = pointed
                pointed.on_mouse_enter()
            else:
                self.pointed_gameobject = None

    def get_pointed_sprite(self, x, y) -> Optional[Union[PlayerEntity, UiElement]]:
        # Since we have many spritelists which are drawn_area in some
        # hierarchical order, we must iterate over them catching
        # cursor-pointed elements in backward order: last draw, is first to
        # be mouse-pointed (it lies on the top)
        if (pointed_sprite := self.dragged_ui_element) is None:
            for drawn in reversed(self._updated_spritelists):
                if not isinstance(drawn, (SelectiveSpriteList, UiSpriteList)):
                    continue
                if pointed_sprite := self.cursor_points(drawn, x, y):
                    break
            else:
                return
        return pointed_sprite

    def cursor_points(self, spritelist: SpriteList, x, y) -> Optional[Sprite]:
        if pointed := get_sprites_at_point((x, y), spritelist):
            if not isinstance(spritelist, UiSpriteList):
                return pointed[0]
            s: UiElement
            try:
                return [s.this_or_child(self) for s in pointed if s.active][-1]
            except IndexError:
                return

    def update_mouse_pointed_ui_element(self,
                                        pointed: Optional[CursorInteractive]):
        if pointed != self.pointed_ui_element:
            self.exit_current_pointed_element()
            self.enter_new_pointed_element(pointed)
        self.pointed_ui_element = pointed

    def exit_current_pointed_element(self):
        try:
            self.pointed_ui_element.on_mouse_exit()
        except AttributeError:
            pass

    def enter_new_pointed_element(self, pointed):
        try:
            pointed.on_mouse_enter(cursor=self)
        except AttributeError:
            pass

    def update_cursor_texture(self):
        if self.window.is_game_running:
            self.cursor_in_game()
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def cursor_in_game(self):
        if self.pointed_ui_element:
            self.set_texture(CURSOR_NORMAL_TEXTURE)
        elif (forced := self.forced_cursor) is not None:
            self.set_texture(forced)
        elif self.units_manager.selected_units:
            self.cursor_texture_with_units_selected()
        elif entity := (self.pointed_unit or self.pointed_building):
            self.cursor_texture_on_pointing_at_entity(entity)
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def cursor_texture_with_units_selected(self):
        if entity := (self.pointed_unit or self.pointed_building):
            self.cursor_on_entity_with_selected_units(entity)
        else:
            self.cursor_on_terrain_with_selected_units()

    def cursor_on_entity_with_selected_units(self, entity):
        if entity.selectable:
            self.set_texture(CURSOR_SELECTION_TEXTURE)
        elif entity.is_enemy(self.units_manager.selected_units[0]):
            self.set_texture(CURSOR_ATTACK_TEXTURE)

    def cursor_on_terrain_with_selected_units(self):
        grid = position_to_map_grid(*self.position)
        if self.game.map.walkable(grid) or grid in self.game.fog_of_war.unexplored:
            self.set_texture(CURSOR_MOVE_TEXTURE)
        else:
            self.set_texture(CURSOR_FORBIDDEN_TEXTURE)

    def cursor_texture_on_pointing_at_entity(self, entity: PlayerEntity):
        if entity.selectable:
            self.set_texture(CURSOR_SELECTION_TEXTURE)
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def set_texture(self, index: int):
        # we override the original method to work with AnimationKeyframe
        # lists which we set-up at cursor initialization. Instead of
        # displaying static texture we switch updated cursor animation:
        self.frames = self.all_frames_lists[index]

    def force_cursor(self, index: Optional[int]):
        self.forced_cursor = index

    @property
    def is_game_loaded_and_running(self) -> bool:
        return self.game is not None and self.game.is_running

    @property
    def pointed_unit(self) -> Optional[Unit]:
        return o if isinstance(o := self.pointed_gameobject, Unit) else None

    @property
    def pointed_building(self) -> Optional[Building]:
        return o if isinstance(o := self.pointed_gameobject, Building) else None

    def get_pointed_of_type(self, type_: Type) -> Optional[Type]:
        return o if isinstance(o := self.pointed_gameobject, type_) else None

    def bind_text_input_field(self, field: TextInputField):
        self.bound_text_input_field = field

    def unbind_text_input_field(self):
        self.bound_text_input_field.unbind_keyboard_handler()
        self.bound_text_input_field = None

    def draw(self):
        if (selection := self.mouse_drag_selection) is not None:
            selection.draw()
        super().draw()


class MouseDragSelection:
    """Class for mouse-selected_units rectangle-areas."""

    __slots__ = ["game", "start", "end", "left", "right", "top", "bottom",
                 "units"]

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

    def update(self, x: float, y: float) -> Tuple[Set[Unit], Set[Unit]]:
        """
        Update current Selection setting new shape of a rectangle-marker.

        :param x: float -- x coordinate of current closing corner
        :param y: float -- y coordinate of current closing corner
        """
        self.end = (x, y)  # actual mouse-cursor position
        self._calculate_selection_rectangle_bounds()
        return self._update_units()  # to update visible selection markers

    def _calculate_selection_rectangle_bounds(self):
        corners = self.start, self.end
        self.left, self.right = sorted([x[0] for x in corners])
        self.bottom, self.top = sorted([x[1] for x in corners])

    def _update_units(self) -> Tuple[Set[Unit], Set[Unit]]:
        """
        Update list of currently selected_units accordingly to the shape of
        the selection rectangle: units inside the shape are considered as
        'selected' and units outside the shape are not selected.
        """
        all_player_units = self.game.local_human_player.units
        units_to_add = set()
        units_to_discard = set()
        # check units if they should be selected or not:
        for unit in (u for u in all_player_units if u.selectable):
            if self._inside_selection_rect(*unit.position):
                if unit not in self.units:
                    units_to_add.add(unit)
            elif unit in self.units:
                units_to_discard.add(unit)
        # update selection units set:
        self._remove_units_from_selection(units_to_discard)
        self._add_units_to_selection(units_to_add)
        return units_to_add, units_to_discard

    def _inside_selection_rect(self, x: float, y: float) -> bool:
        return self.left < x < self.right and self.bottom < y < self.top

    def _remove_units_from_selection(self, units: Set[Unit]):
        self.units.difference_update(units)

    def _add_units_to_selection(self, units: Set[Unit]):
        self.units.update(units)

    def draw(self):
        """Draw rectangle showing borders of current selection."""
        left, right, top, bottom = self.left, self.right, self.top, self.bottom
        draw_lrtb_rectangle_filled(left, right, top, bottom, CLEAR_GREEN)
        draw_lrtb_rectangle_outline(left, right, top, bottom, GREEN)
        draw_text(str(len(self.units)), left, bottom, GREEN)
