#!/usr/bin/env python

from typing import List, Optional, Set, Tuple, Type, Union

from arcade import (
    AnimatedTimeBasedSprite, AnimationKeyframe, MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT, Sprite,
    SpriteList, Texture, Window, draw_lrtb_rectangle_filled,
    draw_lrtb_rectangle_outline, draw_text, get_sprites_at_point, load_texture,
    load_textures
)

from buildings.buildings import Building
from utils.colors import CLEAR_GREEN, GREEN
from game import Game, UPDATE_RATE
from gameobjects.gameobject import GameObject
from utils.improved_spritelists import SelectiveSpriteList
from players_and_factions.player import PlayerEntity
from utils.scheduling import EventsCreator
from units.unit_management import SelectionUnitMarket
from units.units import Unit, UnitTask
from user_interface.user_interface import (
    CursorInteractive, ToggledElement, UiElement, UiSpriteList
)
from utils.classes import HashedList, Singleton
from utils.functions import get_path_to_file, log

DrawnAndUpdated = Union[SpriteList, SelectiveSpriteList, 'MouseCursor']

CURSOR_NORMAL_TEXTURE = 0
CURSOR_FORBIDDEN_TEXTURE = 1
CURSOR_ATTACK_TEXTURE = 2
CURSOR_SELECTION_TEXTURE = 3
CURSOR_MOVE_TEXTURE = 4
CURSOR_REPAIR_TEXTURE = 5


class MouseCursor(Singleton, AnimatedTimeBasedSprite, ToggledElement,
                  EventsCreator):
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
        self.selected_units: HashedList[Unit] = HashedList()
        self.selected_building: Optional[Building] = None
        # for each selected Unit create SelectedUnitMarker, a Sprite showing
        # that this unit is currently selected and will react for players's
        # actions. Sprites are actually drawn and updated in Game class,
        # but here we keep them cashed to easily manipulate them:
        self.selection_markers: Set[SelectionUnitMarket] = set()

        self.attached_task: Optional[UnitTask] = None

        self.forced_cursor: Optional[int] = None

        # hide system mouse cursor, since we render our own Sprite as cursor:
        self.window.set_mouse_visible(False)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}'

    def load_textures(self):
        names = ('normal.png', 'forbidden.png', 'attack.png', 'select.png',
                 'move.png')
        self.textures.extend(
            [load_texture(get_path_to_file(name)) for name in names[1:]]
        )  # without 'normal.png' since it is already loaded
        self.create_cursor_animations_frames(names)
        self.set_texture(CURSOR_NORMAL_TEXTURE)

    def create_cursor_animations_frames(self, names: Tuple[str, ...]):
        """
        For each loaded Texture we create a list of sub-textures which will
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
        if (ui_elem := self.pointed_ui_element) is not None and ui_elem.active:
            ui_elem.on_mouse_press(MOUSE_BUTTON_LEFT)

    def on_right_button_click(self, x: float, y: float, modifiers: int):
        log(f'Right-clicked at x:{x}, y: {y}')
        # TODO: clearing selections, context menu?

    def on_middle_button_click(self, x: float, y: float, modifiers: int):
        log(f'Middle-clicked at x:{x}, y: {y}')

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        if button is MOUSE_BUTTON_LEFT:
            self.on_left_button_release(x, y, modifiers)
        elif button is MOUSE_BUTTON_RIGHT:
            self.on_right_button_release(x, y, modifiers)

    def on_left_button_release(self, x: float, y: float, modifiers: int):
        if not self.pointed_ui_element:
            if self.mouse_drag_selection is None:
                units = self.selected_units
                pointed = self.pointed_unit or self.pointed_building
                if units:
                    self.on_click_with_selected_units(x, y, modifiers, units,
                                                      pointed)
                elif pointed is not None:
                    self.on_player_entity_clicked(pointed)
            else:
                self.close_drag_selection()

    def close_drag_selection(self):
        self.unselect_units()
        self.select_units(*[u for u in self.mouse_drag_selection.units])
        self.mouse_drag_selection = None

    def on_right_button_release(self, x: float, y: float, modifiers: int):
        self.forced_cursor = None
        if self.mouse_dragging:
            self.mouse_dragging = False
        elif self.selected_units:
            self.unselect_units()
        elif self.selected_building is not None:
            self.selected_building = None

    def on_player_entity_clicked(self, clicked: PlayerEntity):
        if clicked.selectable:
            self.on_friendly_player_entity_clicked(clicked)
        elif units := self.selected_units:
            self.on_hostile_player_entity_clicked(clicked, units)

    def on_friendly_player_entity_clicked(self, clicked: PlayerEntity):
        clicked: Union[Unit, Building]
        if not clicked.is_building:
            self.on_unit_clicked(clicked)
        else:
            self.on_building_clicked(clicked)

    def on_hostile_player_entity_clicked(self, clicked: PlayerEntity, units):
        cx, cy = clicked.position
        x, y = self.game.pathfinder.get_closest_walkable_position(cx, cy)
        self.send_units_to_pointed_location(units, x, y)

    def on_click_with_selected_units(self, x, y, modifiers, units, pointed):
        pointed: Union[PlayerEntity, None]
        if pointed is not None:
            self.on_player_entity_clicked(pointed)
        elif self.game.map.position_to_node(x, y).pathable:
            self.send_units_to_pointed_location(units, x, y)

    def send_units_to_pointed_location(self, units, x, y):
        waypoints = self.game.pathfinder.group_of_waypoints(x, y, len(units))
        for i, unit in enumerate(units):
            unit.move_to(waypoints[i])

    def on_unit_clicked(self, clicked_unit: Unit):
        self.unselect_units()
        self.select_units(clicked_unit)

    def select_units(self, *units: Unit):
        self.selected_units = HashedList(units)
        self.create_selection_markers(units)
        self.game.update_interface_content(context=units)

    def create_selection_markers(self, units):
        for unit in units:
            marker = SelectionUnitMarket(selected=unit)
            self.selection_markers.add(marker)

    def remove_from_selection_markers(self, entity: PlayerEntity):
        for marker in self.selection_markers:
            if marker.selected is entity:
                marker.kill()

    def unselect_units(self):
        self.selected_units.clear()
        self.clear_selection_markers()
        self.game.update_interface_content()

    def clear_selection_markers(self,
                                killed: Set[SelectionUnitMarket] = None):
        killed = killed if killed is not None else self.selection_markers
        for marker in killed:
            marker.kill()
        self.selection_markers.difference_update(killed)

    def on_building_clicked(self, clicked_building: Building):
        # TODO: resolving possible building-related tasks for units first
        self.selected_building = clicked_building
        self.game.update_interface_content(context=clicked_building)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.is_game_loaded_and_running:
            if buttons == MOUSE_BUTTON_LEFT:
                self.on_left_button_drag(dx, dy, x, y)
            elif buttons == MOUSE_BUTTON_RIGHT:
                self.mouse_dragging = True
                self.game.window.change_viewport(dx, dy)

    def on_left_button_drag(self, dx, dy, x, y):
        if self.game.map.on_map_area(x, y):
            self.on_mouse_motion(x, y, dx, dy)
            if self.mouse_drag_selection is not None:
                new, lost = self.mouse_drag_selection.update(x, y)
                self.update_selection_markers_set(new, lost)
            else:
                self.mouse_drag_selection = MouseDragSelection(self.game, x, y)

    def update_selection_markers_set(self, new, lost):
        discarded = {m for m in self.selection_markers if m.selected in lost}
        self.clear_selection_markers(discarded)
        self.create_selection_markers(new)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        # TODO
        raise NotImplementedError

    def update(self):
        super().update()
        self.update_selection_markers()
        self.update_cursor_pointed()
        self.update_cursor_texture()
        self.update_animation()

    def update_selection_markers(self):
        for marker in self.selection_markers:
            marker.update()

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
            self.pointed_gameobject = pointed if pointed.rendered else None
            self.update_mouse_pointed_ui_element(None)
        else:
            self.pointed_gameobject = None
            self.update_mouse_pointed_ui_element(pointed)

    def get_pointed_sprite(self, x, y) -> Optional[Union[PlayerEntity, UiElement]]:
        # Since we have many spritelists which are drawn in some
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

    @staticmethod
    def cursor_points(spritelist: SpriteList, x, y) -> Optional[Sprite]:
        # Since our Sprites can have 'children' e.g. Buttons, which should
        # be first to interact with cursor, we discard all parents and seek
        # for first child, which is pointed instead:
        if pointed := get_sprites_at_point((x, y), spritelist):
            s: Union[CursorInteractive, PlayerEntity]
            for sprite in (s for s in pointed if not getattr(s, 'children', False)):
                return sprite  # first pointed children
            else:
                return pointed[0]  # return pointed Sprite if no children found

    def update_mouse_pointed_ui_element(self,
                                        pointed: Optional[CursorInteractive]):
        if pointed != self.pointed_ui_element:
            if hasattr(self.pointed_ui_element, 'on_mouse_exit'):
                self.pointed_ui_element.on_mouse_exit()
            if hasattr(pointed, 'on_mouse_enter'):
                pointed.on_mouse_enter(cursor=self)
        self.pointed_ui_element = pointed

    def update_cursor_texture(self):
        if self.is_game_loaded_and_running:
            if self.pointed_ui_element:
                self.set_texture(CURSOR_NORMAL_TEXTURE)
            elif (forced := self.forced_cursor) is not None:
                self.set_texture(forced)
            elif self.selected_units:
                return self.cursor_texture_with_units_selected()
            elif entity := (self.pointed_unit or self.pointed_building):
                return self.cursor_texture_on_pointing_at_entity(entity)
        self.set_texture(CURSOR_NORMAL_TEXTURE)

    def cursor_texture_with_units_selected(self):
        if entity := (self.pointed_unit or self.pointed_building):
            if entity.selectable:
                self.set_texture(CURSOR_SELECTION_TEXTURE)
            elif entity.is_enemy(self.selected_units[0]):
                self.set_texture(CURSOR_ATTACK_TEXTURE)
        elif self.game.map.position_to_node(*self.position).walkable:
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

    def force_cursor(self, index: int):
        self.forced_cursor = index

    @property
    def is_game_loaded_and_running(self) -> bool:
        return self.game is not None and self.game.is_running

    @property
    def pointed_unit(self) -> Optional[Unit]:
        return o if isinstance(o := self.pointed_gameobject, Unit) else None

    @property
    def pointed_building(self) -> Optional[Building]:
        return o if isinstance(o := self.pointed_gameobject,
                               Building) else None

    def get_pointed_of_type(self, type_: Type) -> Optional[Type]:
        return o if isinstance(o := self.pointed_gameobject, type_) else None

    def draw(self):
        if (selection := self.mouse_drag_selection) is not None:
            selection.draw()
        super().draw()
        if self.is_game_loaded_and_running and self.game.window.debug:
            self.draw_selected_units_counter()

    def draw_selected_units_counter(self):
        x, y = self.position
        draw_text(str(len(self.selected_units)), x, y - 50, GREEN)


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
