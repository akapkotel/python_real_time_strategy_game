#!/usr/bin/env python
from __future__ import annotations

__title__ = 'RaTS: Real (almost) Time Strategy'
__author__ = 'Rafał "Akapkotel" Trąbski'
__license__ = "Share Alike Attribution-NonCommercial-ShareAlike 4.0"
__version__ = "0.0.3"
__maintainer__ = "Rafał Trąbski"
__email__ = "rafal.trabski@mises.pl"
__status__ = "development"
__credits__ = []

from functools import partial
from typing import (Any, Dict, List, Optional, Set, Union)

import arcade
from arcade import (
    SpriteList, create_line, draw_circle_outline, draw_line,
    draw_rectangle_filled, draw_text
)
from arcade.arcade_types import Color, Point

from colors import BLACK, GREEN, RED, WHITE
from improved_spritelists import DividedSpriteList, SpriteListWithSwitch
from data_types import Viewport

from observers import ObjectsOwner, OwnedObject
from scheduling import EventsCreator, EventsScheduler, ScheduledEvent
from user_interface import (
    Button, Checkbox, TextInputField, Frame
)
from user_interface import UiSpriteList
from utils.functions import (
    clamp, get_path_to_file, get_screen_size, log, timer, to_rgba
)
from views import LoadingScreen, WindowView, Updateable
from menu import Menu, UiElementsBundle, UiBundlesHandler

FULL_SCREEN = False
SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_size()
SCREEN_X, SCREEN_Y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
SCREEN_CENTER = SCREEN_X, SCREEN_Y

TILE_WIDTH = 60
TILE_HEIGHT = 60
SECTOR_SIZE = 8

GAME_SPEED = 1.0

UPDATE_RATE = 1 / (30 * GAME_SPEED)
PROFILING_LEVEL = 0  # higher the level, more functions will be time-profiled
PYPROFILER = True
DEBUG = False


def spawn_test_unit(position, unit_name: str, player: Player) -> Unit:
    unit_name = get_path_to_file(unit_name)
    return Unit(unit_name, player, UnitWeight.LIGHT, position)


class Window(arcade.Window, EventsCreator):

    def __init__(self, width: int, height: int, update_rate: float):
        arcade.Window.__init__(self, width, height, update_rate=update_rate)
        self.set_fullscreen(FULL_SCREEN)
        self.set_caption(__title__)
        self.center_window()

        self.events_scheduler = EventsScheduler(update_rate=update_rate)

        self._updated: List[Updateable] = []

        self.test_variable = False

        # views:
        self.menu_view = Menu()
        self.game_view: Optional[Game] = None
        self.create_submenus()

        self.show_view(LoadingScreen(loaded_view=self.menu_view))

        # cursor-related:
        self.cursor = MouseCursor(self, get_path_to_file('normal.png'))
        # store viewport data to avoid redundant get_viewport() calls and call
        # get_viewport only when viewport is actually changed:
        self.current_viewport = self.get_viewport()

        # keyboard-related:
        self.keyboard = KeyboardHandler(window=self)

    @property
    def screen_center(self) -> Point:
        left, _, bottom, _ = self.current_view.viewport
        return left + SCREEN_X, bottom + SCREEN_Y

    @property
    def updated(self) -> List[Updateable]:
        return self._updated

    @updated.setter
    def updated(self, value: List[Updateable]):
        self._updated = value
        try:
            self.cursor.updated_spritelists = value
        except AttributeError:
            pass  # MouseCursor is not initialised yet

    def create_submenus(self):
        back_to_menu_button = Button(
            get_path_to_file('menu_button_back.png'), SCREEN_X, 400,
            function_on_left_click=partial(self.menu_view.switch_submenu_of_index, 0)
        )

        main_menu = UiElementsBundle(
            index=0,
            name='Main menu',
            elements=[
                Button(get_path_to_file('menu_button_quit.png'), SCREEN_X, 200,
                       function_on_left_click=self.close),
                Button(get_path_to_file('menu_button_options.png'), SCREEN_X, 400,
                       function_on_left_click=partial(
                           self.menu_view.switch_submenu_of_index, 1)),
                Button(get_path_to_file('menu_button_newgame.png'), SCREEN_X, 600,
                       function_on_left_click=self.start_new_game),
            ]
        )

        frame = Frame('', 500, 500, 500, 500, RED)
        options_menu = UiElementsBundle(
            index=1,
            name='Second menu',
            elements=[
                frame,
                back_to_menu_button,
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), SCREEN_X, 600,
                    parent=frame,
                    ticked=self.test_variable,
                    variable=(self, 'test_variable')
                )
            ]
        )
        self.menu_view.register(main_menu)
        self.menu_view.register(options_menu)

    @property
    def is_game_running(self) -> bool:
        return self.game_view is not None and self.current_view == self.game_view

    def start_new_game(self):
        self.game_view = Game()
        self.show_view(self.game_view)

    def on_update(self, delta_time: float):
        self.current_view.on_update(delta_time)
        if (cursor := self.cursor).active:
            cursor.update()
        self.events_scheduler.update()
        super().on_update(delta_time)

    def on_draw(self):
        self.clear()
        self.current_view.on_draw()
        if (cursor := self.cursor).visible:
            cursor.draw()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        if self.cursor.active:
            if self.current_view is self.game_view:
                left, _, bottom, _ = self.current_view.viewport
                self.cursor.on_mouse_motion(x + left, y + bottom, dx, dy)
            else:
                self.cursor.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if self.cursor.active:
            self.cursor.on_mouse_press(x, y, button, modifiers)

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        if self.cursor.active:
            left, _, bottom, _ = self.current_view.viewport
            self.cursor.on_mouse_release(x + left, y + bottom, button, modifiers)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.cursor.active:
            left, _, bottom, _ = self.current_view.viewport
            self.cursor.on_mouse_drag(x + left, y + bottom, dx, dy, buttons, modifiers)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.cursor.active:
            self.cursor.on_mouse_scroll(x, y, scroll_x, scroll_y)

    def on_key_press(self, symbol: int, modifiers: int):
        if self.keyboard.active:
            self.keyboard.on_key_press(symbol, modifiers)
            if symbol == arcade.key.ENTER:
                if self.game_view is not None and self.game_view.is_running:
                    spawn_test_unit(self.cursor.position, 'jeep_blue.png',
                                    self.game_view.players[2])

    def on_key_release(self, symbol: int, modifiers: int):
        self.keyboard.on_key_release(symbol, modifiers)

    def show_view(self, new_view: WindowView):
        if new_view.requires_loading:
            self.show_view(LoadingScreen(loaded_view=new_view))
        else:
            super().show_view(new_view)

    def toggle_mouse_and_keyboard(self, value: bool, only_mouse=False):
        try:
            self.cursor.active = value
            self.cursor.visible = value
            if not only_mouse:
                self.keyboard.active = value
        except AttributeError:
            pass

    def change_viewport(self, dx: float, dy: float):
        """
        Change displayed area accordingly to the current position of player
        in the game world. If not in game, return static menu viewport.
        """
        game_map = self.game_view.map
        left, right, bottom, top = self.get_viewport()
        new_left = clamp(left - dx, game_map.width - SCREEN_WIDTH, 0)
        new_bottom = clamp(bottom - dy, game_map.height - SCREEN_HEIGHT, 0)
        if self.is_game_running:
            self.game_view.update_interface_position(dx, dy)
        self.update_viewport_coordinates(new_bottom, new_left)

    def update_viewport_coordinates(self, new_bottom, new_left):
        new_right = new_left + SCREEN_WIDTH
        new_top = new_bottom + SCREEN_HEIGHT
        self.current_view.viewport = new_left, new_right, new_bottom, new_top
        self.set_viewport(new_left, new_right, new_bottom, new_top)

    def move_viewport_to_the_position(self, x: int, y: int):
        """
        Call it when Player clicked on the minimap or teleported to the
        position of selected permanent group of Units with numeric keys.
        """
        game_map = self.game_view.map
        new_left = clamp(x - SCREEN_X, game_map.width - SCREEN_WIDTH, 0)
        new_bottom = clamp(y - SCREEN_Y, game_map.height - SCREEN_HEIGHT, 0)
        self.update_viewport_coordinates(new_bottom, new_left)

    def get_viewport(self) -> Viewport:
        # We cache viewport coordinates each time they are changed,
        # so no need for redundant call to the Window method
        return self.current_view.viewport

    def save_game(self):
        # TODO: save GameObject.total_objects_count (?)
        raise NotImplementedError

    def load_game(self):
        raise NotImplementedError

    def close(self):
        log(f'Terminating application...')
        super().close()


class Game(WindowView, EventsCreator, UiBundlesHandler):
    instance: Optional[Game] = None

    def __init__(self, debug: bool = DEBUG):
        WindowView.__init__(self, requires_loading=True)
        EventsCreator.__init__(self)
        UiBundlesHandler.__init__(self)
        self.assign_reference_to_self_for_all_classes()

        self.paused = False

        # SpriteLists:
        self.terrain_objects = SpriteListWithSwitch(is_static=True, update_on=False)
        self.vehicles_threads = SpriteList(is_static=True)
        self.buildings = DividedSpriteList(is_static=True)
        self.units = DividedSpriteList()
        self.selection_markers_sprites = SpriteList()
        self.interface: UiSpriteList() = self.create_interface()
        self.set_updated_and_drawn_lists()

        self.map = Map(100 * TILE_WIDTH, 50 * TILE_HEIGHT, TILE_WIDTH,
                       TILE_HEIGHT)
        self.pathfinder = Pathfinder(map=self.map)

        self.fog_of_war = FogOfWar()
        # we put FoW before the interface to list of rendered layers to
        # assure that FoW will not cover player interface:
        self.drawn.insert(-2, self.fog_of_war)

        # Settings, game-progress data, etc.
        self.player_configs: Dict[str, Any] = self.load_player_configs()

        # Units belongs to the Players, Players belongs to the Factions, which
        # are updated each frame to evaluate AI, enemies-visibility, etc.
        self.factions: Dict[int, Faction] = {}
        self.players: Dict[int, Player] = {}

        self.local_human_player: Optional[Player] = None
        # We only draw those Units and Buildings, which are 'known" to the
        # local human Player's Faction or belong to it, the rest of entities
        # is hidden. This set is updated each frame:
        self.local_drawn_units_and_buildings: Set[PlayerEntity] = set()

        # Player can create group of Units by CTRL + 0-9 keys, and then
        # select those groups quickly with 0-9 keys, or even move screen tp
        # the position of the group by pressing numeric key twice. See the
        # PermanentUnitsGroup class in units_management.py
        self.permanent_units_groups: Dict[int, PermanentUnitsGroup] = {}

        self.missions: Dict[int, Mission] = {}
        self.current_mission: Optional[Mission] = None

        self.debug = debug
        self.debugged = []
        if debug:
            self.map_grid = self.create_map_debug_grid()

        self.test_methods()

    def assign_reference_to_self_for_all_classes(self):
        name = self.__class__.__name__.lower()
        for _class in (c for c in globals().values() if hasattr(c, name)):
            setattr(_class, name, self)
        Game.instance = self.window.cursor.game = self

    def create_interface(self) -> UiSpriteList:
        interface = UiSpriteList()
        self.ui_elements_spritelist = interface
        right_panel_frame = Frame('', SCREEN_WIDTH * 0.9, SCREEN_Y,
                                  SCREEN_WIDTH // 5, SCREEN_HEIGHT, BLACK)
        right_panel = UiElementsBundle(
            name='right_panel',
            index=0,
            elements=[
                right_panel_frame,
            ]
        )
        right_panel.register_to_objectsowners(self)
        return interface

    def update_interface_position(self, dx, dy):
        print(dx)
        right, top = self.interface[0].right, self.interface[0].top
        if right - dx < SCREEN_WIDTH or right - dx > self.map.width:
            dx = 0
        if top - dy < SCREEN_HEIGHT or top - dy > self.map.height:
            dy = 0
        self.interface.move(-dx, -dy)

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)

    def test_methods(self):
        self.test_scheduling_events()
        self.test_factions_and_players_creation()
        self.test_units_spawning()
        self.test_buildings_spawning()

    def test_scheduling_events(self):
        event = ScheduledEvent(self, 2, self.scheduling_test, repeat=True)
        self.schedule_event(event)

    def test_factions_and_players_creation(self):
        faction = Faction(name='Freemen')
        player = Player(id=2, faction=faction, cpu=False)
        cpu_player = CpuPlayer()
        self.local_human_player: Optional[Player] = self.players[2]
        player.start_war_with(cpu_player)

    def test_units_spawning(self):
        player_units = self.spawn_local_human_player_units()
        cpu_units = self.spawn_cpu_units()
        self.units.extend(player_units + cpu_units)

    def spawn_local_human_player_units(self) -> List[Unit]:
        spawned_units = []
        player = self.players[2]
        name = 'jeep_blue.png'
        for x in range(30, SCREEN_WIDTH, TILE_WIDTH * 4):
            for y in range(30, SCREEN_HEIGHT, TILE_HEIGHT * 4):
                spawned_units.append(spawn_test_unit((x, y), name, player=player))
        return spawned_units

    def spawn_cpu_units(self) -> List[Unit]:
        spawned_units = []
        # name = "medic_truck_red.png"
        # player = self.players[4]
        # for x in range(90, SCREEN_WIDTH, TILE_WIDTH * 4):
        #     for y in range(90, SCREEN_HEIGHT, TILE_HEIGHT * 4):
        #         spawned_units.append(spawn_test_unit((x, y), name, player=player))
        return spawned_units

    def test_buildings_spawning(self):
        building = Building(
            get_path_to_file('building_dummy.png'),
            self.players[4],
            (400, 600),
            produces=Unit
        )
        self.buildings.append(building)

    def load_player_configs(self) -> Dict[str, Any]:
        configs: Dict[str, Any] = {}
        # TODO
        return configs

    @staticmethod
    def next_free_player_color() -> Color:
        return 0, 0, 0

    def register(self, acquired: OwnedObject):
        acquired: Union[Player, Faction, PlayerEntity, UiElementsBundle]
        if isinstance(acquired, (Unit, Building)):
            self.register_player_entity(acquired)
        elif isinstance(acquired, (Player, Faction)):
            self.register_player_or_faction(acquired)
        else:
            super().register(acquired)

    def register_player_entity(self, registered: Union[Unit, Building]):
        if not registered.is_building:
            self.units.append(registered)
        else:
            self.buildings.append(registered)

    def register_player_or_faction(self, registered: Union[Player, Faction]):
        if isinstance(registered, Player):
            self.players[registered.id] = registered
        else:
            self.factions[registered.id] = registered

    def unregister(self, owned: OwnedObject):
        owned: Union[PlayerEntity, Player, Faction, UiElementsBundle]
        if isinstance(owned, PlayerEntity):
            self.unregister_player_entity(owned)
        elif isinstance(owned, (Player, Faction)):
            self.unregister_player_or_faction(owned)
        else:
            super().unregister(owned)

    def unregister_player_entity(self, owned: PlayerEntity):
        owned: Union[Unit, Building]
        if not owned.is_building:
            self.units.remove(owned)
        else:
            self.buildings.remove(owned)

    def unregister_player_or_faction(self, owned: Union[Player, Faction]):
        if isinstance(owned, Player):
            del self.players[owned.id]
        else:
            del self.factions[owned.id]

    def get_notified(self, *args, **kwargs):
        pass

    @timer(level=1, global_profiling_level=PROFILING_LEVEL)
    def on_update(self, delta_time: float):
        if not self.paused:
            self.update_local_drawn_units_and_buildings()
            # GameObject.move_all_instances()
            super().on_update(delta_time)
            self.pathfinder.update()
            self.fog_of_war.update()
            self.update_factions_and_players()

    def update_local_drawn_units_and_buildings(self):
        self.local_drawn_units_and_buildings.clear()
        local_faction = self.local_human_player.faction
        self.local_drawn_units_and_buildings.update(
            local_faction.units,
            local_faction.buildings,
            local_faction.known_enemies
        )

    def update_factions_and_players(self):
        for faction in self.factions.values():
            faction.update()

    @timer(level=1, global_profiling_level=PROFILING_LEVEL)
    def on_draw(self):
        super().on_draw()
        if self.debug:
            self.draw_debugging()
        if self.paused:
            self.draw_paused_dialog()

    @timer(level=3, global_profiling_level=PROFILING_LEVEL)
    def draw_debugging(self):
        if self.map_grid is None:
            self.map_grid = self.create_map_debug_grid()
        self.draw_debugged_map_grid()
        self.draw_debugged_mouse_pointed_nodes()
        self.draw_debugged()

    def draw_debugged_map_grid(self):
        self.map_grid.draw()

    def draw_debugged_mouse_pointed_nodes(self):
        position = self.map.normalize_position(*self.window.cursor.position)
        node = self.map.position_to_node(*position)

        draw_circle_outline(node.x, node.y, 10, RED, 2)

        for adj in node.adjacent_nodes + [node]:
            color = to_rgba(WHITE, 25) if adj.walkable else to_rgba(RED, 25)
            draw_rectangle_filled(adj.x, adj.y, TILE_WIDTH,
                                         TILE_HEIGHT, color)
            draw_circle_outline(*adj.position, 5, WHITE, 1)

    def draw_debugged(self):
        self.draw_debug_paths()
        self.draw_debug_lines_of_sight()

    def draw_debug_paths(self):
        for path in (u.path for u in self.local_human_player.units if u.path):
            for i, point in enumerate(path):
                try:
                    end = path[i + 1]
                    draw_line(*point, *end, GREEN, 1)
                except IndexError:
                    pass

    def draw_debug_lines_of_sight(self):
        for unit in (u for u in self.local_human_player.units if u.known_enemies):
            for enemy in unit.known_enemies:
                draw_line(*unit.position, *enemy.position, RED)

    def draw_paused_dialog(self):
        x, y = self.window.screen_center
        draw_rectangle_filled(x, y, SCREEN_WIDTH, 200, to_rgba(BLACK, 150))
        draw_text('GAME PAUSED', x, y, WHITE, 30, anchor_x='center', anchor_y='center')

    def toggle_pause(self):
        self.paused = paused = not self.paused
        self.window.toggle_mouse_and_keyboard(not paused, only_mouse=True)

    def create_map_debug_grid(self) -> arcade.ShapeElementList:
        grid = arcade.ShapeElementList()
        # horizontal lines:
        for i in range(self.map.rows):
            y = i * TILE_HEIGHT
            h_line = create_line(0, y, self.map.width, y, BLACK)
            grid.append(h_line)

            y = i * TILE_HEIGHT + TILE_HEIGHT // 2
            h2_line = create_line(TILE_WIDTH // 2, y, self.map.width, y, WHITE)
            grid.append(h2_line)
        # vertical lines:
        for j in range(self.map.columns * 2):
            x = j * TILE_WIDTH
            v_line = create_line(x, 0, x, self.map.height, BLACK)
            grid.append(v_line)

            x = j * TILE_WIDTH + TILE_WIDTH // 2
            v2_line = create_line(x, TILE_HEIGHT // 2, x, self.map.height, WHITE)
            grid.append(v2_line)
        return grid


def start_profilling_code_execution():
    try:
        from pyprofiler import start_profile, end_profile
        profiler = start_profile()
        return end_profile, profiler
    except Exception as e:
        log(str(e), console=True)
        return None, None

def end_profilling_code_execution(profiler):
    try:
        # noinspection PyUnboundLocalVariable
        end_profile(profiler, 30, True)
    except NameError:
        pass


if __name__ == '__main__':
    # these imports are placed here to avoid circular-imports issue:
    from map import Map, Pathfinder
    from unit_management import PermanentUnitsGroup, SelectedEntityMarker
    from player import Faction, Player, CpuPlayer, PlayerEntity
    from keyboard_handling import KeyboardHandler
    from mouse_handling import MouseCursor
    from units import Unit, UnitWeight
    from fog_of_war import FogOfWar
    from buildings import Building
    from missions import Mission

    if PYPROFILER:
        end_profile, profiler = start_profilling_code_execution()
    window = Window(SCREEN_WIDTH, SCREEN_HEIGHT, UPDATE_RATE)
    arcade.run()

    if PYPROFILER and profiler is not None:
        end_profilling_code_execution(profiler)
