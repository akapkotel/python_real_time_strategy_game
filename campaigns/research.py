#!/usr/bin/env python

from abc import abstractmethod
from functools import partial
from typing import Tuple, Dict

from utils.data_types import TechnologyId
from utils.game_logging import log_here


class Technology:
    def __init__(self,
                 id: TechnologyId,
                 name: str,
                 required: Tuple[TechnologyId] = (),
                 unlock: Tuple[TechnologyId] = (),
                 difficulty: float = 100.0,
                 funding_cost: float = 0,
                 effect: str = None):
        self.id = id
        self.name = name
        self.description = None
        self.required = required
        self.unlock = unlock
        self.difficulty = difficulty
        self.funding_cost = 0
        self.function_on_researched = effect

    def unlocked(self, researcher) -> bool:
        return all(tech_id in researcher.known_technologies for tech_id in self.required)

    @abstractmethod
    def gain_technology_effects(self, researcher):
        partial(eval(f'self.{self.function_on_researched}'), researcher)()

    def kill(self, researcher):
        researcher.kill()
