#!/usr/bin/env python

import os
import shelve
import time

from typing import List, Dict, Callable, Any, Generator, Tuple
from PIL import Image

from utils.functions import find_paths_to_all_files_of_type
from utils.game_logging import log, logger
from utils.data_types import SavedGames
from players_and_factions.player import Faction
from map.map import Map, Pathfinder
from user_interface.minimap import MiniMap
from gameobjects.spawning import GameObjectsSpawner
from effects.explosions import ExplosionsPool
# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


MAP_EXTENSION = '.map'
SAVE_EXTENSION = '.sav'
SCENARIO_EXTENSION = '.scn'
PROJECT_EXTENSION = '.proj'


def replace_bak_save_extension_with_sav(full_save_path):
    """
    On Windows Shelve library saves its data as 3 different files with .bak, 'dat and .dir extensions. The correct
    file to load saved data is that with 'bak extension.
    """
    os.rename(full_save_path + '.bak', full_save_path)


def add_extension_to_file_name_if_required(path: str, save_name: str, extension: str, finished: bool = False):
    return os.path.join(path, save_name if extension in save_name else save_name + extension)


class SaveManager:
    """
    This manager works not only with player-created saved games, but also with
    predefined scenarios stored in the same file-format, but in ./scenarios
    direction.
    TODO: saving and loading saved files does not work on Windows, since shelve produces 3 files with different extensions (.bak, .dir, .dat) instead of a single one
    """
    game = None

    def __init__(self, saves_path: str, scenarios_path: str, window):
        self.window = window
        self.scenarios_path = os.path.abspath(scenarios_path)
        self.saves_path = os.path.abspath(saves_path)
        self.projects_path = os.path.join(self.scenarios_path, 'projects')

        self.scenarios: SavedGames = {}
        self.saved_games: SavedGames = {}
        self.projects: SavedGames = {}

        self.update_scenarios(SCENARIO_EXTENSION, self.scenarios_path)
        self.update_saves(SAVE_EXTENSION, self.saves_path)
        self.update_projects(PROJECT_EXTENSION, self.projects_path)

        log(f'Found {len(self.scenarios)} scenarios in {self.scenarios_path}.', True)
        log(f'Found {len(self.projects)} scenarios in {self.projects_path}.', True)
        log(f'Found {len(self.saved_games)} saved games in {self.saves_path}.', True)

        self.loaded = False

    def __bool__(self):
        return not self.loaded

    def update_scenarios(self, extension: str, scenarios_path: str):
        self.scenarios = self.find_all_files(extension, scenarios_path)
        for name, path in self.scenarios.items():
            with shelve.open(path, 'r') as scenario_file:
                self.window.scenarios.append(scenario_file['scenario_descriptor'])

    def update_projects(self, extension: str, projects_path: str):
        self.projects = self.find_all_files(extension, projects_path)

    def update_saves(self, extension: str, saves_path: str):
        self.saved_games = self.find_all_files(extension, saves_path)

    @staticmethod
    def find_all_files(extension: str, path: str) -> SavedGames:
        names_to_paths = find_paths_to_all_files_of_type(extension, path)
        return {
            name: os.path.join(path, name).replace('.bak', '') for name, path in names_to_paths.items()
        }

    def set_correct_path_and_extension(self, scenario: bool, finished: bool) -> Tuple[str, str]:
        if scenario:
            path = self.scenarios_path if finished else self.projects_path
            extension = SCENARIO_EXTENSION if finished else PROJECT_EXTENSION
        else:
            path = self.saves_path
            extension = SAVE_EXTENSION
        return path, extension

    def save_game(self, save_name: str, game: 'Game', scenario: bool = False, finished: bool = False):
        path, extension = self.set_correct_path_and_extension(scenario, finished)
        full_save_path = add_extension_to_file_name_if_required(path, save_name, extension)
        self.delete_file(full_save_path, scenario)  # to avoid 'adding data' to existing file
        with shelve.open(full_save_path) as file:
            file['save_date'] = time.gmtime()
            file['timer'] = game.save_timer()
            file['settings'] = game.settings
            file['viewports'] = game.viewport, game.window.menu_view.viewport
            file['map'] = game.map.save()
            file['factions'] = [f.save() for f in game.factions.values()]
            file['players'] = game.players
            file['local_human_player'] = game.local_human_player.id
            file['units'] = [unit.save() for unit in game.units]
            file['buildings'] = [building.save() for building in game.buildings]
            file['scenario_descriptor'] = game.current_scenario.get_descriptor
            file['scenario_miniature'] = game.mini_map.create_minimap_texture()
            file['scenario'] = game.current_scenario
            file['permanent_units_groups'] = game.units_manager.permanent_units_groups
            if game.editor_mode and finished:
                game.fog_of_war.create_dark_sprites(forced=True)
            file['fog_of_war'] = game.fog_of_war
            file['mini_map'] = game.mini_map.save()
            file['scheduled_events'] = self.game.events_scheduler.save()
        if os.name == 'nt':
            replace_bak_save_extension_with_sav(full_save_path)
        self.update_files(extension, path)
        log(f'Game saved successfully as: {save_name + extension}', True)

    def update_files(self, extension, path):
        if extension is SAVE_EXTENSION:
            self.update_saves(extension, path)
        elif extension is SCENARIO_EXTENSION:
            self.update_scenarios(extension, path)
        else:
            self.update_projects(extension, path)

    def get_full_path_to_file_with_extension(self, filename: str) -> str:
        """
        Since we do not know if player want's to load his own saved game or to
        start a new game from a predefined .scn file, we determine it checking
        the file name provided to us and adding proper path and extension.
        """
        if SAVE_EXTENSION in filename:
            return os.path.join(self.saves_path, filename)
        elif SCENARIO_EXTENSION in filename:
            return os.path.join(self.scenarios_path, filename)
        elif PROJECT_EXTENSION in filename:
            return os.path.join(self.projects_path, filename)
        elif (full_name := filename + SCENARIO_EXTENSION) in self.scenarios:
            return os.path.join(self.scenarios_path, full_name)
        elif (full_name := filename + PROJECT_EXTENSION) in self.projects:
            return os.path.join(self.projects_path, full_name)
        else:
            return os.path.join(self.saves_path, filename + SAVE_EXTENSION)

    def extract_miniature_from_save(self, filename: str) -> Image:
        path = self.get_full_path_to_file_with_extension(filename)
        with shelve.open(path) as file:
            try:
                image = file['scenario_miniature']
            except KeyError:
                return None
        return image

    def read_save_date(self, filename: str, scenario: bool):
        full_save_path = self.get_full_path_to_file_with_extension(filename)
        with shelve.open(full_save_path) as file:
            date = file['save_date']
        return date

    def load_game(self, filename: str, editor_mode: bool = False) -> Generator[float, Any, None]:
        full_save_path = self.get_full_path_to_file_with_extension(filename)
        print(full_save_path)
        with shelve.open(full_save_path) as file:
            loaded = ['timer', 'settings', 'viewports', 'map', 'factions',
                      'players', 'local_human_player', 'units', 'buildings',
                      'scenario_descriptor', 'permanent_units_groups', 'fog_of_war',
                      'mini_map', 'scenario', 'scheduled_events']
            progress = 1 / len(loaded)
            for name in loaded:
                log(f'Loading: {name}...', console=True)
                self.loading_step(function=eval(f'self.load_{name}'), argument=file[name])
                log(f'Saved data: {name} was successfully loaded!', console=True)
                yield progress
            self.game.settings.editor_mode = editor_mode
        self.loaded = True
        log(f'Saved game: {filename} was loaded successfully!', console=True)

    @staticmethod
    def loading_step(function: Callable, argument: Any):
        function(argument)

    def load_scenario_descriptor(self, descriptor):
        pass

    def load_timer(self, loaded_timer):
        self.game.timer = loaded_timer

    def load_settings(self, settings):
        self.window.settings.__dict__.update(settings.__dict__)
        # recalculating rendering layers is required since settings changed and
        # LayeredSpriteList instances where instantiated with settings values
        # from the menu, not from the loaded file
        for spritelist in self.game.updated:
            try:
                spritelist.rendering_layers = spritelist.create_rendering_layers()
            except AttributeError:
                pass

    def load_viewports(self, viewports):
        self.game.viewport = viewports[0]
        self.game.window.menu_view.viewport = viewports[1]

    def load_map(self, map_settings):
        self.game.map = game_map = Map(map_settings=map_settings)
        self.game.pathfinder = Pathfinder(game_map)

    def load_factions(self, factions):
        for f in factions:
            id, name, f, e = f['id'], f['name'], f['friends'], f['enemies']
            self.game.factions[id] = Faction(id, name, f, e)

    def load_players(self, players):
        self.game.players = {i: players[i] for i in players}

    def load_local_human_player(self, index):
        self.game.local_human_player = self.game.players[index]

    def load_units(self, units):
        return self.load_entities(units)

    def load_buildings(self, buildings):
        return self.load_entities(buildings)

    def load_entities(self, entities):
        """
        Respawn Units and Buildings. Respawning is executed in two steps. First a new GameObject is instantiated, and
        then it's original state is retrieved and set by calling after_spawn method.
        """
        if self.game.spawner is None:
            self.game.spawner = GameObjectsSpawner()
        if self.game.explosions_pool is None:
            self.game.explosions_pool = ExplosionsPool(self.game)
        for e in entities:
            entity = self.game.spawn(e['object_name'], e['player'], e['position'], object_id=e['id'])
            entity.after_respawn(e)

    def load_scenario(self, scenario):
        self.game.current_scenario = scenario

    def load_permanent_units_groups(self, groups):
        self.game.units_manager.permanent_units_groups = groups
        for group_id, group in groups.items():
            for unit in group:
                unit.set_permanent_units_group(group_id)

    def load_fog_of_war(self, fog_of_war):
        self.game.fog_of_war = fog_of_war

    def load_mini_map(self, minimap):
        self.game.mini_map = MiniMap(minimap, loaded=True)

    def load_scheduled_events(self, scheduled_events: List[Dict]):
        self.game.events_scheduler.load(scheduled_events)

    def delete_file(self, save_name: str, scenario: bool):
        paths = self.scenarios if scenario else self.saved_games
        try:
            os.remove(paths[save_name])
            del paths[save_name]
        except Exception as e:
            log(f'{str(e)}', console=True)

    def rename_saved_game(self, old_name: str, new_name: str):
        try:
            new = os.path.join(self.saves_path, new_name)
            os.rename(self.saved_games[old_name], new)
            self.saved_games[new_name] = new
            del self.saved_games[old_name]
        except Exception as e:
            log(f'{str(e)}', console=True)


# these imports are placed here to avoid circular-imports issue:
from game import Game
