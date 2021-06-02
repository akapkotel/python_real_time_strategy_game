#!/usr/bin/env python

import os
import shelve

from utils.classes import Singleton
from utils.functions import log, find_paths_to_all_files_of_type
from utils.data_types import SavedGames
from players_and_factions.player import Faction, Player
from map.map import Map, Pathfinder
from user_interface.minimap import MiniMap
from gameobjects.spawning import ObjectsFactory
from effects.explosions import ExplosionsPool

SAVE_EXTENSION = '.sav'
SCENARIO_EXTENSION = '.scn'


class SaveManager(Singleton):
    """
    This manager works not only with player-created saved games, but also with
    predefined scenarios stored in the same file-format, but in ./scenarios
    direction.
    """

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

    def save_game(self, save_name: str, game: 'Game'):
        full_save_path = os.path.join(self.saves_path, save_name)
        with shelve.open(full_save_path + SAVE_EXTENSION) as file:
            file['game_viewport'] = game.viewport
            file['menu_viewport'] = game.window.menu_view.viewport
            file['map'] = game.map.save()
            file['mission'] = game.mission
            file['factions'] = [f.save() for f in game.factions.values()]
            file['players'] = game.players
            file['local_human_player_id'] = game.local_human_player.id
            file['units'] = [unit.save() for unit in game.units]
            file['buildings'] = [building.save() for building in game.buildings]
            file['permanent_units_groups'] = game.permanent_units_groups
            file['fog_of_war'] = game.fog_of_war
            file['mini_map'] = game.mini_map
        log(f'Game saved successfully as: {save_name + SAVE_EXTENSION}', True)

    def load_game(self, save_name: str, game: 'Game'):
        full_save_path = os.path.join(self.saves_path, save_name)
        with shelve.open(full_save_path + SAVE_EXTENSION) as file:
            game.window.menu_view.viewport = file['menu_viewport']
            game.viewport = file['game_viewport']
            game.map = Map(map_settings=file['map'])
            game.mission = file['mission']
            game.pathfinder = Pathfinder(game.map)
            game.spawner = ObjectsFactory(game.pathfinder, game.window.configs)
            game.explosions_pool = ExplosionsPool()
            for f in file['factions']:
                id, name, friends, enemies = f['id'], f['name'], f['friends'], f['enemies']
                game.factions[f['id']] = Faction(id, name, friends, enemies)
            for i in file['players']:
                game.players[i] = file['players'][i]
            game.local_human_player = game.players[file['local_human_player_id']]
            for u in file['units']:
                game.spawn(u['object_name'], u['player'], u['position'], id=u['id'])
            for b in file['buildings']:
                game.spawn(b['object_name'], b['player'], b['position'], id=b['id'])
            game.permanent_units_groups = file['permanent_units_groups']
            game.fog_of_war = file['fog_of_war']
            game.mini_map = MiniMap()
        game.after_loading()
        log(f'Game {save_name + SAVE_EXTENSION} loaded successfully!', True)

    def delete_saved_game(self, save_name: str):
        try:
            os.remove(self.saved_games[save_name])
            del self.saved_games[save_name]
        except FileNotFoundError:
            pass

    def rename_saved_game(self, old_name: str, new_name: str):
        try:
            new = os.path.join(self.saves_path, new_name) + SAVE_EXTENSION
            os.rename(self.saved_games[old_name], new)
            self.saved_games[new_name] = new
            del self.saved_games[old_name]
        except Exception as e:
            log(f'{str(e)}', console=True)


from game import Game