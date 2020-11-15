#!/usr/bin/env python
from __future__ import annotations

import pyglet

from typing import Dict, Deque, Optional
from pyglet.media import Player
from pyglet.media.codecs.base import Source, StaticSource
from collections import deque

from utils.classes import Singleton
from utils.functions import find_paths_to_all_files_of_type, log


SOUNDS_EXTENSION = 'wav'

load_source = pyglet.media.load


class SoundPlayer(Singleton):
    # TODO: implement sound-playing

    def __init__(self, sounds_directory: Optional[str] = None):
        self.sounds: Dict[str, Source] = self._preload_sounds(sounds_directory)
        log(f'Loaded {len(self.sounds)} sounds.', True)

        self.queue: Deque[str] = deque()

        self.played: Dict[str, Player] = {}

        self.volume: float = 1.0

    @staticmethod
    def _preload_sounds(sounds_directory=None) -> Dict[str, Source]:
        names_to_paths = find_paths_to_all_files_of_type(SOUNDS_EXTENSION,
                                                         sounds_directory)
        return {
            name: load_source(f'{path}/{name}', streaming=False) for
            name, path in names_to_paths.items()
        }

    @staticmethod
    def _create_sound_source(full_sound_path: str) -> Source:
        source = load_source(full_sound_path, streaming=False)
        return StaticSource(source)

    def play_sound(self, name: str,
                   loop: bool = False,
                   volume: Optional[float] = None):
        if volume is not None:
            self.volume = volume
        if (source := self.sounds.get(name)) is not None:
            self._play_sound(name, source, loop)

    def stop_sound(self, name: str):
        self.played[name].delete()

    def pause(self):
        for player in self.played.values():
            player.pause()

    def play(self):
        for player in self.played.values():
            player.play()

    def clear(self):
        raise NotImplementedError

    def _play_sound(self, name: str, source: Source, loop: bool):
        if loop:
            self._create_looped_player_and_play(name, source)
        else:
            source.play()

    def _create_looped_player_and_play(self, name: str, source: Source):
        player = Player()
        player.queue(source)
        player.play()
        player.loop = True
        self.played[name] = player
