#!/usr/bin/env python3
from __future__ import annotations

__title__ = 'Python Real Time Strategy Game'
__author__ = 'Rafał "Akapkotel" Trąbski'
__license__ = "Share Alike Attribution-NonCommercial-ShareAlike 4.0"
__version__ = "0.0.9"
__maintainer__ = "Rafał Trąbski"
__email__ = "rafal.trabski@mises.pl"
__status__ = "development"
__credits__ = {'Coding': __author__,
               'Graphics': __author__,
               'Testing': [__author__],
               'Music': [],
               'Sounds': []}

import random
import time
import pathlib

from typing import (Any, Dict, Tuple, List, Optional, Set, Union, Generator)
from functools import partial

import pyglet
from arcade import (
    SpriteList, Window, draw_rectangle_filled, draw_text, run, Sprite, get_screens, MOUSE_BUTTON_RIGHT
)
from arcade.arcade_types import Color, Point

from effects.sound import SoundPlayer
from utils.constants import TILE_WIDTH, TILE_HEIGHT, EDITOR, SAVED_GAMES, SCENARIO_EDITOR_MENU, LOADING_MENU, \
    SAVING_MENU, MAIN_MENU, MINIMAP_WIDTH, MINIMAP_HEIGHT, UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, UI_BUILDINGS_PANEL, \
    UI_UNITS_PANEL, UI_UNITS_CONSTRUCTION_PANEL, UI_BUILDINGS_CONSTRUCTION_PANEL, UI_TERRAIN_EDITING_PANEL
from persistency.configs_handling import read_csv_files
from persistency.resources_manager import ResourcesManager
from user_interface.user_interface import (
    Frame,
    Button,
    UiBundlesHandler,
    UiElementsBundle,
    TextInputField,
    UiTextLabel,
    UiElement,
    ProgressButton,
    Checkbox, UnitProductionCostsHint, Hint
)
from user_interface.localization import LocalizationManager
from utils.observer import Observed
from utils.colors import BLACK, GREEN, RED, WHITE, rgb_to_rgba, YELLOW
from utils.data_types import Viewport
from utils.functions import ignore_in_editor_mode
from utils.game_logging import log_here, log_this_call
from utils.timing import timer
from utils.geometry import clamp, average_position_of_points_group, generate_2d_grid
from utils.improved_spritelists import (
    LayeredSpriteList, SpriteListWithSwitch, UiSpriteList,
)
from utils.scheduling import EventsCreator, EventsScheduler
from utils.views import LoadingScreen, LoadableWindowView, Updateable

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!

SEPARATOR = '-' * 20

BEFORE_INTERFACE_LAYER = -2

GAME_PATH = pathlib.Path(__file__).parent.absolute()

SCREEN = get_screens()[0]
SCREEN_WIDTH, SCREEN_HEIGHT = SCREEN.width, SCREEN.height
SCREEN_CENTER = (SCREEN_X, SCREEN_Y) = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2

UI_WIDTH = SCREEN_WIDTH // 5

PLAYER_UNITS_COUNT = 5
CPU_UNITS_COUNT = 5

PROFILING_LEVEL = 0  # higher the level, more functions will be time-profiled


def ask_player_for_confirmation(position: Tuple, after_switch_to_bundle: str):
    """
    Use this function to decorate method you want, to be preceded by display of
    simple confirm-or-cancel dialog for the player. The dialog would be shown
    first, and after player clicks 'confirm' decorated method would be called.
    If player clicks 'cancel', method would be ignored and a UiElementsBundle
    of name provided in after_switch_to_bundle param is loaded.\n
    To IGNORE this prompt, pass special argument ignore_confirmation=True to
    the called decorated method - it will be digested by the internal wrapper,
    and will cause aborting of the dialog procedure, and decorated method is
    going to be executed instead.

    :param position: Tuple[x, y] -- position on which dialog will be centered
    :param after_switch_to_bundle: str -- name of the UiElementsBundle to be
    displayed after player makes choice.
    :return: Callable
    """
    def decorator(function):
        def wrapper(self, ignore_confirmation=False):
            if ignore_confirmation:
                return function(self)
            function_on_yes = partial(function, self)
            return self.menu_view.open_confirmation_dialog(
                position, after_switch_to_bundle, function_on_yes
            )
        return wrapper
    return decorator


class Settings:
    """This class will serve for permanently saving user-defined settings and restore them between games."""

    def __init__(self):
        self.developer_mode: bool = __status__ == "development"
        self.editor_mode: bool = False

        self.fps: int = 60
        self.game_speed: float = 1.0
        self.update_rate = 1 / (self.fps * self.game_speed)
        self.draw_fps_counter: bool = self.developer_mode and not self.editor_mode

        self.sound_on: bool = False
        self.music_on: bool = True
        self.sound_effects_on: bool = True

        self.sound_volume: float = 0.5
        self.music_volume: float = 1.0
        self.effects_volume: float = 1.0

        self.full_screen: bool = False
        self.pyprofiler: bool = False

        self.difficulty: int = 3

        self.immortal_player_units: bool = False
        self.immortal_cpu_units: bool = False
        self.ai_sleep: bool = False
        self.instant_production_time: bool = False
        self.unlimited_player_resources: bool = False
        self.unlimited_cpu_resources: bool = False
        self.fog_of_war: bool = True

        self.vehicles_threads: bool = True
        self.threads_fadeout_seconds: int = 2
        self.simplified_health_bars: bool = True

        self.shot_blasts: bool = True
        self.remove_wrecks_after_seconds: int = 30
        self.damage_randomness_factor = 0.25
        self.percent_chance_for_spawning_tree: float = 0.05

        self.resources_abundance: float = 0.01
        self.starting_resources: float = 0.5

        self.show_minimap: bool = True

        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        self.map_width: int = 100
        self.map_height: int = 100
        self.tile_width: int = TILE_WIDTH
        self.tile_height: int = TILE_HEIGHT

        self.hints_delay_seconds: float = 0.6
        self.scrolling_speed_factor: int = 15
        self.language: str = 'en'

        self.load_settings_from_file()

    def load_settings_from_file(self):
        with open('settings.cfg', 'r') as file:
            for line in file.readlines():
                uncommented = line.split(' #')[0]
                attribute, value = uncommented.split(' = ')
                if 'self' in value or '(' in value or ')' in value:
                    continue
                elif attribute == 'language':
                    self.__setattr__(attribute, str(value))
                else:
                    self.__setattr__(attribute, eval(value))


class GameWindow(Window, EventsCreator):
    """
    This class represents the whole window-application which allows player to
    manage his saved games, start new games, change settings etc.
    """

    def __init__(self, settings: Settings):
        Window.__init__(self, settings.screen_width, settings.screen_height, __title__, settings.full_screen, update_rate=settings.update_rate)
        EventsCreator.__init__(self)

        self.total_delta_time = 0
        self.frames = 0
        self.current_fps = 0

        self.settings = settings  # shared with Game
        self.resources_manager = ResourcesManager()
        self.localization_manager = LocalizationManager(default_language=settings.language)
        self.configs = read_csv_files('resources/configs')  # shared with Game

        self.campaigns: Dict[str, Campaign] = load_campaigns()
        self.scenarios: List[ScenarioDescriptor] = []

        self.sound_player = SoundPlayer(window=self)

        self.save_manager = SaveManager('saved_games', 'scenarios', self)

        self._updated: List[Updateable] = []

        # views:
        self._current_view: Optional[LoadableWindowView] = None
        self.menu_view: Menu = Menu()
        self.game_view: Optional[Game] = None

        # Mouse-related:
        self.mouse = MouseCursor(self, self.resources_manager.get('normal.png'))

        # keyboard-related:
        self.keyboard = KeyboardHandler(self, self.menu_view)

        # store viewport data to avoid redundant get_viewport() calls and call
        # get_viewport only when viewport is actually changed:
        self.current_viewport = 0, SCREEN_WIDTH, 0, SCREEN_HEIGHT

        self.show_view(LoadingScreen(loaded_view=self.menu_view))

    @property
    def game(self) -> Game:
        return self.game_view

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
            self.mouse.updated_spritelists = value
        except AttributeError:
            pass  # MouseCursor is not initialised yet

    def toggle_full_screen(self):
        self.set_fullscreen(not self.fullscreen)
        if not self.fullscreen:
            self.set_size(SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)
            self.center_window()

    @property
    def is_game_running(self) -> bool:
        return self.current_view is self.game_view

    # @timer(level=1, global_profiling_level=PROFILING_LEVEL, forced=False)
    def on_update(self, delta_time: float):
        self.frames += 1
        self.total_delta_time += delta_time
        self.current_fps = round(pyglet.clock.get_fps(), 2)  # round(1 / delta_time, 2)
        self.current_view.on_update(delta_time)
        for controller in (self.mouse, self.keyboard):
            if controller.active:
                controller.update()
        self.sound_player.on_update()
        super().on_update(delta_time)

    def on_draw(self):
        self.clear()
        self.current_view.on_draw()
        if (cursor := self.mouse).visible:
            cursor.draw()
        if self.settings.draw_fps_counter:
            self.draw_current_fps_on_screen()

    def draw_current_fps_on_screen(self):
        draw_text(f'FPS: {self.current_fps}',
                  self.current_view.viewport[0] + 30,
                  self.current_view.viewport[3] - 30,
                  GREEN if self.current_fps > 24 else YELLOW if self.current_fps > 20 else RED)

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        if self.mouse.active:
            if self.current_view is self.game_view:
                left, _, bottom, _ = self.current_view.viewport
                self.mouse.on_mouse_motion(x + left, y + bottom, dx, dy)
            else:
                self.mouse.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if self.mouse.active:
            self.mouse.on_mouse_press(x, y, button, modifiers)

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        if self.mouse.active:
            left, _, bottom, _ = self.current_view.viewport
            self.mouse.on_mouse_release(x + left, y + bottom, button)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.mouse.active:
            if self.is_game_running and self.mouse.pointed_ui_element:
                return
            left, _, bottom, _ = self.current_view.viewport
            self.mouse.on_mouse_motion(x, y, dx, dy)
            self.mouse.on_mouse_drag(x + left, y + bottom, dx, dy, buttons)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.mouse.active:
            self.mouse.on_mouse_scroll(scroll_x, scroll_y)

    def on_key_press(self, symbol: int, modifiers: int):
        if self.keyboard.active:
            self.keyboard.on_key_press(symbol)

    def on_key_release(self, symbol: int, modifiers: int):
        self.keyboard.on_key_release(symbol)

    def show_view(self, new_view: LoadableWindowView):
        if self.current_view is not new_view:
            if new_view.requires_loading:
                super().show_view(LoadingScreen(loaded_view=new_view))
            else:
                super().show_view(new_view)

    def toggle_mouse_and_keyboard(self, value: bool, only_mouse=False):
        try:
            self.mouse.active = value
            self.mouse.visible = value
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
        offset = SCREEN_WIDTH - UI_WIDTH
        new_left = clamp(left - dx, game_map.width - offset, 0)
        new_bottom = clamp(bottom - dy, game_map.height - SCREEN_HEIGHT, 0)
        self._update_viewport_coordinates(new_left, new_bottom)

    def _update_viewport_coordinates(self, new_left, new_bottom):
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
        offset = SCREEN_WIDTH - UI_WIDTH
        new_left = clamp(x - SCREEN_X, game_map.width - offset, 0)
        new_bottom = clamp(y - SCREEN_Y, game_map.height - SCREEN_HEIGHT, 0)
        self._update_viewport_coordinates(new_left, new_bottom)

    def get_viewport(self) -> Viewport:
        """Returns a Tuple of 4 floats: left margin, right margin, bottom margin, top margin of the screen."""
        # We cache viewport coordinates each time they are changed,
        # so there is no need for redundant call to the Window method
        return self.current_view.viewport

    def open_saving_menu(self):
        self.show_view(self.menu_view)
        self.menu_view.switch_to_bundle(SCENARIO_EDITOR_MENU if self.settings.editor_mode else SAVING_MENU)

    def create_new_game(self):
        self.game_view = Game(loader=None)

    def start_new_game(self, editor_mode: bool = False):
        self.settings.editor_mode = editor_mode
        if (selected := self.mouse.selected_ui_element) is not None:
            self.load_saved_game_or_scenario(selected, editor_mode)
        else:
            self.create_new_game()
            self.show_view(self.game_view)

    def load_game(self):
        if self.mouse.selected_ui_element is not None:
            self.start_new_game()

    def continue_game(self):
        self.show_view(self.game_view)

    def open_scenario_editor(self):
        self.start_new_game(editor_mode=True)

    def load_scenario(self):
        if self.mouse.selected_ui_element is not None:
            self.open_scenario_editor()

    def save_game(self, text_input_field: Optional[TextInputField] = None):
        """
        Save current game-state into the shelf file with .sav extension.

        :param text_input_field: TextInputField -- field from which name for a
        new saved-game file should be read. If field is empty, automatic save
        name would be generated
        """
        if (selected := self.is_valid_file_selected()) is not None:
            save_name = selected.name
        elif not (save_name := text_input_field.get_text()):
            now = time.gmtime()
            save_name = f'saved_game_({now.tm_year}_{now.tm_yday}_{now.tm_hour}_{now.tm_min}_{now.tm_sec})'
        self.save_manager.save_game(save_name, self.game_view, scenario=self.settings.editor_mode)
        self.menu_view.refresh_files_list_in_bundle(SAVING_MENU, SAVED_GAMES)

    def load_saved_game_or_scenario(self, selected=None, editor_mode: bool = False):
        if self.is_valid_file_selected() is not None:
            loader = self.save_manager.load_game(filename=selected.name, editor_mode=editor_mode)
            self.game_view = game = Game(loader=loader)
            self.show_view(game)

    @ask_player_for_confirmation(SCREEN_CENTER, MAIN_MENU)
    def quit_current_game(self):
        self.game_view.unload()
        self.show_view(self.menu_view)
        self.settings.editor_mode = False
        self.menu_view.toggle_game_related_buttons()

    @ask_player_for_confirmation(SCREEN_CENTER, LOADING_MENU)
    def delete_saved_game(self):
        if (selected := self.is_valid_file_selected()) is not None:
            self.save_manager.delete_file(selected.name)

    @ask_player_for_confirmation(SCREEN_CENTER, SCENARIO_EDITOR_MENU)
    def delete_scenario(self):
        if (selected := self.is_valid_file_selected()) is not None:
            self.save_manager.delete_file(selected.name)

    def is_valid_file_selected(self):
        if (selected := self.mouse.selected_ui_element) is not None:
            return selected if self.save_manager.check_if_file_exists(selected.name) else None

    def switch_immortality(self, human_player: bool):
        if (game := self.game_view) is not None:
            for player in game.players.values():
                if (human_player and not player.cpu) or (not human_player and player.cpu):
                    player.immortal = not player.immortal

    def change_language(self, new_language: str):
        self.localization_manager.set_language(new_language)
        self.retranslate_ui_elements(self.localization_manager)

    def retranslate_ui_elements(self, localization_manager: LocalizationManager):
        for view in (self.game_view, self.menu_view):
            if view is not None:
                view.retranslate_ui_elements(localization_manager)

    @ask_player_for_confirmation(SCREEN_CENTER, MAIN_MENU)
    def close(self):
        log_here(f'Terminating application... Average FPS: {round(1 / (self.total_delta_time / self.frames), 2)}', console=True)
        self.sound_player.pause()
        super().close()


class Timer:

    def __init__(self):
        self.game_start_time = time.time()
        self.total_game_time = self.frames = self.seconds = self.minutes = self.hours = 0
        self.formatted_time = f'00:00:00'

    def update(self):
        self.total_game_time = seconds = time.time() - self.game_start_time
        gmtime = time.gmtime(seconds)
        self.frames += 1
        self.seconds = s = gmtime.tm_sec
        self.minutes = m = gmtime.tm_min
        self.hours = h = gmtime.tm_hour
        f = format
        self.formatted_time = f"{f(h, '02')}:{f(m, '02')}:{f(s, '02')}"

    def draw(self):
        _, right, bottom, _ = Game.instance.viewport
        x, y = right - 270, bottom + 840
        draw_text(f"Time:{self.formatted_time}", x, y, GREEN, 15)

    def save(self):
        self.total_game_time = time.time() - self.game_start_time
        return self

    def load(self):
        self.game_start_time = time.time() - self.total_game_time


class ScenarioEditor:
    _selected_player: Optional[Player] = None

    @property
    def selected_player(self) -> Player:
        return self._selected_player or Game.instance.local_human_player


class Game(LoadableWindowView, UiBundlesHandler, EventsCreator):
    """This is an actual Game-instance, created when player starts the game."""
    instance: Optional[Game] = None

    def __init__(self, loader: Optional[Generator] = None):
        LoadableWindowView.__init__(self, loader)
        UiBundlesHandler.__init__(self)
        EventsCreator.__init__(self)

        self.assign_reference_to_self_for_all_classes()

        self.timer = Timer()
        self.dialog: Optional[Tuple[str, Color, Color]] = None

        # SpriteLists:
        self.terrain_tiles = SpriteListWithSwitch(is_static=True, update_on=False)
        self.dead_bodies = SpriteListWithSwitch(is_static=True, update_on=False)
        self.vehicles_threads = SpriteList(is_static=True)
        self.units_ordered_destinations = UnitsOrderedDestinations()
        self.units = LayeredSpriteList(update_on=not self.editor_mode)
        self.static_objects = SpriteListWithSwitch(is_static=True, update_on=False)
        self.buildings = LayeredSpriteList(update_on=not self.editor_mode)
        self.explosions_pool: Optional[ExplosionsPool] = ExplosionsPool(game=self)
        self.selection_markers_sprites = SpriteList()
        self.interface: UiSpriteList() = self.create_user_interface()
        self.set_updated_and_drawn_lists()

        self.events_scheduler = EventsScheduler(game=self)

        self.map: Optional[Map] = None
        self.mini_map: Optional[MiniMap] = None
        self.fog_of_war: Optional[FogOfWar] = None

        self.pathfinder: Optional[Pathfinder] = None

        # All GameObjects are initialized by the specialised factory:
        self.spawner: Optional[GameObjectsSpawner] = None

        # Units belongs to the Players, Players belongs to the Factions, which
        # are updated each frame to evaluate AI, enemies-visibility, etc.
        self.factions: Dict[int, Faction] = {}
        self.players: Dict[int, Player] = {}

        self.local_human_player: Optional[Player] = None
        # We only draw those Units and Buildings, which are "known" to the
        # local human Player's Faction or belong to it, the rest of entities
        # is hidden. This set is updated each frame:
        self.local_drawn_units_and_buildings: Set[PlayerEntity] = set()

        self.units_manager = UnitsManager(mouse=self.mouse, keyboard=self.window.keyboard)

        self.current_campaign: Optional[Campaign] = None
        self.current_scenario: Optional[Scenario] = None

        self.scenario_editor: Optional[ScenarioEditor] = ScenarioEditor() if self.editor_mode else None

        # list used only when Game is randomly-generated:
        rows, columns = self.settings.map_height, self.settings.map_width
        self.things_to_load = [
            ['map', Map, 0.35, {'rows': rows, 'columns': columns,
             'grid_width': TILE_WIDTH, 'grid_height': TILE_HEIGHT}],
            ['pathfinder', Pathfinder, 0.05, lambda: self.map],
            ['fog_of_war', FogOfWar, 0.15],
            ['spawner', GameObjectsSpawner, 0.05],
            ['mini_map', MiniMap, 0.15, ((SCREEN_WIDTH, SCREEN_HEIGHT),
                                         (MINIMAP_WIDTH, MINIMAP_HEIGHT),
                                         (TILE_WIDTH, TILE_HEIGHT), rows)],
        ] if self.loader is None else []

        self.random_scenario = self.loader is None

        log_here('Game initialized successfully', console=self.settings.developer_mode)

    @property
    def resources_manager(self) -> ResourcesManager:
        return self.window.resources_manager

    @property
    def sound_player(self) -> SoundPlayer:
        return self.window.sound_player

    @property
    def settings(self) -> Settings:
        return self.window.settings

    @property
    def editor_mode(self) -> bool:
        return self.window.settings.editor_mode

    @property
    def mouse(self) -> MouseCursor:
        return self.window.mouse

    @property
    def keyboard(self) -> KeyboardHandler:
        return self.window.keyboard

    @property
    def configs(self):
        return self.window.configs

    @property
    def current_active_player(self) -> Player:
        return self.scenario_editor.selected_player if self.editor_mode else self.local_human_player

    def assign_reference_to_self_for_all_classes(self):
        game = self.__class__.__name__.lower()
        for _class in (c for c in globals().values() if hasattr(c, game)):
            setattr(_class, game, self)
        Game.instance = self.window.mouse.game = self

    def find_object_by_class_and_id(self,
                                    name_and_id: Union[str, Tuple[str, int]]):
        if isinstance(name_and_id, Tuple):
            obj_name, object_id = name_and_id
            object_class = eval(obj_name)
            if object_class in (CpuPlayer, HumanPlayer):
                return self.players.get(object_id)
            return self.find_gameobject(object_class, object_id)
        else:
            object_class = eval(name_and_id)
            return {Game: self, GameWindow: self.window, Scenario: self.current_scenario,
                    UnitsManager: self.units_manager}[object_class]

    def find_gameobject(self,
                        object_class: Union[type(Unit), type(Building), type(TerrainObject)],
                        object_id: int) -> Optional[GameObject]:
        """
        Find any GameObject existing in game by providing its type and id.

        :param object_class: type -- class of the object, possible are: Unit,
        Building, TerrainObject
        :param object_id: int -- a unique integer identifier of the GameObject
        :return: Optional[GameObject]
        """
        return {
            Soldier: self.units,
            Unit: self.units,
            VehicleWithTurret: self.units,
            Building: self.buildings,
            Sprite: self.terrain_tiles,
            TerrainObject: self.static_objects,
            Wreck: self.static_objects,
        }[object_class].get(object_id)

    def create_user_interface(self) -> UiSpriteList:
        ui_x, ui_y = SCREEN_WIDTH - UI_WIDTH // 2, SCREEN_Y
        ui_size = UI_WIDTH, SCREEN_HEIGHT
        # right_panel = Frame('ui_right_panel.png', ui_x, ui_y, *ui_size, name='right_panel')
        ui_options_section = UiElementsBundle(
            name=UI_OPTIONS_PANEL,
            elements=[
                Frame('ui_right_panel.png', ui_x, ui_y, *ui_size, name='right_panel'),
                Checkbox('menu_checkbox.png', ui_x - 170, ui_y + 370, '', 10,
                         ticked=self.settings.show_minimap, variable=(self.settings, 'show_minimap')),
                Button('ui_buildings_construction_options.png', ui_x - 117, ui_y + 153,
                       functions=partial(self.show_construction_options, UI_BUILDINGS_CONSTRUCTION_PANEL)),
                Button('ui_units_construction_options.png', ui_x, ui_y + 153,
                       functions=partial(self.show_construction_options, UI_UNITS_CONSTRUCTION_PANEL)),
                Button('game_button_menu.png', ui_x + 100, 120,
                        functions=partial(self.window.show_view,
                                          self.window.menu_view)),
                Button('game_button_save.png', ui_x, 120,
                        functions=self.window.open_saving_menu),
                Button('game_button_pause.png', ui_x - 100, 120,
                        functions=partial(self.toggle_pause)),
            ],
            register_to=self
        )
        if self.editor_mode:
            ui_options_section.append(
                Button('ui_terrain_editing_options.png', ui_x + 117, ui_y + 153,
                       functions=partial(self.show_construction_options, UI_TERRAIN_EDITING_PANEL))
            )
            ui_terrain_editing_panel = UiElementsBundle(
                name=UI_TERRAIN_EDITING_PANEL,
                elements=[],
                register_to=self
            )

        y = SCREEN_HEIGHT * 0.79075
        x = SCREEN_WIDTH - UI_WIDTH + 90
        resources = (r for r in Player.resources)
        ui_resources_section = UiElementsBundle(
            name=UI_RESOURCES_SECTION,
            elements=[
                UiTextLabel(x, y, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x + 165, y, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x, y - 40, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x + 165, y - 40, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x, y - 80, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x + 165, y - 80, '0', 17, WHITE, next(resources), align_x='left'),
                UiTextLabel(x + 100, y - 120, '0', 17, WHITE, next(resources), align_x='left')
            ],
            register_to=self
        )
        ui_units_panel = UiElementsBundle(
            name=UI_UNITS_PANEL,
            elements=[],
            register_to=self
        )
        ui_buildings_panel = UiElementsBundle(
            name=UI_BUILDINGS_PANEL,
            elements=[],
            register_to=self
        )
        ui_units_construction_panel = UiElementsBundle(
            name=UI_UNITS_CONSTRUCTION_PANEL,
            elements=[],
            register_to=self
        )
        ui_buildingss_construction_panel = UiElementsBundle(
            name=UI_BUILDINGS_CONSTRUCTION_PANEL,
            elements=[],
            register_to=self
        )
        return self.ui_elements_spritelist  # UiBundlesHandler attribute

    def update_interface_position(self, right, top):
        diff_x = right - self.interface[0].right
        diff_y = top - self.interface[0].top
        self.interface.move(diff_x, diff_y)
        self.update_not_displayed_bundles_positions(diff_x, diff_y)
        self.mini_map.update_position(diff_x, diff_y)

    def change_interface_content(self, context_gameobjects=None):
        """
        Change elements displayed in interface to proper for currently selected
        gameobjects giving player access to context-options.
        """
        self._unload_all(exceptions=(UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, EDITOR))
        if context_gameobjects is not None:
            if isinstance(context_gameobjects, Building):
                self.configure_building_interface(context_gameobjects)
            else:
                self.configure_units_interface(context_gameobjects)

    @ignore_in_editor_mode
    def configure_building_interface(self, context_building: Building):
        self.load_bundle(name=UI_BUILDINGS_PANEL, clear=True)
        ui_elements = context_building.create_ui_elements(*self.ui_position)
        self.get_bundle(UI_BUILDINGS_PANEL).extend(ui_elements)

    @property
    def ui_position(self) -> Tuple[int, int]:
        _, right, bottom, _ = self.viewport
        return right - UI_WIDTH // 2, bottom + SCREEN_Y

    @ignore_in_editor_mode
    def configure_units_interface(self, context_units: tuple[Unit]):
        self.create_selected_units_panel(context_units)
        self.load_bundle(UI_UNITS_PANEL)

    def create_selected_units_panel(self, context_units: tuple[Unit]):
        """
        Create UI elements for selected units. Top element is a list of units icons, if there are many. Each icon is
        a little button allowing player to select it.
        If there is only one unit selected, instead of a list of buttons, it is its name and health and fuel bars.
        Then thera are custom buttons for each action the unit can perform.
        """
        selected_units_bundle = self.get_bundle(UI_UNITS_PANEL)
        selected_units_bundle.clear()
        x, y = self.ui_position
        self.create_selected_units_panel_labels(selected_units_bundle, x, y)
        if len(context_units) == 1:
            selected_units_bundle.extend(context_units[0].create_ui_information_about_unit(x, y))
        elif len(self.units_manager.selected_units_types) == 1:
            self.create_ui_selection_buttons_for_units_of_the_same_type(context_units, selected_units_bundle, x, y)
        else:
            self.create_ui_selection_buttons_for_many_units_types(selected_units_bundle, x, y)
        self.create_ui_universal_units_buttons(selected_units_bundle, x, y)
        # TODO: 4. get specific UiElements for each unit type, and add them to the bundle only once for each unit type

    def create_selected_units_panel_labels(self, selected_units_bundle, x, y):
        localize = self.window.localization_manager.get
        selected_units_bundle.extend(
            [UiTextLabel(x, y + 60, localize('SELECTED_UNITS'), 13, WHITE, active=False),
             UiTextLabel(x, y - 130, localize('AVAILABLE_ACTIONS'), 13, WHITE, active=False)]
        )

    def create_ui_selection_buttons_for_units_of_the_same_type(self, context_units, selected_units_bundle, x, y):
        icon_scale = 0.75
        positions = generate_2d_grid(x - 135, y + 20, 3, 6, 75 * icon_scale, 75 * icon_scale)
        for (col, row), unit in zip(positions, context_units):
            unit_button = ProgressButton(f'{unit.object_name}_icon.png', col, row, str(unit.id),
                                                         functions=partial(self.units_manager.select_units, unit),
                                                         scale=icon_scale, health_bar=True)
            unit_button.progress = unit.health_ratio * 100
            selected_units_bundle.append(unit_button)

    def create_ui_selection_buttons_for_many_units_types(self, selected_units_bundle, x, y):
        positions = generate_2d_grid(x - 135, y + 10, 2, 6, 75, 75)
        for (col, row), (unit_type, units_count) in zip(positions, self.units_manager.selected_units_types.items()):
            if units_count:
                selected_units_bundle.append(
                    ProgressButton(
                        f'{unit_type}_icon.png', col, row, unit_type,
                        functions=partial(self.units_manager.select_units_of_type, unit_type),
                        counter=units_count
                    )
                )

    def create_ui_universal_units_buttons(self, selected_units_bundle: UiElementsBundle, x, y):
        selected_units_bundle.extend([
            Button('game_button_stop.png', x - 125, y - 175, functions=self.units_manager.stop_all_units,
                   hint=Hint('button_hint_stop.png', delay=self.settings.hints_delay_seconds)),
            Button('game_button_waypoints.png', x - 50, y - 175, functions=self.units_manager.toggle_waypoint_mode,
                   hint=Hint('button_hint_waypoints.png', delay=self.settings.hints_delay_seconds)),
        ])

    def update_unit_icon_health(self, unit: Unit):
        selected_units_bundle = self.get_bundle(UI_UNITS_PANEL)
        try:
            progress_button = selected_units_bundle.find_by_name(str(unit.id))
            progress_button.progress = unit.health_ratio * 100
        except AttributeError:
            pass

    def show_construction_options(self, construction_bundle_name: str):
        self._unload_all(exceptions=(UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, EDITOR))

        construction_bundle = self.get_bundle(construction_bundle_name)
        construction_bundle.clear()

        x, y = self.ui_position
        positions = generate_2d_grid(x - 135, y + 20, 6, 4, 75, 75)

        if construction_bundle_name is UI_UNITS_CONSTRUCTION_PANEL:
            self.populate_construction_options_with_available_units(construction_bundle, positions)
        elif construction_bundle_name is UI_BUILDINGS_CONSTRUCTION_PANEL:
            self.populate_construction_options_with_available_buildings(construction_bundle, positions)
        else:
            self.populate_construction_options_with_terrain_features(construction_bundle, positions)

        self.load_bundle(construction_bundle_name)

    def populate_construction_options_with_available_buildings(self, construction_bundle, positions):
        for i, building_name in enumerate(set(self.local_human_player.buildings_possible_to_build)):
            column, row = positions[i]
            button = Button(f'{building_name}_icon.png', column, row, building_name,
                            active=self.local_human_player.enough_resources_for(building_name),
                            functions=partial(self.mouse.attach_placeable_gameobject, building_name))
            construction_bundle.append(button)

    def populate_construction_options_with_available_units(self, units_construction_bundle, positions):
        if self.editor_mode:
            self.populate_with_all_possible_units(positions, units_construction_bundle)
        else:
            self.populate_with_units_available_in_game(positions, units_construction_bundle)

    def populate_with_all_possible_units(self, positions, units_construction_bundle):
        for (col, row), unit_name in zip(positions, set(self.local_human_player.units_possible_to_build)):
            button = ProgressButton(f'{unit_name}_icon.png', col, row, unit_name,
                                    functions=partial(self.mouse.attach_placeable_gameobject, unit_name))
            units_construction_bundle.append(button)

    def populate_with_units_available_in_game(self, positions, units_construction_bundle):
        delay = self.settings.hints_delay_seconds
        for (col, row), unit_name in zip(positions, set(self.local_human_player.units_possible_to_build)):
            producer = self.local_human_player.get_default_producer_of_unit(unit_name)
            hint = UnitProductionCostsHint(self.local_human_player, producer.produced_units[unit_name], delay=delay)
            button = ProgressButton(f'{unit_name}_icon.png', col, row, unit_name,
                                    functions=partial(producer.start_production, unit_name), hint=hint)
            button.bind_function(partial(producer.cancel_production, unit_name), MOUSE_BUTTON_RIGHT)
            units_construction_bundle.append(button)

    def populate_construction_options_with_terrain_features(self, terrain_features_bundle, positions):
        # TODO: implement terrain tiles as PlaceAble objects to place on the map in editor mode
        ...

    def create_effect(self, effect_type: Any, name: str, x, y):
        """
        Add animated sprite to the 'self.effects' spritelist to display e.g.:
        explosions.
        """
        if effect_type is Explosion:
            self.create_explosion(x, y, name)

    def create_explosion(self, x, y, name: str):
        if self.explosions_pool is None:
            self.explosions_pool = ExplosionsPool(self)
        self.explosions_pool.create_explosion('explosion.png', x, y)

    def on_show_view(self):
        super().on_show_view()
        self.load_timer(self.timer)
        self.window.toggle_mouse_and_keyboard(True)
        self.window.sound_player.play_playlist('game')
        self.change_interface_content()

    def create_random_scenario(self):
        self.test_factions_and_players_creation()
        self.test_buildings_spawning()
        self.test_units_spawning()
        self.test_scenarios()

    def place_viewport_at_players_base_or_starting_position(self):
        if self.local_human_player.buildings:
            position = average_position_of_points_group(
                [u.position for u in self.local_human_player.buildings]
            )
        else:
            position = average_position_of_points_group(
                [u.position for u in self.local_human_player.units]
            )
        self.window.move_viewport_to_the_position(*position)

    def test_factions_and_players_creation(self):
        # TODO: remove it when game is completed
        self.local_human_player = player = HumanPlayer(id=2, color=GREEN, faction=Faction(name='Solarian Republic'))
        cpu_player = CpuPlayer(color=RED, faction=Faction(name='Interplanetary Industrial Conglomerate'))
        player.start_war_with(cpu_player)

    def test_buildings_spawning(self):
        # TODO: remove it when game is completed
        self.spawn('medium_vehicles_factory', self.players[2], (400, 600), garrison=1)
        self.spawn('garrison', self.players[2], (600, 800), garrison=1)
        self.spawn('command_center', self.players[2], (400, 900), garrison=1)
        self.spawn('medium_vehicles_factory', self.players[4], (1400, 1000), garrison=1)
        ConstructionSite('command_center', self.players[2], (850, 800))

    def spawn(self,
              object_name: str,
              player: Optional[Union[Player, int]] = None,
              position: Optional[Point] = None,
              *args,
              **kwargs) -> Optional[GameObject]:
        player = self.players.get(player, player)
        return self.spawner.spawn(object_name, player, self.map.get_valid_position(position), *args, **kwargs)

    def spawn_group(self,
                    names: List[str],
                    player: Union[Player, int],
                    position: Optional[Point] = None,
                    *args,
                    **kwargs) -> List[Unit]:
        player = self.players.get(player, player)
        positions = self.pathfinder.get_group_of_waypoints(*self.map.get_valid_position(position), len(names))
        return [
            self.spawner.spawn(name, player, map_grid_to_position(position), *args, **kwargs)
            for name, position in zip(names, positions)
        ]

    def test_units_spawning(self):
        # TODO: remove it when game is completed
        units_names = ('tank_medium', 'apc', 'truck')
        walkable = list(self.map.all_walkable_nodes)
        for unit_name in units_names:
            for player in (self.players.values()):
                node = random.choice(walkable)
                walkable.remove(node)
                names = [unit_name] * (PLAYER_UNITS_COUNT if player.is_human_player else CPU_UNITS_COUNT)
                self.spawn_group(names, player, node.position)

    def test_scenarios(self):
        # TODO: remove it when game is completed
        human = self.local_human_player
        cpu_player = self.players[4]
        events = (
            NoUnitsLeftTrigger(human).triggers(Defeat(human)),
            NoUnitsLeftTrigger(cpu_player).triggers(Victory(human)),
            TimePassedTrigger(human, 30).triggers(Victory(human)),
            MapRevealedTrigger(human).triggers(Victory(human)),
        )
        self.current_scenario = Scenario('Test Mission', 'Map 1')\
            .add_players(human, cpu_player)\
            .add_events_triggers(*events)\
            .unlock_technologies_for_player(human, 'technology_1')\
            .unlock_buildings_for_player(human, 'command_center')

    def on_being_attached(self, attached: Observed):
        if isinstance(attached, GameObject):
            self.attach_gameobject(attached)
        elif isinstance(attached, (Player, Faction)):
            self.attach_player_or_faction(attached)
        elif isinstance(attached, (UiElementsBundle, UiElement)):
            super().on_being_attached(attached)
        else:
            log_here(f'Tried to attach {attached} which Game is unable to attach.')

    def notify(self, attribute: str, value: Any):
        pass

    def on_being_detached(self, detached: Observed):
        if isinstance(detached, GameObject):
            self.detach_gameobject(detached)
        elif isinstance(detached, (Player, Faction)):
            self.detach_player_or_faction(detached)
        elif isinstance(detached, (UiElementsBundle, UiElement)):
            self.remove(detached)
        else:
            log_here(f'Tried to detach {detached} which Game is unable to detach.')

    def attach_gameobject(self, gameobject: GameObject):
        if isinstance(gameobject, PlayerEntity):
            self.attach_player_entity(gameobject)
        elif isinstance(gameobject, Corpse):
            self.dead_bodies.append(gameobject)
        else:
            self.static_objects.append(gameobject)

    def attach_player_entity(self, gameobject: PlayerEntity):
        if gameobject.is_building:
            self.buildings.append(gameobject)
        else:
            self.units.append(gameobject)

    def attach_player_or_faction(self, attached: Union[Player, Faction]):
        if isinstance(attached, Player):
            self.players[attached.id] = attached
        else:
            self.factions[attached.id] = attached

    def detach_gameobject(self, gameobject: GameObject):
        if isinstance(gameobject, PlayerEntity):
            self.detach_player_entity(gameobject)
        elif isinstance(gameobject, Corpse):
            self.dead_bodies.remove(gameobject)
        else:
            self.static_objects.remove(gameobject)

    def detach_player_entity(self, gameobject: PlayerEntity):
        if gameobject.is_building:
            self.buildings.remove(gameobject)
        else:
            self.units.remove(gameobject)

    def detach_player_or_faction(self, detached: Union[Player, Faction]):
        if isinstance(detached, Player):
            del self.players[detached.id]
        else:
            del self.factions[detached.id]

    def get_notified(self, *args, **kwargs):
        pass

    def update_view(self, delta_time):
        if not self.editor_mode and self.timer is not None:
            self.timer.update()
        for thing in (self.events_scheduler, self.fog_of_war, self.pathfinder, self.mini_map, self.current_scenario):
            if thing is not None:
                thing.update()
        super().update_view(delta_time)
        self.update_local_drawn_units_and_buildings()
        self.update_factions_and_players(delta_time)

    def after_loading(self):
        self.window.menu_view.update_ui_elements_from_variables()
        self.window.show_view(self)
        # we put FoW before the interface to list of rendered layers to
        # assure that FoW will not cover player interface:
        self.drawn.insert(BEFORE_INTERFACE_LAYER, self.fog_of_war)
        super().after_loading()
        if self.random_scenario:
            self.create_random_scenario()
        self.place_viewport_at_players_base_or_starting_position()
        self.update_interface_position(self.viewport[1], self.viewport[3])

    def save_timer(self) -> Timer:
        """Before saving timer, recalculate total time game was played."""
        self.timer.total_game_time = time.time() - self.timer.game_start_time
        return self.timer

    @log_this_call()
    def load_timer(self, loaded_timer: Timer):
        """
        Subtract total time played from loading time to correctly reset timer
        after loading game and continue time-counting from where it was stopped
        last time.
        """
        self.timer = loaded_timer
        self.timer.game_start_time = time.time() - self.timer.total_game_time

    def update_local_drawn_units_and_buildings(self):
        """
        We draw on the screen only these PlayerEntities, which belongs to the
        local Player's Faction, or are detected by his Faction.
        """
        self.local_drawn_units_and_buildings.clear()
        if (local_faction := self.local_human_player.faction) is not None:
            self.local_drawn_units_and_buildings.update(
                local_faction.units,
                local_faction.buildings,
                local_faction.known_enemies
            )

    def update_factions_and_players(self, delta_time):
        for faction in self.factions.values():
            faction.update(delta_time)

    @timer(level=1, global_profiling_level=PROFILING_LEVEL)
    def on_draw(self):
        super().on_draw()
        if self.mini_map is not None and self.settings.show_minimap:
            self.mini_map.draw()
        self.timer.draw()
        if self.dialog is not None:
            self.draw_dialog(*self.dialog)

        # for unit in self.units:
        #     draw_text(f'{unit.current_node}, {unit.forced_destination}', unit.right, unit.bottom, RED)
        #     if unit.path:
        #         draw_text(f'{unit.path[-1]}',unit.right, unit.top, WHITE)

    def draw_dialog(self, text: str, txt_color: Color = WHITE, color: Color = BLACK):
        x, y = self.window.screen_center
        draw_rectangle_filled(x, y, SCREEN_WIDTH, 200, rgb_to_rgba(color, 150))
        draw_text(text, x, y, txt_color, 30, anchor_x='center', anchor_y='center')

    def toggle_pause(self, dialog: str = 'GAME PAUSED', color: Color = BLACK):
        super().toggle_pause()
        self.reset_dialog(*(dialog, color) if self.paused else (None, None))
        self.save_timer() if self.paused else self.load_timer(self.timer)
        self.window.toggle_mouse_and_keyboard(not self.paused, only_mouse=True)

    def reset_dialog(self, text: str = None,
                     color: Color = BLACK,
                     txt_color: Color = WHITE):
        if text is None:
            self.dialog = None
        else:
            self.dialog = (text, txt_color, color)

    def unload(self):
        self.updated.clear()
        self.local_human_player = None
        self.scenario_editor = None
        self.units_manager.unselect_all_selected()
        self.local_drawn_units_and_buildings.clear()
        self.factions.clear()
        self.players.clear()
        self.window.game_view = None


def run_profiled_game(settings: Settings):
    import pyprofiler
    with pyprofiler.start_profile() as profiler:
        GameWindow(settings)
        run()
    pyprofiler.end_profile(profiler, 35, True)


def run_game(settings: Settings):
    GameWindow(settings)
    run()


if __name__ == '__main__':
    # these imports are placed here to avoid circular-imports issue:
    # imports-optimization can delete SelectedEntityMarker, PermanentUnitsGroup imports:
    from map.map import Map, Pathfinder, map_grid_to_position
    from units.unit_management import (
        UnitsManager, SelectedEntityMarker, PermanentUnitsGroup
    )
    from effects.explosions import Explosion, ExplosionsPool
    from players_and_factions.player import (
        Faction, Player, CpuPlayer, PlayerEntity, HumanPlayer
    )
    from controllers.keyboard import KeyboardHandler
    from controllers.mouse import MouseCursor
    from units.units import Unit, UnitsOrderedDestinations, Engineer, Soldier, VehicleWithTurret
    from gameobjects.gameobject import GameObject, TerrainObject, Wreck, Corpse
    from gameobjects.spawning import GameObjectsSpawner
    from map.fog_of_war import FogOfWar
    from buildings.buildings import Building, ConstructionSite
    from campaigns.scenarios import Scenario, Campaign, load_campaigns, ScenarioDescriptor
    from campaigns.events import Victory, Defeat
    from campaigns.triggers import NoUnitsLeftTrigger, TimePassedTrigger, MapRevealedTrigger
    from user_interface.menu import Menu
    from user_interface.minimap import MiniMap
    from persistency.save_handling import SaveManager

    game_settings = Settings()

    if __status__ == 'development' and game_settings.pyprofiler:
        run_profiled_game(game_settings)
    else:
        run_game(game_settings)
