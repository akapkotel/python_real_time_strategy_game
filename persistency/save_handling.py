#!/usr/bin/env python

import os
import shelve
import time

from typing import Optional, Generator

from utils.classes import Singleton
from utils.functions import find_paths_to_all_files_of_type
from utils.logging import log, logger
from utils.data_types import SavedGames
from players_and_factions.player import Faction
from map.map import Map, Pathfinder
from user_interface.minimap import MiniMap
from gameobjects.spawning import ObjectsFactory
from effects.explosions import ExplosionsPool
# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!

MAP_EXTENSION = '.map'
SAVE_EXTENSION = '.sav'
SCENARIO_EXTENSION = '.scn'


class SaveManager(Singleton):
    """
    This manager works not only with player-created saved games, but also with
    predefined scenarios stored in the same file-format, but in ./scenarios
    direction.
    """
    game: Optional['Game'] = None

    def __init__(self, saves_path: str, scenarios_path: str):
        self.scenarios_path = scenarios_path = os.path.abspath(scenarios_path)
        self.saves_path = saves_path = os.path.abspath(saves_path)

        self.scenarios = self.find_all_scenarios(SCENARIO_EXTENSION, scenarios_path)
        self.saved_games = self.find_all_game_saves(SAVE_EXTENSION, saves_path)

        log(f'Found {len(self.saved_games)} saved games in {self.saves_path}.')

    @staticmethod
    def find_all_scenarios(extension: str, path: str) -> SavedGames:
        names_to_paths = find_paths_to_all_files_of_type(extension, path)
        return {
            name: os.path.join(path, name) for name, path in names_to_paths.items()
        }

    @staticmethod
    def find_all_game_saves(extension: str, path: str) -> SavedGames:
        names_to_paths = find_paths_to_all_files_of_type(extension, path)
        return {
            name: os.path.join(path, name) for name, path in names_to_paths.items()
        }

    def save_game(self, save_name: str, game: 'Game', scenario: bool = False):
        extension = SCENARIO_EXTENSION if scenario else SAVE_EXTENSION
        full_save_path = os.path.join(self.saves_path, save_name + extension)
        self.delete_saved_game(save_name)  # to avoid 'adding' to existing file
        with shelve.open(full_save_path) as file:
            file['saved_date'] = time.localtime()
            file['timer'] = game.save_timer()
            file['settings'] = game.settings
            file['viewports'] = game.viewport, game.window.menu_view.viewport
            file['map'] = game.map.save()
            file['factions'] = [f.save() for f in game.factions.values()]
            file['players'] = game.players
            file['local_human_player'] = game.local_human_player.id
            file['units'] = [unit.save() for unit in game.units]
            file['buildings'] = [building.save() for building in game.buildings]
            file['mission'] = game.current_mission
            file['permanent_units_groups'] = game.units_manager.permanent_units_groups
            file['fog_of_war'] = game.fog_of_war
            file['mini_map'] = game.mini_map.save()
        log(f'Game saved successfully as: {save_name + SAVE_EXTENSION}', True)

    def load_scenario(self, scenario_name: str) -> Generator:
        return self.load_game(scenario_name, scenario=True)

    def load_game(self, save_name: str, scenario: bool = False):
        save_name = self.add_extension_if_required(save_name, scenario)
        print(save_name)
        directory = self.scenarios_path if scenario else self.saves_path
        full_save_path = os.path.join(directory, save_name)
        with shelve.open(full_save_path) as file:
            for name in ('timer', 'settings', 'viewports', 'map', 'factions',
                         'players', 'local_human_player', 'units', 'buildings',
                         'mission', 'permanent_units_groups', 'fog_of_war',
                         'mini_map'):
                log(f'Loading: {name}...', console=True)
                yield eval(f"self.load_{name}(file['{name}'])")
        log(f'Game {save_name} loaded successfully!', True)
        yield

    @logger()
    def load_timer(self, loaded_timer):
        self.game.timer = loaded_timer

    @logger()
    def load_settings(self, settings):
        self.game.window.settings = self.game.settings = settings

    @logger()
    def load_viewports(self, viewports):
        self.game.viewport = viewports[0]
        self.game.window.menu_view.viewport = viewports[1]

    @logger()
    def load_map(self, map_file):
        self.game.map = game_map = Map(map_settings=map_file)
        self.game.pathfinder = pathfinder = Pathfinder(game_map)
        configs = self.game.window.configs
        self.game.spawner = ObjectsFactory(pathfinder, configs)
        self.game.explosions_pool = ExplosionsPool()

    @logger()
    def load_factions(self, factions):
        for f in factions:
            id, name, f, e = f['id'], f['name'], f['friends'], f['enemies']
            self.game.factions[id] = Faction(id, name, f, e)

    @logger()
    def load_players(self, players):
        self.game.players = {i: players[i] for i in players}

    @logger()
    def load_local_human_player(self, index):
        self.game.local_human_player = self.game.players[index]

    def load_units(self, units):
        return self.load_entities(units)

    def load_buildings(self, buildings):
        return self.load_entities(buildings)

    @logger()
    def load_entities(self, entities):
        """Respawn Units and Buildings."""
        for e in entities:
            self.game.spawn(
                e['object_name'], e['player'], e['position'], id=e['id']
            )

    @logger()
    def load_mission(self, mission):
        self.game.current_mission = mission
        print([c.player.units for c in mission.conditions])

    @logger()
    def load_permanent_units_groups(self, groups):
        self.game.units_manager.permanent_units_groups = groups
        for group_id, group in groups.items():
            for unit in group:
                unit.set_permanent_units_group(group_id)

    @logger()
    def load_fog_of_war(self, fog_of_war):
        self.game.fog_of_war = fog_of_war

    @logger()
    def load_mini_map(self, minimap):
        self.game.mini_map = MiniMap(minimap, loaded=True)

    def delete_saved_game(self, save_name: str):
        print(self.saved_games)
        try:
            os.remove(self.saved_games[save_name])
            del self.saved_games[save_name]
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

    @staticmethod
    def add_extension_if_required(save_name: str, scenario: bool):
        if not (SCENARIO_EXTENSION in save_name or SAVE_EXTENSION in save_name):
            extension = SCENARIO_EXTENSION if scenario else SAVE_EXTENSION
            return save_name + extension
        return save_name


# these imports are placed here to avoid circular-imports issue:
from game import Game
