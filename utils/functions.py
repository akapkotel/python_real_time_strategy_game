#!/usr/bin/env python

import os

from pathlib import Path
from functools import lru_cache

from PIL import Image
from arcade.arcade_types import Color

from utils.colors import colors_names
from utils.game_logging import log_here


@lru_cache
def get_path_to_file(filename: str, extension: str = 'png') -> Path:
    """
    Build full absolute path to the filename and return it + /filename.
    """
    correct_filename = add_extension(filename, extension)
    for dirpath, dirnames, filenames in os.walk(os.getcwd()):
        if correct_filename in filenames:
            return Path(dirpath, correct_filename)
    log_here(f'File {filename} does not exist!', console=True)


@lru_cache
def get_object_name(filename: str) -> str:
    """
    Retrieve raw name of a GameObject from the absolute path to its texture.
    """
    name_with_extension = remove_path_from_name(filename)
    return name_with_extension.split('.', 1)[0]


@lru_cache
def remove_path_from_name(filename: str):
    return filename.rpartition('/')[-1]


def add_extension(object_name: str, extension: str = 'png') -> str:
    return object_name if object_name.endswith(extension) else '.'.join((object_name, extension))


def all_files_of_type_named(extension: str,
                            base_directory: str,
                            named: str) -> dict[str, str]:
    return {
        name: path for name, path
        in find_paths_to_all_files_of_type(extension, base_directory).items()
        if named in name
    }


def find_paths_to_all_files_of_type(extension: str,
                                    base_directory: str) -> dict[str, str]:
    """
    Find and return a Dict containing all dirs where files with 'extension' are
    found.
    """
    names_to_paths = {}
    for path, dirs, files in os.walk(os.path.abspath(base_directory)):
        for file_name in (f for f in files if f.endswith(extension)):
            names_to_paths[file_name] = path
    return names_to_paths


@lru_cache
def add_player_color_to_name(name: str, color: Color) -> str:
    color_name = colors_names[color]
    if not name.endswith(color_name):
        return '_'.join((name, color_name))
    return name


# def get_enemies(war: int) -> Tuple[int, int]:
#     """
#     Since each Player id attribute is a power of 2, id's can
#     be combined to sum, being a unique identifier, for eg.
#     Player with id 8 and Player with id 128 make unique sum
#     136. To save pairs of hostile Players you can sum their
#     id's and this functions allows to retrieve pair from the
#     saved value. Limit of Players in game is 16, since 2^32
#     gives 8589934592, which is highest id checked by functions.
#     """
#     index = 8589934592  # 2 to power of 32
#     while index > 2:
#         if war < index:
#             index >>= 1
#         else:
#             break
#     return index, war - index


def ignore_in_editor_mode(func):
    def wrapper(self, *args, **kwargs):
        try:
            if self.game.settings.editor_mode:
                return
        except AttributeError:
            if self.settings.editor_mode:
                return
        return func(self, *args, **kwargs)
    return wrapper


def ignore_in_menu(func):
    def wrapper(self, *args, **kwargs):
        if not self.window.is_game_running:
            return
        return func(self, *args, **kwargs)
    return wrapper


def ignore_in_game(func):
    def wrapper(self, *args, **kwargs):
        if self.window.is_game_running:
            return
        return func(self, *args, **kwargs)
    return wrapper


def get_texture_size(texture_name: str, rows=1, columns=1) -> tuple[int, int]:
    if '/' not in texture_name:
        texture_name = get_path_to_file(texture_name)
    with Image.open(texture_name) as image:
        width, height = image.size
    return width // columns, height // rows
