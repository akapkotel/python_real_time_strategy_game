#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, List, Optional

from utils.classes import Singleton
from utils.functions import find_paths_to_all_files_of_type, log

from arcade import load_sound, play_sound, stop_sound, Sound
from pyglet.media import Player


SOUNDS_DIRECTORY = 'resources/sounds'
SOUNDS_EXTENSION = 'wav'


class AudioPlayer(Singleton):

    def __init__(self,
                 sounds_directory: str = SOUNDS_DIRECTORY,
                 sound_on: bool = True,
                 music_on: bool = True,
                 sound_effects_on: bool = True):
        """
        AudioPlayer is a singleton.

        :param sounds_directory: str -- name of the directory without path
        :param sound_on: bool -- if sounds should be played or not
        """
        self._sound_on = sound_on
        self._music_on = music_on
        self._sound_effects_on = sound_effects_on

        self.volume: float = 1.0
        self.music_volume: float = self.volume
        self.effects_volume: float = self.volume

        self.sounds: Dict[str, Sound] = self._preload_sounds(sounds_directory)
        self.currently_played: List[Player] = []
        self.current_music: Optional[Player] = None

        log(f'Loaded {len(self.sounds)} sounds.', console=True)

    @staticmethod
    def _preload_sounds(sounds_directory=None) -> Dict[str, Sound]:
        names_to_paths = find_paths_to_all_files_of_type(SOUNDS_EXTENSION,
                                                         sounds_directory)
        return {
            name: load_sound(f'{path}/{name}', streaming=False) for
            name, path in names_to_paths.items()
        }

    @property
    def sound_on(self) -> bool:
        return self._sound_on

    @sound_on.setter
    def sound_on(self, value: bool):
        self.play() if value else self.pause()

    @property
    def music_on(self) -> bool:
        return self._music_on

    @music_on.setter
    def music_on(self, value: bool):
        self._music_on = value
        self.play() if value else self.pause()

    @property
    def sound_effects_on(self):
        return self._sound_effects_on

    @sound_effects_on.setter
    def sound_effects_on(self, value: bool):
        self._sound_effects_on = value

    def play_sound(self, name: str, volume: Optional[float] = None):
        """Play a single sound. Use this for sound effects."""
        if not self.sound_on:
            return
        if volume is not None:
            self.volume = volume
        self._play_sound(name)

    def play_music(self, name: str):
        """Use this for background sound-themes."""
        if self.current_music is not None:
            self._stop_music()
        self._play_sound(name, loop=True)

    def _stop_music(self):
        stop_sound(self.current_music)
        self.current_music = None

    def _play_sound(self, name: str, loop: bool = False):
        try:
            player = play_sound(self.sounds[name], self.volume, looping=loop)
            if loop:
                self.current_music = player
            else:
                self.currently_played.append(player)
        except KeyError:
            pass

    def play(self):
        """Plays all the sounds."""
        if self.current_music is not None:
            self.current_music.play()
        for player in self.currently_played:
            player.play()

    def pause(self):
        """Pauses playing all the sounds."""
        if self.current_music is not None:
            self.current_music.pause()
        for player in self.currently_played:
            player.pause()
