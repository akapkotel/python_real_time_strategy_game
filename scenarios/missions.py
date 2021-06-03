#!/usr/bin/env python
from __future__ import annotations

from typing import List

from .conditions import Condition


class Mission:
    """
    Mission keeps track of the scenario-objectives and evaluates if Players
    achieved their objectives and checks win and fail conditions. It allows to
    control when the current game ends and what is the result of a game.
    """

    def __init__(self, id: int, name: str, map_name: str):
        self.id = id
        self.name = name
        self.map_name = map_name

        self.conditions: List[Condition] = []

    def new_condition(self):
        raise NotImplementedError

    def remove_condition(self):
        raise NotImplementedError

    def update(self):
        for condition in (c for c in self.conditions if c.is_met()):
            condition.execute_consequences()
            self.conditions.remove(condition)
