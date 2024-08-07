#!/usr/bin/env python
from typing import List, Optional, Set, Tuple, Type, Union

from arcade import (
    AnimatedTimeBasedSprite,
    AnimationKeyframe,
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_RIGHT,
    Sprite,
    SpriteList,
    Texture,
    Window,
    draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline,
    draw_text,
    get_sprites_at_point,
    load_texture,
    load_textures,
    draw_lines
)

from buildings.buildings import Building
from map.map import position_to_map_grid
from utils.colors import CLEAR_GREEN, GREEN, BLACK, WHITE, RED, MAP_GREEN
from game import Game
from gameobjects.gameobject import GameObject, PlaceableGameObject
from utils.constants import CURSOR_NORMAL_TEXTURE, CURSOR_FORBIDDEN_TEXTURE, CURSOR_ATTACK_TEXTURE, \
    CURSOR_SELECTION_TEXTURE, CURSOR_MOVE_TEXTURE
from utils.data_types import Number
from utils.improved_spritelists import LayeredSpriteList, UiSpriteList
from players_and_factions.player import PlayerEntity
from utils.scheduling import EventsCreator
from units.unit_management import UnitsManager
from units.units import Unit
from user_interface.user_interface import (
    CursorInteractive,
    ToggledElement,
    UiElement,
    ScrollableContainer,
    TextInputField
)

from utils.functions import ignore_in_menu
from utils.game_logging import log_this_call

MOUSE_CURSOR_SIZE = 60

DrawnAndUpdated = Union[SpriteList, LayeredSpriteList, 'MouseCursor']


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
        self.animations_keyframes: List[List[AnimationKeyframe]] = []
        self.load_textures()
        self.frame_time = 0

        # cache currently updated and drawn spritelists of the active View:
        self._updated_spritelists: List[DrawnAndUpdated] = []

        self.mouse_dragging = False

        self.placeable_gameobject: Optional[PlaceableGameObject] = None

        self.dragged_ui_element: Optional[UiElement] = None
        self.pointed_ui_element: Optional[UiElement] = None
        self.selected_ui_element: Optional[UiElement] = None
        self.pointed_gameobject: Optional[GameObject] = None
        self.pointed_scrollable: Optional[ScrollableContainer] = None
        self.bound_text_input_field: Optional[TextInputField] = None

        self.show_hint = False
        self.text_hint_delay = self.window.settings.hints_delay_seconds

        # player can select Units by dragging mouse cursor with left-button
        # pressed: all Units inside selection-rectangle will be added to the
        # selection:
        self.mouse_drag_selection: Optional[MouseDragSelection] = None

        # is set when new Game instance is created
        self.units_manager: Optional[UnitsManager] = None

        self.forced_cursor: Optional[int] = None

        self.cursor_over_minimap_position: Optional[Tuple[int, int]] = None

        # used to change cursor color when placed over objects if they are friends or foes
        self.cursor_default_color = MAP_GREEN
        self.cross_color = self.cursor_default_color

        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def load_textures(self):
        names = ('normal.png', 'forbidden.png', 'attack.png', 'select.png',
                 'move.png', 'enter.png')
        self.textures.extend(
            [load_texture(self.window.resources_manager.get(name)) for name in names[1:]]
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
            frames_count = texture.width // MOUSE_CURSOR_SIZE
            locations_list = [(MOUSE_CURSOR_SIZE * j, 0, MOUSE_CURSOR_SIZE, MOUSE_CURSOR_SIZE) for j in range(frames_count)]
            frames = load_textures(self.window.resources_manager.get(names[i]), locations_list)
            duration = 1 / frames_count
            self.animations_keyframes.append(
                self.new_frames_list(frames, duration)
            )

    @staticmethod
    def new_frames_list(frames: List[Texture], duration: Number) -> List[AnimationKeyframe]:
        return [
            AnimationKeyframe(
                duration=duration, texture=frame, tile_id=i
            ) for i, frame in enumerate(frames)
        ]

    def bind_units_manager(self, manager: UnitsManager):
        self.units_manager = manager

    @property
    def updated_spritelists(self):
        return self._updated_spritelists

    @updated_spritelists.setter
    def updated_spritelists(self, value: List[SpriteList]):
        self._updated_spritelists = [
            v for v in value if isinstance(v, (SpriteList, LayeredSpriteList))
        ]

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.position = x, y
        if self.placeable_gameobject is not None:
            grid_x, grid_y = position_to_map_grid(x, y)
            self.placeable_gameobject.snap_to_the_map_grid(grid_x, grid_y)

    def attach_placeable_gameobject(self, gameobject_name: str):
        player = self.game.current_active_player
        self.placeable_gameobject = PlaceableGameObject(gameobject_name, player)

    def select_ui_element(self, element: Optional[UiElement] = None):
        self.selected_ui_element = element

    @log_this_call()
    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_press(x, y)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_press()

    @log_this_call()
    def on_left_button_press(self, x: float, y: float):
        if (ui_element := self.pointed_ui_element) is not None:
            ui_element.on_mouse_press(MOUSE_BUTTON_LEFT)
            self.evaluate_mini_map_click(MOUSE_BUTTON_LEFT)
        if self.bound_text_input_field not in (ui_element, None):
            self.unbind_text_input_field()
        if self.placeable_gameobject is not None and self.placeable_gameobject.is_construction_possible():
            self.placeable_gameobject.build()

    @ignore_in_menu
    def evaluate_mini_map_click(self, button: int):
        left, _, bottom, _ = self.game.viewport
        if self.cursor_over_minimap_position is not None:
            if button == MOUSE_BUTTON_RIGHT or not self.units_manager.selected_units:
                self.window.move_viewport_to_the_position(*self.cursor_over_minimap_position)
            elif units := self.units_manager.selected_units:
                self.units_manager.on_terrain_click_with_units(*self.cursor_over_minimap_position, units)

    @log_this_call()
    def on_right_button_press(self):
        if self.pointed_ui_element is not None:
            self.pointed_ui_element.on_mouse_press(MOUSE_BUTTON_RIGHT)
            self.evaluate_mini_map_click(MOUSE_BUTTON_RIGHT)

    def on_mouse_release(self, x: float, y: float, button: int):
        # TODO: fix issue with right-click over mini-map which clears all selected units and should not
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_release(x, y)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_release()

    def on_left_button_release(self, x: float, y: float):
        self.dragged_ui_element = None
        self.on_left_button_release_in_game(x, y)

    @ignore_in_menu
    def on_left_button_release_in_game(self, x, y):
        if self.mouse_drag_selection is None:
            if self.pointed_ui_element is None:
                self.units_manager.on_left_click_no_selection(x, y)
        else:
            self.close_drag_selection()

    @ignore_in_menu
    def close_drag_selection(self):
        if units := [u for u in self.mouse_drag_selection.units]:
            self.units_manager.select_units(*units)
        self.mouse_drag_selection = None

    @ignore_in_menu
    def on_right_button_release(self):
        if self.mouse_dragging:
            self.mouse_dragging = None
            return
        elif self.pointed_ui_element is not None:
            pass
        elif self.units_manager.units_or_building_selected:
            self.units_manager.unselect_all_selected()
        else:
            self.units_manager.selected_building = None
        self.placeable_gameobject = None

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int):
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
            ui_element.on_mouse_drag(dx, dy)

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

    def on_mouse_scroll(self, scroll_x: int, scroll_y: int):
        if self.pointed_scrollable is not None:
            self.pointed_scrollable.on_mouse_scroll(scroll_x, scroll_y)

    def update(self):
        super().update()
        if self.game is not None and self.game.mini_map is not None:
            self.cursor_over_minimap_position = self.game.mini_map.cursor_over_minimap(*self.position)
        if self.units_manager is not None:
            self.units_manager.update()
        if self.placeable_gameobject is not None:
            self.placeable_gameobject.update()
        self.update_cursor_pointed()
        self.update_cursor_texture()
        self.update_animation()

    def update_animation(self, delta_time: float = 1/60):
        """
        Logic for selecting the proper texture to use.
        """
        self.cur_frame_idx += 1
        if self.cur_frame_idx >= len(self.frames):
            self.cur_frame_idx = 0
        self.texture = self.frames[self.cur_frame_idx].texture

    def update_cursor_pointed(self):
        """
        Search all Spritelists and LayeredSpriteLists for any UiElements or
        GameObjects placed at the MouseCursor position.
        """
        pointed = self.get_pointed_sprite(*self.position)
        if isinstance(pointed, PlayerEntity):
            self.switch_pointed_gameobject(pointed)
            self.update_mouse_pointed_ui_element(None)
        else:
            self.switch_pointed_gameobject(None)
            self.update_mouse_pointed_ui_element(pointed)

    def switch_pointed_gameobject(self, pointed: Optional[GameObject]):
        if pointed is not self.pointed_gameobject:
            if self.pointed_gameobject is not None:
                self.pointed_gameobject.on_mouse_exit()
            if pointed is not None and pointed.is_rendered:
                self.set_pointed_gameobject(pointed)
            else:
                self.clear_pointed_gameobject()

    def set_pointed_gameobject(self, pointed):
        self.pointed_gameobject = pointed
        self.text_hint_delay += self.game.timer.total_game_time
        self.show_hint = True
        pointed.on_mouse_enter()
        self.set_cursor_cross_color(pointed)

    def clear_pointed_gameobject(self):
        self.pointed_gameobject = None
        self.text_hint_delay = self.window.settings.hints_delay_seconds
        self.show_hint = False
        self.cross_color = self.cursor_default_color

    def set_cursor_cross_color(self, pointed: PlayerEntity):
        if pointed.is_controlled_by_human_player:
            self.cross_color = GREEN
        else:
            self.cross_color = RED

    def get_pointed_sprite(self, x, y) -> Optional[Union[PlayerEntity, UiElement]]:
        # Since we have many spritelists which are drawn in some
        # hierarchical order, we must iterate over them catching
        # cursor-pointed elements in backward order: last draw, is first to
        # be mouse-pointed (it lies on the top)
        if (pointed_sprite := self.dragged_ui_element) is None:
            for drawn in reversed(self._updated_spritelists):
                if not isinstance(drawn, (LayeredSpriteList, UiSpriteList)):
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
        if not self.window.is_game_running:
            return self.set_texture(CURSOR_NORMAL_TEXTURE)
        if self.pointed_ui_element:
            self.set_texture(CURSOR_NORMAL_TEXTURE)
        elif (forced := self.forced_cursor) is not None:
            self.set_texture(forced)
        elif self.units_manager.selected_units:
            self.cursor_texture_with_units_selected()
        elif (entity := self.pointed_unit or self.pointed_building) is not None:
            self.cursor_texture_on_pointing_at_entity(entity)
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def cursor_texture_with_units_selected(self):
        if (entity := self.pointed_unit or self.pointed_building) is not None:
            self.cursor_on_entity_with_selected_units(entity)
        else:
            self.cursor_on_terrain_with_selected_units()

    def cursor_on_entity_with_selected_units(self, entity):
        if entity.is_controlled_by_human_player:
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
        if entity.is_controlled_by_human_player:
            self.set_texture(CURSOR_SELECTION_TEXTURE)
        else:
            self.set_texture(CURSOR_NORMAL_TEXTURE)

    def set_texture(self, index: int):
        # we override the original method to work with AnimationKeyframe
        # lists which we set up at cursor initialization. Instead of
        # displaying static texture we switch updated cursor animation:
        self.frames = self.animations_keyframes[index]

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
        # if self.placeable_gameobject is None:
        self.draw_cross_cursor()

        if self.show_hint and self.text_hint_delay <= self.game.timer.total_game_time:
            self.draw_text_hint(self.pointed_gameobject.text_hint)

        if (selection := self.mouse_drag_selection) is not None:
            selection.draw()

        if self.placeable_gameobject is not None and self.is_game_loaded_and_running and self.pointed_ui_element is None:
            self.placeable_gameobject.draw()

        super().draw()

    def draw_cross_cursor(self):
        color = self.cross_color
        cx, cy = self.position

        # debug cursor position over minimap
        # draw_text(f'{self.cursor_over_minimap_position}', cx, cy, RED)

        # debug cursor position over map
        # draw_text(f'{cx, cy}', cx, cy, RED)

        if self.game is not None and self.game.is_running:
            x, width, y, height = self.game.viewport
            draw_lines([(x, cy), (x + width, cy), (cx, y + height), (cx, y)], color=color, line_width=2)
        else:
            draw_lines([(0, cy), (self.window.width, cy), (cx, self.window.height), (cx, 0)], color=color, line_width=2)

    def draw_text_hint(self, text_hint: str):
        x, y = self.right, self.bottom
        right, top, bottom = x + 9 * len(text_hint), y + 10, y - 10
        draw_lrtb_rectangle_filled(x, right, top, bottom, BLACK)
        draw_lrtb_rectangle_outline(x, right, top, bottom, WHITE)
        draw_text(text_hint, x + 5, y, WHITE, 11, anchor_y='center')


class MouseDragSelection:
    """Class for ectangle-area inside which every Unit would be selected."""

    __slots__ = ["game", "start", "end", "left", "right", "top", "bottom",
                 "units", "all_selectable_units"]

    def __init__(self, game: Game, x: float, y: float):
        """
        Initialize new Selection with empty set of possibly_selected_units Units.

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
        self.units: Set[Unit] = set()
        self.all_selectable_units = self.find_all_selectable_units()

    def find_all_selectable_units(self):
        if self.game.editor_mode:
            return self.game.units
        else:
            return {u for u in self.game.local_human_player.units if u.is_rendered}

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
        self.left, self.right = sorted(x[0] for x in corners)
        self.bottom, self.top = sorted(x[1] for x in corners)

    def _update_units(self) -> Tuple[Set[Unit], Set[Unit]]:
        """
        Update list of currently selected_units accordingly to the shape of
        the selection rectangle: units inside the shape are considered as
        'selected' and units outside the shape are not selected.
        """
        new = {u for u in self.all_selectable_units if self._inside_selection_rect(*u.position)}
        added = new.difference(self.units)
        old = self.units.difference(new)
        self.units = new
        return added, old

    def _inside_selection_rect(self, x: float, y: float) -> bool:
        return self.left < x < self.right and self.bottom < y < self.top

    def draw(self):
        """Draw rectangle showing borders of current selection."""
        left, right, top, bottom = self.left, self.right, self.top, self.bottom
        draw_lrtb_rectangle_filled(left, right, top, bottom, CLEAR_GREEN)
        draw_lrtb_rectangle_outline(left, right, top, bottom, GREEN)
        # draw_text(str(len(self.units)), left, bottom, GREEN)
