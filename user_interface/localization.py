#!/usr/bin/env python

import json
import os
import pathlib
from typing import Dict


class LocalizationManager:
    def __init__(self, default_language='en'):
        """
        :param default_language: one of following: 'en', 'pl', 'ger'
        """
        self.current_language = default_language
        self._translations = {}
        self._retranslation_table = None
        self.json_files_path = os.path.abspath('resources\\languages')
        self._load_translations(default_language)

    @property
    def retranslations_table(self) -> Dict:
        return self._retranslation_table

    def _load_translations(self, language: str):
        file_path = pathlib.Path(self.json_files_path, f'{language}.json')
        with open(file_path, 'r', encoding='utf-8') as file:
            self._translations = json.load(file)
        self.current_language = language

    def _build_retranslation_table(self):
        self._retranslation_table = {translation: key for key, translation in self._translations.items()}

    def get(self, key):
        return self._translations.get(key, key)

    def set_language(self, language: str):
        """:param language: one of following: 'en', 'pl', 'ger'"""
        if self._translations:
            self._build_retranslation_table()
        self._load_translations(language)
