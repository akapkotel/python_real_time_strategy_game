#!/usr/bin/env python
from __future__ import annotations

from typing import Tuple, List, Deque, Optional, Any
from dataclasses import dataclass, field
from abc import abstractmethod
from collections import deque

from utils.data_types import GridPosition


@dataclass
class UnitTask:
    name: str = ''
    priority: int = 0
    id: int = 0
    target: Any = None
    evaluation_args: Optional[Tuple[str]] = field(default_factory=tuple)

    @abstractmethod
    def done(self, *args, **kwargs):
        raise NotImplementedError


class TaskIdle(UnitTask):
    name = 'idle'

    def done(self):
        return False


class MoveTask(UnitTask):
    name: str = 'move'
    target: GridPosition

    def done(self, position: GridPosition):
        x, y = position
        return (int(x), int(y)) == self.target


class TasksExecutor:

    def __init__(self, start_with_tasks: Optional[List[UnitTask]] = None):
        self.tasks: Deque[UnitTask] = deque()
        self.paused_tasks: List[int] = []
        if start_with_tasks is not None:
            self.tasks.extend(start_with_tasks)
            self.start_all_tasks()

    def evaluate_tasks(self) -> int:
        for i, task in enumerate(self.tasks.copy()):
            if self.paused_tasks[i]:
                continue
            if (keys := task.evaluation_args) is not None:
                args = tuple(getattr(self, key) for key in keys)
                print(args)
                if task.done(*args):
                    self.tasks.remove(task)
            elif task.done():
                self.tasks.remove(task)
        return len(self.tasks)

    def add_task(self, task: UnitTask):
        self.tasks.append(task)
        self.paused_tasks.append(0)

    def cancel_task(self, task_id: int):
        try:
            task = [task for task in self.tasks if id(task) == task_id][0]
        except IndexError:
            return
        self.paused_tasks.remove(self.tasks.index(task))
        self.tasks.remove(task)

    def cancel_all_tasks(self):
        self.paused_tasks.clear()
        self.tasks.clear()

    def pause_all_tasks(self):
        self.paused_tasks = [1 for _ in self.tasks]

    def start_all_tasks(self):
        self.paused_tasks = [0 for _ in self.tasks]
