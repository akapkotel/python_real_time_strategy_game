#!/usr/bin/env python

import os

from functools import lru_cache
from typing import Dict, Tuple

import PIL
from arcade.arcade_types import Color
from shapely import speedups

from utils.colors import colors_names

SEPARATOR = '-' * 20

speedups.enable()


# def get_screen_size() -> Tuple[int, int]:
#     from PIL import ImageGrab
#     screen = ImageGrab.grab()
#     return int(screen.width), int(screen.height)


# def get_objects_with_attribute(instance: object,
#                                name: str,
#                                ignore: Tuple = ()) -> List[Any]:
#     """
#     Search all attributes of <instance> to find all objects which have their
#     own attribute of <name> and return these objects as List. You can also add
#     a Tuple of class names to be ignored during query.
#     """
#     attributes = instance.__dict__.values()
#     return [
#         attr for attr in attributes if
#         hasattr(attr, name) and not isinstance(attr, ignore)
#     ]


# very universal function
@lru_cache
def get_path_to_file(filename: str, extension: str = 'png') -> str:
    """
    Build full absolute path to the filename and return it + /filename.
    """
    correct_filename = add_extension(filename, extension)
    for directory in os.walk(os.getcwd()):
        if correct_filename in directory[2]:
            return f'{directory[0]}/{correct_filename}'


def get_object_name(filename: str) -> str:
    """
    Retrieve raw name of a GameObject from the absolute path to it's texture.
    """
    name_with_extension = remove_path_from_name(filename)
    return name_with_extension.split('.', 1)[0]


def remove_path_from_name(filename: str):
    return filename.rpartition('/')[-1]


def add_extension(object_name: str, extension: str = 'png') -> str:
    if not object_name.endswith(extension):
        return '.'.join((object_name, extension))
    return object_name


def all_files_of_type_named(extension: str,
                            base_directory: str,
                            named: str) -> Dict[str, str]:
    return {
        name: path for name, path
        in find_paths_to_all_files_of_type(extension, base_directory).items()
        if named in name
    }


def find_paths_to_all_files_of_type(extension: str,
                                    base_directory: str) -> Dict[str, str]:
    """
    Find and return a Dict containing all dirs where files with 'extension' are
    found.
    """
    names_to_paths = {}
    for directory in os.walk(os.path.abspath(base_directory)):
        for file_name in (f for f in directory[2] if f.endswith(extension)):
            names_to_paths[file_name] = directory[0]
    return names_to_paths


def add_player_color_to_name(name: str, color: Color) -> str:
    if (color := colors_names[color]) not in name:
        # split = name.split('.')
        # return ''.join((split[0], '_', color, '.', split[1]))
        return '_'.join((name, color))
    return name


def decolorised_name(name: str) -> str:
    for color in ('_red', '_green', '_blue', '_yellow'):
        if color in name:
            return name.replace(color, '')  # name.rsplit('_', 1)[0]
    return name


def name_to_texture_name(name: str) -> str:
    return name + '.png' if '.png' not in name else name


# def get_enemies(war: int) -> Tuple[int, int]:
#     """
#     Since each Player id attribute is a power of 2, id's can
#     be combined to sum, being an unique identifier, for eg.
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
            if self.settings.editor_mode:
                return
        except AttributeError:
            if self.game.settings.editor_mode:
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


def get_texture_size(texture_name: str, rows=1, columns=1) -> Tuple[int, int]:
    if '/' not in texture_name:
        texture_name = get_path_to_file(texture_name)
    image = PIL.Image.open(texture_name)
    return image.size[0] // columns, image.size[1] // rows
