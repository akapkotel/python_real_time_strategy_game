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
        self.event = None
        self.bind_task_to_units()
        self.schedule_next_update()

    def bind_task_to_units(self):
        for unit in self.units:
            self.remove_tasks_of_the_same_type(unit)
            unit.tasks.append(self)

    def remove_tasks_of_the_same_type(self, unit):
        for task in unit.tasks[::]:
            if task.identifier == self.identifier:
                unit.tasks.remove(task)
                task.remove(unit)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__} id: {id(self)}'

    def update(self):
        log_here(f'Updating task: {self}, units: {self.units}', True)
        if self.check_if_task_is_completed():
            self.kill_task()
        else:
            self.schedule_next_update()

    def schedule_next_update(self):
        self.event = event = ScheduledEvent(self.manager, 1, self.update)
        self.manager.schedule_event(event)

    def remove(self, unit):
        try:
            self.units.remove(unit)
            unit.tasks.remove(self)
        except ValueError:
            pass

    def check_if_task_is_completed(self):
        ...

    def kill_task(self):
        log_here(f'Killing task: {self}, units: {self.units}', True)
        self.manager.units_tasks.remove(self)
        self.manager.unschedule_event(self.event)
        for unit in self.units:
            unit.tasks.remove(self)
        self.units.clear()


class TaskEnterBuilding(UnitTask):
    identifier = 1

    def __init__(self, units_manager, soldiers, building):
        self.target = building
        super().__init__(units_manager, soldiers)

    def update(self):
        for soldier in self.units[:]:
            self.check_if_soldier_can_enter(soldier)
        super().update()

    def check_if_soldier_can_enter(self, soldier):
        if self.target.occupied_nodes.intersection(soldier.adjacent_nodes) and self.target.count_empty_garrison_slots:
            soldier.enter_building(self.target)
            self.remove(soldier)
        else:
            self.check_if_soldier_heading_to_target(soldier)

    def check_if_soldier_heading_to_target(self, soldier):
        if not soldier.has_destination:
            x, y = self.target.position
            self.manager.game_view.pathfinder.navigate_units_to_destination(soldier, x, y)

    def check_if_task_is_completed(self):
        if any((not self.units, not self.target.is_alive, not self.target.is_enemy)):
            self.kill_task()


class TaskEnterVehicle(TaskEnterBuilding):
    identifier = 2

    def __init__(self, units_manager, soldiers, vehicle):
        super().__init__(units_manager, soldiers, vehicle)


    def check_if_soldier_can_enter(self, soldier):
        if self.target.current_node in soldier.current_node.adjacent_nodes:
            soldier.enter_vehicle(self.target)
            self.units.remove(soldier)


class TaskAttackMove(UnitTask):
    identifier = 3

    def __init__(self, units_manager, units, x, y):
        super().__init__(units_manager, units)
        self.target = self.manager.game.map.position_to_node(x, y)

    def check_if_task_is_completed(self) -> bool:
        return not self.units or not any(u.has_destination for u in self.units)
