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

import random
import time

from typing import (Any, Dict, Tuple, List, Optional, Set, Union, Generator)

from functools import partial
from dataclasses import dataclass
from arcade import (
    SpriteList, Window, draw_rectangle_filled, draw_text, run
)
from arcade.arcade_types import Color, Point

from effects.sound import AudioPlayer
from persistency.configs_handling import read_csv_files
from user_interface.user_interface import (
    Frame, Button, UiBundlesHandler, UiElementsBundle, UiSpriteList,
    ScrollableContainer
)
from utils.colors import BLACK, GREEN, RED, WHITE
from utils.data_types import Viewport
from utils.functions import (
    get_path_to_file, get_screen_size, to_rgba,
    SEPARATOR
)
from utils.logging import log, logger, timer
from utils.geometry import clamp, average_position_of_points_group
from utils.improved_spritelists import (
    SelectiveSpriteList, SpriteListWithSwitch
)
from utils.ownership_relations import OwnedObject
from utils.scheduling import EventsCreator, EventsScheduler, ScheduledEvent
from utils.views import LoadingScreen, LoadableWindowView, Updateable

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!
BASIC_UI = 'basic_ui'
EDITOR = 'editor'
BUILDINGS_PANEL = 'building_panel'
UNITS_PANEL = 'units_panel'

FULL_SCREEN = False
SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_size()
SCREEN_X, SCREEN_Y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
SCREEN_CENTER = SCREEN_X, SCREEN_Y
MINIMAP_WIDTH = 380
MINIMAP_HEIGHT = 200

TILE_WIDTH = 60
TILE_HEIGHT = 40
SECTOR_SIZE = 8
ROWS = 40
COLUMNS = 60

FPS = 30
GAME_SPEED = 1.0

PLAYER_UNITS = 24
CPU_UNITS = 10

UPDATE_RATE = 1 / (FPS * GAME_SPEED)
PROFILING_LEVEL = 0  # higher the level, more functions will be time-profiled
PYPROFILER = False
DEBUG = False


@dataclass
class Settings:
    """
    Just a simple data container for convenient storage and acces to bunch of
    minor variables, which would overcrowd Window __init__.
    """
    fps: int = FPS
    full_screen: bool = FULL_SCREEN
    debug: bool = DEBUG
    debug_mouse: bool = False
    debug_map: bool = False
    vehicles_threads: bool = True
    threads_fadeout: int = 2
    shot_blasts: bool = True
    game_speed: float = GAME_SPEED
    editor_mode: bool = True


class GameWindow(Window, EventsCreator):
    """
    This class represents the whole window-application which allows player to
    manage his saved games, start new games, change settings etc.
    """

    def __init__(self, width: int, height: int, update_rate: float):
        Window.__init__(self, width, height, update_rate=update_rate)
        self.set_fullscreen(FULL_SCREEN)
        self.set_caption(__title__)

        self.settings = Settings()  # shared with Game

        self.events_scheduler = EventsScheduler(update_rate=update_rate)

        self.sound_player = AudioPlayer()

        self.save_manger = SaveManager('saved_games', 'scenarios')

        self._updated: List[Updateable] = []

        # Settings, gameobjects configs, game-progress data, etc.
        self.configs = read_csv_files('resources/configs')

        # views:
        self._current_view: Optional[LoadableWindowView] = None

        self.menu_view: Menu = Menu()
        self.game_view: Optional[Game] = None
        # self.menu_view.create_submenus()

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
    def current_view(self) -> LoadableWindowView:
        return self._current_view

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

    def toggle_fullscreen(self):
        self.set_fullscreen(not self.fullscreen)
        if not self.fullscreen:
            self.set_size(SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)
            self.center_window()

    @property
    def is_game_running(self) -> bool:
        return self.game_view is not None and self.current_view == self.game_view

    def start_new_game(self):
        if self.game_view is None:
            self.game_view = Game(loader=None)
        self.show_view(self.game_view)

    def quit_current_game(self):
        self.game_view.unload()
        self.game_view = None
        self.show_view(self.menu_view)
        self.menu_view.toggle_game_related_buttons()

    @timer(level=1, global_profiling_level=PROFILING_LEVEL)
    def on_update(self, delta_time: float):
        log(f'Time: {delta_time}{SEPARATOR}', console=False)
        self.current_view.on_update(delta_time)
        if (cursor := self.cursor).active:
            cursor.update()
        self.events_scheduler.update()
        self.sound_player.on_update()
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

    def on_key_release(self, symbol: int, modifiers: int):
        self.keyboard.on_key_release(symbol, modifiers)

    def show_view(self, new_view: LoadableWindowView):
        if new_view.requires_loading:
            super().show_view(LoadingScreen(loaded_view=new_view))
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
        self.update_viewport_coordinates(new_bottom, new_left)

    def update_viewport_coordinates(self, new_bottom, new_left):
        new_right = new_left + SCREEN_WIDTH
        new_top = new_bottom + SCREEN_HEIGHT
        self.current_view.viewport = new_left, new_right, new_bottom, new_top
        self.set_viewport(new_left, new_right, new_bottom, new_top)
        if self.is_game_running:
            self.game_view.update_interface_position(new_right, new_top)

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
        self.save_manger.save_game('save_01', self.game_view)

    def load_game(self):
        if self.game_view is not None:
            self.quit_current_game()
        loader = self.save_manger.load_game(save_name='save_01')
        self.game_view = game = Game(loader=loader)
        self.show_view(game)

    def close(self):
        log(f'Terminating application...')
        super().close()


class Game(LoadableWindowView, EventsCreator, UiBundlesHandler):
    """This is an actual Game-instance, created when player starts the game."""
    instance: Optional[Game] = None

    def __init__(self, loader: Optional[Generator] = None):
        LoadableWindowView.__init__(self, loader)
        EventsCreator.__init__(self)
        UiBundlesHandler.__init__(self)
        self.assign_reference_to_self_for_all_classes()

        self.generate_random_entities = self.loader is None

        self.settings = self.window.settings  # shared with Window class
        self.timer = {'start': time.time(), 'total': 0, 'f': 0, 's': 0, 'm': 0, 'h': 0}
        self.dialog: Optional[Tuple[str, Color, Color]] = None

        # SpriteLists:
        self.terrain_tiles = SpriteListWithSwitch(is_static=True, update_on=False)
        self.vehicles_threads = SpriteList(is_static=True)
        self.units_ordered_destinations = UnitsOrderedDestinations()
        self.units = SelectiveSpriteList()
        self.static_objects = SpriteListWithSwitch(is_static=True, update_on=False)
        self.buildings = SelectiveSpriteList(is_static=True)
        self.effects = SpriteList(is_static=True)
        self.selection_markers_sprites = SpriteList()
        self.interface: UiSpriteList() = self.create_interface()
        self.set_updated_and_drawn_lists()

        self.map: Optional[Map] = None
        self.pathfinder: Optional[Pathfinder] = None

        self.fog_of_war: Optional[FogOfWar] = None

        # All GameObjects are initialized by the specialised factory:
        self.spawner: Optional[ObjectsFactory] = None

        self.explosions_pool: Optional[ExplosionsPool] = None

        self.mini_map: Optional[MiniMap] = None

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

        self.current_mission: Optional[Mission] = None

        self.debugger: Optional[GameDebugger] = None

        # list used only when Game is randomly-generated:
        self.things_to_load = [
            ['map', Map, 0.35, {'rows': ROWS, 'columns': COLUMNS,
             'grid_width': TILE_WIDTH, 'grid_height': TILE_HEIGHT}],
            ['pathfinder', Pathfinder, 0.05, lambda: self.map],
            ['fog_of_war', FogOfWar, 0.25],
            ['spawner', ObjectsFactory, 0.05, lambda: self.pathfinder, lambda: self.window.configs],
            ['explosions_pool', ExplosionsPool, 0.10],
            ['mini_map', MiniMap, 0.10, ((SCREEN_WIDTH, SCREEN_HEIGHT),
                                         (MINIMAP_WIDTH, MINIMAP_HEIGHT),
                                         (TILE_WIDTH, TILE_HEIGHT), ROWS)],
            ['debugger', GameDebugger if self.settings.debug else None, 0.10]
        ] if self.loader is None else []

    def assign_reference_to_self_for_all_classes(self):
        name = self.__class__.__name__.lower()
        for _class in (c for c in globals().values() if hasattr(c, name)):
            setattr(_class, name, self)
        Game.instance = self.window.cursor.game = self

    def create_interface(self) -> UiSpriteList:
        ui_x, ui_y = SCREEN_WIDTH * 0.9, SCREEN_Y
        ui_size = SCREEN_WIDTH // 5, SCREEN_HEIGHT
        right_ui_panel = Frame('ui_right_panel.png', ui_x, ui_y, *ui_size)
        right_panel = UiElementsBundle(
            name=BASIC_UI,
            index=0,
            elements=[
                right_ui_panel,
                Button('game_button_menu.png', ui_x, 100,
                       functions=partial(
                           self.window.show_view, self.window.menu_view),
                       parent=right_ui_panel),
                Button('game_button_pause.png', ui_x - 100, 100,
                       functions=partial(self.toggle_pause),
                       parent=right_ui_panel)
            ],
            register_to=self
        )
        units_panel = UiElementsBundle(
            name=UNITS_PANEL,
            index=1,
            elements=[
                Button('game_button_stop.png', ui_x - 100, 800,
                       functions=self.stop_all_units),
                Button('game_button_attack.png', ui_x, 800,
                       functions=partial(self.window.cursor.force_cursor, 2))
            ],
            register_to=self
        )
        biuilding_panel = UiElementsBundle(
            name=BUILDINGS_PANEL,
            index=2,
            elements=[
                Button('game_button_stop.png', ui_x, 800),
            ],
            register_to=self
        )

        editor_panel = UiElementsBundle(
            name=EDITOR,
            index=3,
            elements=[
                ScrollableContainer('ui_scrollable_frame.png', ui_x, ui_y,
                                    'scrollable'),
            ],
            register_to=self,
        )
        editor_panel.extend(
            [
                Button('small_button_none.png', ui_x, 100 * i,
                       parent=editor_panel.elements[0]) for i in range(5)
            ]
        )
        return self.ui_elements_spritelist  # UiBundlesHandler attribute

    def update_interface_position(self, right, top):
        diff_x = right - self.interface[0].right
        diff_y = top - self.interface[0].top
        self.interface.move(diff_x, diff_y)
        self.update_not_displayed_bundles_positions(-diff_x, -diff_y)
        self.mini_map.update_position(diff_x, diff_y)

    def update_interface_content(self, context=None):
        """
        Change elements displayed in interface to proper for currently selected
        gameobjects giving player access to context-options.
        """
        self._unload_all(exception=BASIC_UI)
        if context:
            if isinstance(context, Building):
                self.configure_building_interface(context)
            else:
                self.configure_units_interface(context)

    def configure_building_interface(self, context: Building):
        self.load_bundle(name=('%s' % BUILDINGS_PANEL))

    def configure_units_interface(self, context: List[Unit]):
        self.load_bundle(name=('%s' % UNITS_PANEL))
        self.load_bundle(name=EDITOR)

    def create_effect(self, effect_type: Any, name: str, x, y):
        """
        Add animated sprite to the self.effects spritelist to display e.g.:
        explosions.
        """
        if effect_type == Explosion:
            effect = self.explosions_pool.get(name, x, y)
        else:
            return
        self.effects.append(effect)
        effect.play()

    def on_show_view(self):
        super().on_show_view()
        self.load_timer(self.timer)
        self.window.toggle_mouse_and_keyboard(True)
        self.window.sound_player.play_playlist('game')
        self.update_interface_content()

    def test_methods(self):
        if self.generate_random_entities:
            self.test_scheduling_events()
            self.test_factions_and_players_creation()
            # self.test_buildings_spawning()
            self.test_units_spawning()
            self.test_missions()
        position = average_position_of_points_group(
            [u.position for u in self.local_human_player.units]
        )
        self.window.move_viewport_to_the_position(*position)

    def test_scheduling_events(self):
        event = ScheduledEvent(self, 5, self.scheduling_test, repeat=True)
        self.schedule_event(event)

    def test_factions_and_players_creation(self):
        faction = Faction(name='Freemen')
        player = Player(id=2, color=RED, faction=faction)
        cpu_player = CpuPlayer(color=GREEN)
        self.local_human_player: Optional[Player] = self.players[2]
        player.start_war_with(cpu_player)

    def test_buildings_spawning(self):
        self.buildings.append(self.spawn(
            'medium_factory.png',
            self.players[2],
            (400, 600),
        ))

    def spawn(self,
              object_name: str,
              player: Union[Player, int],
              position: Point,
              id: Optional[int] = None) -> Optional[GameObject]:
        if (player := self.get_player_instance(player)) is not None:
            return self.spawner.spawn(object_name, player, position, id=id)
        return None

    def get_player_instance(self, player: Union[Player, int]):
        if isinstance(player, int):
            try:
                return self.players[player]
            except KeyError:
                return None
        return player

    def spawn_group(self,
                    names: List[str],
                    player: Union[Player, int],
                    position: Point):
        if (player := self.get_player_instance(player)) is not None:
            return self.spawner.spawn_group(names, player, position)
        return None

    def test_units_spawning(self):
        spawned_units = []
        unit_name = 'tank_medium.png'
        for player in (self.players.values()):
            node = random.choice(list(self.map.nodes.values()))
            amount = CPU_UNITS if player.id == 4 else PLAYER_UNITS
            names = [unit_name] * amount
            spawned_units.extend(
                self.spawn_group(names, player, node.position)
            )
        self.units.extend(spawned_units)

    def test_missions(self):
        self.current_mission = mission = Mission(1, 'Test Mission', 'Map 1')
        mission.add()

        map_revealed = MapRevealed(self.local_human_player).set_vp(1)
        mission.new_condition(map_revealed, optional=True)

        no_units = NoUnitsLeft(self.local_human_player).set_vp(-1)
        mission.new_condition(no_units)

        timer = TimePassed(self.local_human_player, 15).set_vp(1)
        mission.new_condition(timer)

        cpu_player = self.players[4]
        cpu_no_units = NoUnitsLeft(cpu_player).set_vp(-1)
        mission.new_condition(cpu_no_units)

    def load_player_configs(self) -> Dict[str, Any]:
        configs: Dict[str, Any] = {}
        # TODO
        return configs

    @staticmethod
    def next_free_player_color() -> Color:
        return 0, 0, 0

    def register(self, acquired: OwnedObject):
        acquired: Union[Player, Faction, PlayerEntity, UiElementsBundle]
        if isinstance(acquired, GameObject):
            self.register_gameobject(acquired)
        elif isinstance(acquired, (Player, Faction)):
            self.register_player_or_faction(acquired)
        else:
            super().register(acquired)

    def register_gameobject(self, registered: GameObject):
        if isinstance(registered, PlayerEntity):
            if registered.is_building:
                self.buildings.append(registered)
            else:
                self.units.append(registered)
        else:
            self.terrain_tiles.append(registered)

    def register_player_or_faction(self, registered: Union[Player, Faction]):
        if isinstance(registered, Player):
            self.players[registered.id] = registered
        else:
            self.factions[registered.id] = registered

    def unregister(self, owned: OwnedObject):
        owned: Union[PlayerEntity, Player, Faction, UiElementsBundle]
        if isinstance(owned, GameObject):
            self.unregister_gameobject(owned)
        elif isinstance(owned, (Player, Faction)):
            self.unregister_player_or_faction(owned)
        else:
            super().unregister(owned)

    def unregister_gameobject(self, owned: GameObject):
        if isinstance(owned, PlayerEntity):
            if owned.is_building:
                self.buildings.remove(owned)
            else:
                self.units.remove(owned)
        else:
            self.terrain_tiles.remove(owned)

    def unregister_player_or_faction(self, owned: Union[Player, Faction]):
        if isinstance(owned, Player):
            del self.players[owned.id]
        else:
            del self.factions[owned.id]

    def get_notified(self, *args, **kwargs):
        pass

    def show_dialog(self, dialog_name: str):
        print(dialog_name)

    def update_view(self, delta_time):
        self.update_timer()
        if self.debugger is not None:
            self.debugger.update()
        super().update_view(delta_time)
        self.update_local_drawn_units_and_buildings()
        self.update_factions_and_players()
        self.fog_of_war.update()
        self.pathfinder.update()
        self.mini_map.update()
        if self.current_mission is not None:
            self.current_mission.update()

    def after_loading(self):
        self.window.show_view(self)
        self.test_methods()
        # we put FoW before the interface to list of rendered layers to
        # assure that FoW will not cover player interface:
        self.drawn.insert(-2, self.fog_of_war)
        super().after_loading()

    def update_timer(self):
        seconds = time.time() - self.timer['start']
        game_time = time.gmtime(seconds)
        self.timer['f'] += 1
        self.timer['s'] = game_time.tm_sec
        self.timer['m'] = game_time.tm_min
        self.timer['h'] = game_time.tm_hour

    def save_timer(self):
        """Before saving timer, recalculate total time game was played."""
        self.timer['total'] = (time.time() - self.timer['start'])
        return self.timer

    @logger()
    def load_timer(self, loaded_timer):
        """
        Subtract total time played from loading time to correctly reset timer
        after loading game.
        """
        self.timer = loaded_timer
        self.timer['start'] = time.time() - loaded_timer['total']

    def update_local_drawn_units_and_buildings(self):
        """
        We draw on the screen only these PlayerEntities, which belongs to the
        local Player's Faction, or are detected by his Faction.
        """
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
        self.mini_map.draw()
        self.draw_timer()
        if self.debugger is not None:
            self.debugger.draw()
        if self.dialog is not None:
            self.draw_dialog(*self.dialog)

    def draw_timer(self):
        _, r, b, _ = self.viewport
        x, y = r - 270, b + 800
        t = self.timer
        f = format
        formatted = f"{f(t['h'], '02')}:{f(t['m'], '02')}:{f(t['s'], '02')}"
        draw_text(f"Time:{formatted}", x, y, GREEN, 15)

    def draw_dialog(self, text: str, txt_color: Color = WHITE, color: Color = BLACK):
        x, y = self.window.screen_center
        draw_rectangle_filled(x, y, SCREEN_WIDTH, 200, to_rgba(color, 150))
        draw_text(text, x, y, txt_color, 30, anchor_x='center', anchor_y='center')

    def toggle_pause(self, dialog: str = 'GAME PAUSED', color: Color = BLACK):
        super().toggle_pause()
        self.reset_dialog(*(dialog, color) if self.paused else (None, None))
        self.save_timer() if self.paused else self.load_timer(self.timer)
        self.window.toggle_mouse_and_keyboard(not self.paused, only_mouse=True)

    def reset_dialog(self, text: str = None, color: Color = BLACK, txt_color: Color = WHITE):
        if text is None:
            self.dialog = None
        else:
            self.dialog = (text, txt_color, color)

    def stop_all_units(self):
        for unit in self.window.cursor.selected_units:
            unit.stop_completely()

    def unload(self):
        self.updated.clear()
        self.local_human_player = None
        self.local_drawn_units_and_buildings.clear()
        self.factions.clear()
        self.players.clear()


if __name__ == '__main__':
    # these imports are placed here to avoid circular-imports issue:
    from map.map import Map, Pathfinder
    from units.unit_management import PermanentUnitsGroup, SelectedEntityMarker
    from effects.explosions import Explosion, ExplosionsPool
    from players_and_factions.player import (
        Faction, Player, CpuPlayer, PlayerEntity
    )
    from controllers.keyboard import KeyboardHandler
    from controllers.mouse import MouseCursor
    from units.units import Unit, UnitsOrderedDestinations
    from gameobjects.gameobject import GameObject
    from gameobjects.spawning import ObjectsFactory
    from map.fog_of_war import FogOfWar
    from buildings.buildings import Building
    from scenarios.missions import Mission
    from scenarios.conditions import NoUnitsLeft, MapRevealed, TimePassed
    from user_interface.menu import Menu
    from user_interface.minimap import MiniMap
    from utils.debugging import GameDebugger
    from persistency.save_handling import SaveManager

    if __status__ == 'development' and PYPROFILER:
        from pyprofiler import start_profile, end_profile
        with start_profile() as profiler:
            window = GameWindow(SCREEN_WIDTH, SCREEN_HEIGHT, UPDATE_RATE)
            run()
        end_profile(profiler, 35, True)
    else:
        window = GameWindow(SCREEN_WIDTH, SCREEN_HEIGHT, UPDATE_RATE)
        run()
