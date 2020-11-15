#!/usr/bin/env python

import os
import shelve

from typing import Optional

from utils.classes import Singleton
from utils.functions import log, find_paths_to_all_files_of_type
from utils.data_types import SavedGames

SAVE_EXTENSION = 'save'


class SaveManager(Singleton):

    def __init__(self, saves_directory: str):
        self.path_to_saves = path = os.path.abspath(saves_directory)

        self.saved_games = self.find_all_save_files(SAVE_EXTENSION, path)

        log(f'Found {len(self.saved_games)} saved games in {self.path_to_saves}.')

    @staticmethod
    def find_all_save_files(extension: str, path: str) -> SavedGames:
        names_to_paths = find_paths_to_all_files_of_type(extension, path)
        return {name: f'{path}/{name}' for name, path in names_to_paths.items()}

    def save_game(self, save_name: str):
        raise NotImplementedError

    def load_game(self, save_name: str):
        raise NotImplementedError

    def delete_saved_game(self, save_name: str):
        try:
            os.remove(self.saved_games[save_name])
            del self.saved_games[save_name]
        except FileNotFoundError:
            pass

    def rename_saved_game(self, old_name: str, new_name: str):
        try:
            new_path = f'{self.path_to_saves}/{new_name}.{SAVE_EXTENSION}'
            os.rename(self.saved_games[old_name], new_path)
            del self.saved_games[old_name]
            self.saved_games[new_name] = new_path
        except Exception as e:
            log(f'{str(e)}', console=True)
