#!/usr/bin/env python
from __future__ import annotations

from utils.logging import log
from utils.scheduling import ScheduledEvent


class UnitTask:
    """

    """

    def __init__(self, units_manager, units):
        self.manager = units_manager
        self.units = units
        self.bind_task_to_units()
        self.schedule_next_update()

    def bind_task_to_units(self):
        for unit in self.units:
            unit.tasks.append(self)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__} id: {id(self)}'

    def update(self):
        log(f'Updating task: {self}', True)
        if self.units:
            self.schedule_next_update()
        else:
            self.kill_task()

    def schedule_next_update(self):
        self.manager.schedule_event(
            ScheduledEvent(self.manager, 1, self.update)
        )

    def kill_task(self):
        self.manager.units_tasks.remove(self)
        for unit in self.units:
            unit.tasks.remove(self)


class TaskEnterBuilding(UnitTask):

    def __init__(self, units_manager, soldiers, building):
        self.building = building
        super().__init__(units_manager, soldiers)

    def update(self):
        for soldier in [s for s in self.units]:
            self.check_if_soldier_can_enter_building(soldier)
        super().update()

    def check_if_soldier_can_enter_building(self, soldier):
        for adjacent in soldier.current_node.adjacent_nodes:
            if adjacent in self.building.occupied_nodes:
                soldier.enter_building(self.building)
                self.units.remove(self)
                break
