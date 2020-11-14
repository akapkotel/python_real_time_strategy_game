#!/usr/bin/env python

import os
import shelve

from utils.classes import Singleton
from utils.functions import get_path_to_file, log
from utils.data_types import SavedGames

SAVE_EXTENSION = '.save'
SAVES_DIRECTORY = '/saved_games'


class SaveManager(Singleton):

    def __init__(self):
        self.saved_games_dir = os.getcwd() + SAVES_DIRECTORY
        self.saved_games: SavedGames = self.find_all_save_files()

    def find_all_save_files(self) -> SavedGames:
        saved_games = {}
        for file_name in os.listdir(self.saved_games_dir):
            if file_name.endswith(SAVE_EXTENSION):
                save_name = file_name.rsplit('.')[0]
                saved_games[save_name] = get_path_to_file(file_name)
        return saved_games

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
            new_path = self.saved_games_dir + f'/{new_name}.{SAVE_EXTENSION}'
            os.rename(self.saved_games[old_name],
                      new_path)
            del self.saved_games[old_name]
            self.saved_games[new_name] = new_path
        except Exception as e:
            log(f'{str(e)}', console=True)
