#!/usr/bin/env python

import json
import os
import pathlib

from user_interface.user_interface import UiBundlesHandler


class LocalizationManager:
    def __init__(self, default_language='English'):
        """
        :param default_language: one of following: 'English', 'Polish', 'German'
        """
        self.current_language = default_language
        self._translations = {}
        self._retranslation_table = None
        self.json_files_path = os.path.abspath('resources\\languages')
        self._load_translations(default_language)

    def _load_translations(self, language: str):
        file_path = pathlib.Path(self.json_files_path, f'{language.lower()}.json')
        with open(file_path, 'r', encoding='utf-8') as file:
            self._translations = json.load(file)
        self.current_language = language

    def _build_retranslation_table(self):
        self._retranslation_table = {translation: key for key, translation in self._translations.items()}

    def get(self, key):
        return self._translations.get(key, key)

    def set_language(self, language: str):
        """:param language: one of following: 'English', 'Polish', 'German'"""
        if self._translations:
            self._build_retranslation_table()
        self._load_translations(language)

    def reload_translations(self, *views):
        for view in views:
            if isinstance(view, UiBundlesHandler):
                self._retranslate_ui_elements(view)

    def _retranslate_ui_elements(self, view):
        for bundle in view.ui_elements_bundles.values():
            for element in (e for e in bundle if hasattr(e, 'text')):
                key = self._retranslation_table[element.text]
                element.text = self.get(key)
