#!/usr/bin/env python
from __future__ import annotations

from utils.game_logging import log_here
from utils.scheduling import ScheduledEvent


class UnitTask:
    """
    UnitsTask allows to assign to the groups of Units an objective, and then
    keep updating the task, checking if it is finished or not. Default way the
    task works is that it is automatically rescheduling its 'update' method
    after each update call, if any alive Unit is still assigned to it.
    """
    identifier = 0

    def __init__(self, units_manager, units):
        self.manager = units_manager
        self.units = units
        self.bind_task_to_units()
        self.schedule_next_update()

    def bind_task_to_units(self):
        for unit in self.units:
            self.remove_same_tasks(unit)
            unit.tasks.append(self)

    def remove_same_tasks(self, unit):
        for task in [t for t in unit.tasks]:
            if task.identifier == self.identifier:
                unit.tasks.remove(task)
                task.remove(unit)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__} id: {id(self)}'

    def update(self):
        log_here(f'Updating task: {self}, units: {self.units}', True)
        if self.condition():
            self.schedule_next_update()
        else:
            self.kill_task()

    def condition(self) -> bool:
        return self.units

    def schedule_next_update(self):
        self.manager.schedule_event(
            ScheduledEvent(self.manager, 1, self.update)
        )

    def remove(self, unit):
        try:
            self.units.remove(unit)
            unit.tasks.remove(self)
        except ValueError:
            pass

    def kill_task(self):
        self.manager.units_tasks.remove(self)
        for unit in self.units:
            unit.tasks.remove(self)


class TaskEnterBuilding(UnitTask):
    identifier = 1

    def __init__(self, units_manager, soldiers, building):
        self.target = building
        super().__init__(units_manager, soldiers)

    def update(self):
        for soldier in self.units[:]:
            self.check_if_soldier_can_enter(soldier)
        super().update()

    def condition(self) -> bool:
        return self.units and self.target and self.target.count_empty_garrison_slots

    def check_if_soldier_can_enter(self, soldier):
        if self.target.occupied_nodes.intersection(soldier.adjacent_nodes):
            if self.target.is_enemy(soldier) or self.target.count_empty_garrison_slots:
                soldier.enter_building(self.target)
            self.remove(soldier)
        else:
            self.check_if_soldier_heading_to_target(soldier)

    def check_if_soldier_heading_to_target(self, soldier):
        if not soldier.has_destination:
            x, y = self.target.position
            self.manager.game_view.pathfinder.navigate_units_to_destination(soldier, x, y)


class TaskEnterVehicle(TaskEnterBuilding):
    identifier = 2

    def __init__(self, units_manager, soldiers, vehicle):
        super().__init__(units_manager, soldiers, vehicle)

    def check_if_soldier_can_enter(self, soldier):
        if self.target.current_node in soldier.current_node.adjacent_nodes:
            soldier.enter_vehicle(self.target)
            self.units.remove(soldier)


class TaskMove(UnitTask):
    identifier = 3

    def __init__(self, units_manager, units, position):
        super().__init__(units_manager, units)
        self.target = position

    def condition(self) -> bool:
        return self.units[0].position != self.target
