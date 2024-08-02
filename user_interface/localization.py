#!/usr/bin/env python

import json
import os
import pathlib


class LocalizationManager:
    def __init__(self, default_language='en'):
        """
        :param default_language: one of following: 'en', 'pl', 'ger'
        """
        self.current_language = default_language
        self.translations = {}
        self.json_files_path = os.path.abspath('resources\\languages')
        self._load_translations(default_language)

    def _load_translations(self, language: str):
        file_path = pathlib.Path(self.json_files_path, f'{language}.json')
        with open(file_path, 'r', encoding='utf-8') as file:
            self.translations = json.load(file)
        self.current_language = language

    def get(self, key):
        return self.translations.get(key, key)

    def set_language(self, language: str):
        """:param language: one of following: 'en', 'pl', 'ger'"""
        self._load_translations(language)
