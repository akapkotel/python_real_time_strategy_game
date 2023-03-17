#!/usr/bin/env python3
from __future__ import annotations

__title__ = 'Python Real Time Strategy Game'
__author__ = 'Rafał "Akapkotel" Trąbski'
__license__ = "Share Alike Attribution-NonCommercial-ShareAlike 4.0"
__version__ = "0.0.4"
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
from dataclasses import dataclass

from typing import (Any, Dict, Tuple, List, Optional, Set, Union, Generator)
from functools import partial


from arcade import (
    SpriteList, Window, draw_rectangle_filled, draw_text, run, Sprite, get_screens, MOUSE_BUTTON_RIGHT
)
from arcade.arcade_types import Color, Point

from effects.sound import AudioPlayer
from map.constants import TILE_WIDTH, TILE_HEIGHT
from persistency.configs_handling import read_csv_files
from user_interface.scenario_editor import ScenarioEditor
from user_interface.constants import (
    EDITOR, MAIN_MENU, SAVING_MENU, LOADING_MENU, UI_RESOURCES_SECTION, UI_UNITS_PANEL, UI_BUILDINGS_PANEL,
    UI_UNITS_CONSTRUCTION_PANEL, UI_BUILDINGS_CONSTRUCTION_PANEL, UI_OPTIONS_PANEL, MINIMAP_WIDTH, MINIMAP_HEIGHT,
    SCENARIOS, SAVED_GAMES,
)
from user_interface.user_interface import (
    Frame, Button, UiBundlesHandler, UiElementsBundle, GenericTextButton,
    SelectableGroup, TextInputField, UiTextLabel,
    UiElement, ProgressButton, Hint
)
from utils.observer import Observed
from utils.colors import BLACK, GREEN, RED, WHITE, rgb_to_rgba
from utils.data_types import Viewport
from utils.functions import get_path_to_file, ignore_in_editor_mode
from utils.game_logging import log, logger
from utils.timing import timer
from utils.geometry import clamp, average_position_of_points_group, generate_2d_grid
from utils.improved_spritelists import (
    LayeredSpriteList, SpriteListWithSwitch, UiSpriteList,
)
from utils.scheduling import EventsCreator, EventsScheduler, ScheduledEvent
from utils.views import LoadingScreen, LoadableWindowView, Updateable

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!

SEPARATOR = '-' * 20

BEFORE_INTERFACE_LAYER = -2

GAME_PATH = pathlib.Path(__file__).parent.absolute()

SCREEN = get_screens()[0]
SCREEN_WIDTH, SCREEN_HEIGHT = SCREEN.width, SCREEN.height
SCREEN_CENTER = (SCREEN_X, SCREEN_Y) = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2

UI_WIDTH = SCREEN_WIDTH // 5

PLAYER_UNITS = 5
CPU_UNITS = 5

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
        self.developer_mode: bool = True
        self.editor_mode: bool = False

        self.fps: int = 30
        self.game_speed: float = 1.0
        self.update_rate = 1 / (self.fps * self.game_speed)

        self.full_screen: bool = False
        self.pyprofiler: bool = False

        self.god_mode: bool = False
        self.ai_sleep: bool = False

        self.vehicles_threads: bool = True
        self.threads_fadeout_seconds: int = 2

        self.shot_blasts: bool = True
        self.remove_wrecks_after_seconds: int = 30
        self.damage_randomness_factor = 0.25
        self.percent_chance_for_spawning_tree: float = 0.05

        self.resources_abundance: float = 0.01
        self.starting_resources: float = 0.5

        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        self.map_width: int = 100
        self.map_height: int = 100
        self.tile_width: int = TILE_WIDTH
        self.tile_height: int = TILE_HEIGHT

        self.hints_delay_seconds: int = 1

        with open('settings.txt', 'r') as file:
            for line in file.readlines():
                attribute, value = line.split(' = ')
                if 'self' in value or '(' in value or ')' in value:
                    continue
                else:
                    self.__setattr__(attribute, eval(value))


class GameWindow(Window, EventsCreator):
    """
    This class represents the whole window-application which allows player to
    manage his saved games, start new games, change settings etc.
    """

    def __init__(self, settings: Settings):
        Window.__init__(self, settings.screen_width, settings.screen_height, update_rate=settings.update_rate)
        EventsCreator.__init__(self)

        self.total_delta_time = 0
        self.frames = 0
        self.current_fps = 0

        self.set_caption(__title__)
        self.set_fullscreen(settings.full_screen)

        self.settings = Settings()  # shared with Game

        self.campaigns: Dict[str, Campaign] = load_campaigns()
        self.missions: List[MissionDescriptor] = []

        self.sound_player = AudioPlayer()

        self.save_manager = SaveManager('saved_games', 'scenarios', self)

        self._updated: List[Updateable] = []

        # Settings, gameobjects configs, game-progress data, etc.
        self.configs = read_csv_files('resources/configs')

        # views:
        self._current_view: Optional[LoadableWindowView] = None
        self.menu_view: Menu = Menu()
        self.game_view: Optional[Game] = None

        # cursor-related:
        self.cursor = MouseCursor(self, get_path_to_file('normal.png'))
        # store viewport data to avoid redundant get_viewport() calls and call
        # get_viewport only when viewport is actually changed:
        self.current_viewport = 0, SCREEN_WIDTH, 0, SCREEN_HEIGHT

        # keyboard-related:
        self.keyboard = KeyboardHandler(self, self.menu_view)

        self.show_view(LoadingScreen(loaded_view=self.menu_view))

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

    def toggle_full_screen(self):
        self.set_fullscreen(not self.fullscreen)
        if not self.fullscreen:
            self.set_size(SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)
            self.center_window()

    @property
    def is_game_running(self) -> bool:
        return self.current_view is self.game_view

    def start_new_game(self):
        scenarios = self.menu_view.selectable_groups[SCENARIOS]
        if scenarios.currently_selected is not None:
            self.load_saved_game_or_scenario(scenarios=scenarios)
        if self.game_view is None:
            self.game_view = Game(loader=None)
        self.show_view(self.game_view)

    def open_scenario_editor(self):
        self.settings.editor_mode = True
        # TODO: starting new Game in editor mode
        # self.scenario_editor = ScenarioEditor(SCREEN_WIDTH * 0.9, SCREEN_Y)

    # @timer(level=1, global_profiling_level=PROFILING_LEVEL, forced=False)
    def on_update(self, delta_time: float):
        self.frames += 1
        self.total_delta_time += delta_time
        log(f'Time: {delta_time}{SEPARATOR}', console=False)

        self.current_fps = round(1 / delta_time, 2)

        self.current_view.on_update(delta_time)

        for controller in (self.cursor, self.keyboard):
            if controller.active:
                controller.update()

        self.sound_player.on_update()

        super().on_update(delta_time)

    def on_draw(self):
        self.clear()
        self.current_view.on_draw()
        if (cursor := self.cursor).visible:
            cursor.draw()
        self.draw_current_fps_on_screen()

    def draw_current_fps_on_screen(self):
        draw_text(f'FPS: {str(self.current_fps)}',
                  self.current_view.viewport[0] + 30,
                  self.current_view.viewport[3] - 30,
                  WHITE
        )

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
            self.cursor.on_mouse_release(x + left, y + bottom, button)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.cursor.active:
            if self.current_view is self.game_view and self.cursor.pointed_ui_element:
                return
            left, _, bottom, _ = self.current_view.viewport
            self.cursor.on_mouse_motion(x, y, dx, dy)
            self.cursor.on_mouse_drag(x + left, y + bottom, dx, dy, buttons, modifiers)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.cursor.active:
            self.cursor.on_mouse_scroll(x, y, scroll_x, scroll_y)

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
        # We cache viewport coordinates each time they are changed,
        # so there is no need for redundant call to the Window method
        return self.current_view.viewport

    def update_scenarios_list(self, menu: str):
        campaign_menu = self.menu_view.get_bundle(menu)
        self.menu_view.selectable_groups[SCENARIOS] = group = SelectableGroup()
        campaign_menu.remove_subgroup(5)

        x, y = SCREEN_X * 0.35, (i for i in range(300, SCREEN_HEIGHT, 60))
        campaign_menu.extend(  # refresh saved-games list
            GenericTextButton('blank_file_button.png', x, next(y), file,
                              None, subgroup=5, selectable_group=group)
            for file in self.save_manager.scenarios
        )

    def update_saved_games_list(self, menu: str):
        loading_menu = self.menu_view.get_bundle(menu)
        loading_menu.remove_subgroup(4)
        x, y = SCREEN_X // 2, (i for i in range(300, SCREEN_HEIGHT, 60))
        self.menu_view.selectable_groups[SAVED_GAMES] = group = SelectableGroup()
        loading_menu.extend(
            GenericTextButton('blank_file_button.png', x, next(y), file,
                              None, subgroup=4, selectable_group=group)
            for file in self.save_manager.saved_games
        )

    def open_saving_menu(self):
        self.show_view(self.menu_view)
        self.menu_view.switch_to_bundle(name=SAVING_MENU)

    def save_game(self, text_input_field: Optional[TextInputField] = None):
        """
        Save current game-state into the shelve file with .sav extension.

        :param text_input_field: TextInputField -- field from which name for a
        new saved-game file should be read. If field is empty, automatic save
        name would be generated
        """
        saves = self.menu_view.selectable_groups[SAVED_GAMES]
        if (selected_save := saves.currently_selected) is not None:
            save_name = selected_save.name
        elif not (save_name := text_input_field.get_text()):
            save_name = f'saved_game({time.asctime()})'
        self.save_manager.save_game(save_name, self.game_view, scenario=self.settings.editor_mode)

    def load_saved_game_or_scenario(self, scenarios=None):
        if self.game_view is not None:
            self.quit_current_game(self)
        files = scenarios or self.menu_view.selectable_groups[SAVED_GAMES]
        if (selected_save := files.currently_selected) is not None:
            loader = self.save_manager.load_game(file_name=selected_save.name)
            self.game_view = game = Game(loader=loader)
            self.show_view(game)

    @ask_player_for_confirmation(SCREEN_CENTER, MAIN_MENU)
    def quit_current_game(self):
        self.game_view.unload()
        self.show_view(self.menu_view)
        self.menu_view.toggle_game_related_buttons()

    @ask_player_for_confirmation(SCREEN_CENTER, LOADING_MENU)
    def delete_saved_game(self):
        saves = self.menu_view.selectable_groups[SAVED_GAMES]
        if (selected := saves.currently_selected) is not None:
            self.save_manager.delete_file(selected.name, False)

    @ask_player_for_confirmation(SCREEN_CENTER, MAIN_MENU)
    def close(self):
        print(f'Average FPS: {round(1 / (self.total_delta_time / self.frames), 2)}')
        log('Terminating application...', console=True)
        super().close()


class Timer:

    def __init__(self):
        self.start = time.time()
        self.total = self.frames = self.seconds = self.minutes = self.hours = 0
        self.formatted = None

    def update(self):
        self.total = seconds = time.time() - self.start
        gmtime = time.gmtime(seconds)
        self.frames += 1
        self.seconds = s = gmtime.tm_sec
        self.minutes = m = gmtime.tm_min
        self.hours = h = gmtime.tm_hour
        f = format
        self.formatted = f"{f(h, '02')}:{f(m, '02')}:{f(s, '02')}"

    def draw(self):
        _, right, bottom, _ = Game.instance.viewport
        x, y = right - 270, bottom + 840
        draw_text(f"Time:{self.formatted}", x, y, GREEN, 15)

    def save(self):
        self.total = time.time() - self.start
        return self

    def load(self):
        self.start = time.time() - self.total


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
        self.vehicles_threads = SpriteList(is_static=True)
        self.units_ordered_destinations = UnitsOrderedDestinations()
        self.units = LayeredSpriteList()
        self.static_objects = SpriteListWithSwitch(is_static=True, update_on=False)
        self.buildings = LayeredSpriteList(is_static=True, use_spatial_hash=True)
        self.effects = SpriteList(is_static=True)
        self.selection_markers_sprites = SpriteList()
        self.interface: UiSpriteList() = self.create_user_interface()
        self.set_updated_and_drawn_lists()

        self.events_scheduler = EventsScheduler(game=self)

        self.map: Optional[Map] = None

        self.pathfinder: Optional[Pathfinder] = None

        self.fog_of_war: Optional[FogOfWar] = None

        self.scenario_editor = None

        # All GameObjects are initialized by the specialised factory:
        self.spawner: Optional[GameObjectsSpawner] = None

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

        self.units_manager = UnitsManager(cursor=self.cursor)

        self.current_mission: Optional[Mission] = None

        self.debugger: Optional[GameDebugger] = None

        # list used only when Game is randomly-generated:
        rows, columns = self.settings.map_height, self.settings.map_width
        self.things_to_load = [
            ['map', Map, 0.35, {'rows': rows, 'columns': columns,
             'grid_width': TILE_WIDTH, 'grid_height': TILE_HEIGHT}],
            ['pathfinder', Pathfinder, 0.05, lambda: self.map],
            ['fog_of_war', FogOfWar, 0.15],
            ['spawner', GameObjectsSpawner, 0.05],
            ['explosions_pool', ExplosionsPool, 0.10],
            ['mini_map', MiniMap, 0.15, ((SCREEN_WIDTH, SCREEN_HEIGHT),
                                         (MINIMAP_WIDTH, MINIMAP_HEIGHT),
                                         (TILE_WIDTH, TILE_HEIGHT), rows)],
        ] if self.loader is None else []

        log('Game initialized successfully', console=True)

    @property
    def things_to_update_each_frame(self):
        return (self.events_scheduler, self.debugger, self.fog_of_war, self.pathfinder, self.mini_map, self.timer,
                self.current_mission)

    @property
    def sound_player(self) -> AudioPlayer:
        return self.window.sound_player

    @property
    def settings(self) -> Settings:
        return self.window.settings

    @property
    def cursor(self) -> MouseCursor:
        return self.window.cursor

    @property
    def configs(self):
        return self.window.configs

    def assign_reference_to_self_for_all_classes(self):
        game = self.__class__.__name__.lower()
        for _class in (c for c in globals().values() if hasattr(c, game)):
            setattr(_class, game, self)
        Game.instance = self.window.cursor.game = self

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
            return {Game: self, GameWindow: self.window, Mission: self.current_mission,
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
        }[object_class].get_by_id(object_id)

    def create_user_interface(self) -> UiSpriteList:
        ui_x, ui_y = SCREEN_WIDTH - UI_WIDTH // 2, SCREEN_Y
        ui_size = UI_WIDTH, SCREEN_HEIGHT
        right_panel = Frame('ui_right_panel.png', ui_x, ui_y, *ui_size)
        ui_options_section = UiElementsBundle(
            name=UI_OPTIONS_PANEL,
            elements=[
                right_panel,
                Button('ui_buildings_construction_options.png', ui_x - 89, ui_y + 153,
                       functions=self.show_buildings_construction_options),
                Button('ui_units_construction_options.png', ui_x + 90, ui_y + 153,
                       functions=self.show_units_construction_options),
                Button('game_button_menu.png', ui_x + 100, 120,
                        functions=partial(self.window.show_view,
                                          self.window.menu_view),
                        parent=right_panel),
                 Button('game_button_save.png', ui_x, 120,
                        functions=self.window.open_saving_menu,
                        parent=right_panel),
                 Button('game_button_pause.png', ui_x - 100, 120,
                        functions=partial(self.toggle_pause),
                        parent=right_panel),
            ],
            register_to=self
        )
        y = SCREEN_HEIGHT * 0.79075
        x = SCREEN_WIDTH - UI_WIDTH + 90
        resources = (r for r in Player.resources)
        ui_resources_section = UiElementsBundle(
            name=UI_RESOURCES_SECTION,
            elements=[
                UiTextLabel(x, y, '0', 17, WHITE, next(resources)),
                UiTextLabel(x + 165, y, '0', 17, WHITE, next(resources)),
                UiTextLabel(x, y - 40, '0', 17, WHITE, next(resources)),
                UiTextLabel(x + 165, y - 40, '0', 17, WHITE, next(resources)),
                UiTextLabel(x, y - 80, '0', 17, WHITE, next(resources)),
                UiTextLabel(x + 165, y - 80, '0', 17, WHITE, next(resources)),
                UiTextLabel(x + 100, y - 120, '0', 17, WHITE, next(resources))
            ],
            register_to=self
        )
        ui_units_panel = UiElementsBundle(
            name=UI_UNITS_PANEL,
            elements=[
                Button('game_button_stop.png', ui_x - 100, ui_y + 50,
                       functions=self.stop_all_units),
                Button('game_button_attack.png', ui_x, ui_y + 50,
                       functions=partial(self.window.cursor.force_cursor, 2))
            ],
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

    def change_interface_content(self, context=None):
        """
        Change elements displayed in interface to proper for currently selected
        gameobjects giving player access to context-options.
        """
        self._unload_all(exceptions=[UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, EDITOR])
        if context:
            if isinstance(context, Building):
                self.configure_building_interface(context)
            else:
                self.configure_units_interface(context)

    @ignore_in_editor_mode
    def configure_building_interface(self, context_building: Building):
        self.load_bundle(name=UI_BUILDINGS_PANEL, clear=True)
        ui_elements = context_building.create_ui_elements(*self.ui_position)
        self.get_bundle(UI_BUILDINGS_PANEL).extend(ui_elements)

    @property
    def ui_position(self) -> Tuple[float, float]:
        _, right, bottom, _ = self.viewport
        return right - UI_WIDTH / 2, bottom + SCREEN_Y

    @ignore_in_editor_mode
    def configure_units_interface(self, context_units: List[Unit]):
        self.load_bundle(name=UI_UNITS_PANEL)
        bundle = self.get_bundle(UI_BUILDINGS_PANEL)
        if all(isinstance(u, Engineer) for u in context_units):
            bundle.extend(Engineer.create_ui_buttons(*self.ui_position))

    def show_buildings_construction_options(self):
        self._unload_all(exceptions=[UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, EDITOR])
        for building_name in self.local_human_player.buildings_possible_to_build:
            log(building_name, True)  # TODO: real logic instead of test log

    def show_units_construction_options(self):
        self._unload_all(exceptions=[UI_OPTIONS_PANEL, UI_RESOURCES_SECTION, EDITOR])
        self.create_units_constructions_options()
        self.load_bundle(UI_UNITS_CONSTRUCTION_PANEL)

    def create_units_constructions_options(self):
        x, y = self.ui_position
        units_construction_bundle = self.get_bundle(UI_UNITS_CONSTRUCTION_PANEL)
        units_construction_bundle.elements.clear()
        positions = generate_2d_grid(x - 135, y + 20, 6, 4, 75, 75)
        for i, unit_name in enumerate(set(self.local_human_player.units_possible_to_build)):
            column, row = positions[i]
            producer = self.local_human_player.get_default_producer_of_unit(unit_name)
            hint = Hint(f'{unit_name}_production_hint.png', delay=0.5)
            b = ProgressButton(f'{unit_name}_icon.png', column, row, unit_name,
                               functions=partial(producer.start_production, unit_name)).add_hint(hint)
            b.bind_function(partial(producer.cancel_production, unit_name), MOUSE_BUTTON_RIGHT)
            units_construction_bundle.elements.append(b)

    def create_effect(self, effect_type: Any, name: str, x, y):
        """
        Add animated sprite to the 'self.effects' spritelist to display e.g.:
        explosions.
        """
        if effect_type is Explosion:
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
        self.change_interface_content()

    def create_random_scenario(self):
        if self.loader is None:
            self.test_scheduling_events()
            self.test_factions_and_players_creation()
            self.test_buildings_spawning()
            self.test_units_spawning()
            self.test_missions()

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

    def test_scheduling_events(self):
        event = ScheduledEvent(self, 5, self.scheduling_test)
        self.schedule_event(event)

    def test_factions_and_players_creation(self):
        faction = Faction(name='Freemen')
        player = HumanPlayer(id=2, color=GREEN, faction=faction)
        cpu_player = CpuPlayer(color=RED)
        self.local_human_player: Optional[Player] = self.players[2]
        player.start_war_with(cpu_player)

    def test_buildings_spawning(self):
        self.spawn('medium_vehicles_factory', self.players[2], (400, 600), garrison=1)
        self.spawn('garrison', self.players[2], (600, 800), garrison=1)
        self.spawn('command_center', self.players[2], (400, 900), garrison=1)
        self.spawn('medium_vehicles_factory', self.players[4], (1400, 1000), garrison=1)
        ConstructionSite('command_center', self.players[2], 850, 800),

    def spawn(self,
              object_name: str,
              player: Optional[Union[Player, int]] = None,
              position: Optional[Point] = None,
              *args,
              **kwargs) -> Optional[GameObject]:
        player = self.players.get(player, player)
        if position is None:
            position = self.map.get_random_position()
        return self.spawner.spawn(object_name, player, position, *args, **kwargs)

    def spawn_group(self,
                    names: List[str],
                    player: Union[Player, int],
                    position: Optional[Point] = None,
                    *args,
                    **kwargs) -> List[Unit]:
        player = self.players.get(player, player)
        if position is None:
            position = self.map.get_random_position()
        positions = self.pathfinder.get_group_of_waypoints(*position, len(names))
        return [
            self.spawner.spawn(name, player, map_grid_to_position(position), *args, **kwargs)
            for name, position in zip(names, positions)
        ]

    def test_units_spawning(self):
        units_names = ('tank_medium', 'apc', 'truck')
        walkable = list(self.map.all_walkable_nodes)
        for unit_name in units_names:
            for player in (self.players.values()):
                node = random.choice(walkable)
                walkable.remove(node)
                amount = PLAYER_UNITS if player.is_local_human_player else CPU_UNITS
                names = [unit_name] * amount
                self.spawn_group(names, player, node.position)

    def test_missions(self):
        human = self.local_human_player
        cpu_player = self.players[4]
        triggers = (
            MapRevealedTrigger(human).set_vp(1),
            NoUnitsLeftTrigger(human).triggers(Defeat()),
            TimePassedTrigger(human, 10).set_vp(1).triggers(Victory()),
            HasUnitsOfTypeTrigger(human, 'tank_medium').set_vp(1),
            NoUnitsLeftTrigger(cpu_player).triggers(Defeat())
        )
        self.current_mission = Mission('Test Mission', 'Map 1')\
            .add_players(human, cpu_player)\
            .add_triggers(*triggers)\
            .unlock_technologies_for_player(human, 'technology_1')

    def on_being_attached(self, attached: Observed):
        if isinstance(attached, GameObject):
            self.attach_gameobject(attached)
        elif isinstance(attached, (Player, Faction)):
            self.attach_player_or_faction(attached)
        elif isinstance(attached, (UiElementsBundle, UiElement)):
            super().on_being_attached(attached)
        else:
            log(f'Tried to attach {attached} which Game is unable to attach.')

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
            log(f'Tried to detach {detached} which Game is unable to detach.')

    def attach_gameobject(self, gameobject: GameObject):
        if isinstance(gameobject, PlayerEntity):
            if gameobject.is_building:
                self.buildings.append(gameobject)
            else:
                self.units.append(gameobject)
        else:
            self.static_objects.append(gameobject)

    def attach_player_or_faction(self, attached: Union[Player, Faction]):
        if isinstance(attached, Player):
            self.players[attached.id] = attached
        else:
            self.factions[attached.id] = attached

    def detach_gameobject(self, gameobject: GameObject):
        if isinstance(gameobject, PlayerEntity):
            if gameobject.is_building:
                self.buildings.remove(gameobject)
            else:
                self.units.remove(gameobject)
        else:
            self.static_objects.remove(gameobject)

    def detach_player_or_faction(self, detached: Union[Player, Faction]):
        if isinstance(detached, Player):
            del self.players[detached.id]
        else:
            del self.factions[detached.id]

    def get_notified(self, *args, **kwargs):
        pass

    def update_view(self, delta_time):
        for thing in (t for t in self.things_to_update_each_frame if t is not None):
            thing.update()
        super().update_view(delta_time)
        self.update_local_drawn_units_and_buildings()
        self.update_factions_and_players()

    def after_loading(self):
        self.window.show_view(self)
        # we put FoW before the interface to list of rendered layers to
        # assure that FoW will not cover player interface:
        self.drawn.insert(BEFORE_INTERFACE_LAYER, self.fog_of_war)
        super().after_loading()
        if self.loader is None:
            self.create_random_scenario()
        self.place_viewport_at_players_base_or_starting_position()
        self.update_interface_position(self.viewport[1], self.viewport[3])

    def save_timer(self):
        """Before saving timer, recalculate total time game was played."""
        self.timer.total = time.time() - self.timer.start
        return self.timer

    @logger()
    def load_timer(self, loaded_timer):
        """
        Subtract total time played from loading time to correctly reset timer
        after loading game and continue time-counting from where it was stopped
        last time.
        """
        self.timer = loaded_timer
        self.timer.start = time.time() - self.timer.total

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

    def update_factions_and_players(self):
        for faction in self.factions.values():
            faction.update()

    @timer(level=1, global_profiling_level=PROFILING_LEVEL)
    def on_draw(self):
        super().on_draw()
        if self.mini_map is not None:
            self.mini_map.draw()
        self.timer.draw()
        if self.debugger is not None:
            self.debugger.draw()
        if self.dialog is not None:
            self.draw_dialog(*self.dialog)

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

    def stop_all_units(self):
        for unit in self.units_manager.selected_units:
            unit.stop_completely()

    def unload(self):
        self.updated.clear()
        self.local_human_player = None
        self.units_manager.unselect_all_selected()
        self.local_drawn_units_and_buildings.clear()
        self.factions.clear()
        self.players.clear()
        self.window.settings = Settings()
        self.window.game_view = None

def run_profiled_game(settings: Settings):
    from pyprofiler import start_profile, end_profile
    with start_profile() as profiler:
        GameWindow(settings)
        run()
    end_profile(profiler, 35, True)


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
    from gameobjects.gameobject import GameObject, TerrainObject, Wreck
    from gameobjects.spawning import GameObjectsSpawner
    from map.fog_of_war import FogOfWar
    from buildings.buildings import Building, ConstructionSite
    from campaigns.missions import (
        Mission, load_campaigns, Campaign, MissionDescriptor
    )
    from campaigns.triggers import (
        NoUnitsLeftTrigger, MapRevealedTrigger, TimePassedTrigger, HasUnitsOfTypeTrigger
    )
    from campaigns.triggered_events import Defeat, Victory
    from user_interface.menu import Menu
    from user_interface.minimap import MiniMap
    from utils.debugging import GameDebugger
    from persistency.save_handling import SaveManager

    settings = Settings()

    if __status__ == 'development' and settings.pyprofiler:
        run_profiled_game(settings)
    else:
        run_game(settings)
