from unittest import TestCase, main

from units.units_tasking import TaskIdle, MoveTask, TasksExecutor


class TestTasksExecutor(TestCase):

    def setUp(self) -> None:
        self.executor: TasksExecutor = TasksExecutor()

    def tearDown(self) -> None:
        self.executor = None

    def test_evaluate_tasks(self):
        self.assertEqual(self.executor.evaluate_tasks(), 0)

        self.executor.add_task(TaskIdle())
        self.assertEqual(1, self.executor.evaluate_tasks())

        position = 50, 50
        task = MoveTask(target=position, evaluation_args=('position',))
        self.executor.add_task(task)
        setattr(self.executor, 'position', (50, 50))
        self.executor.evaluate_tasks()

    def test_add_task(self):
        task = TaskIdle()
        self.executor.add_task(task)
        self.assertIn(task, self.executor.tasks)

    def test_cancel_task(self):
        task = TaskIdle()
        self.executor.add_task(task)
        self.executor.cancel_task(id(task))
        self.assertNotIn(task, self.executor.tasks)
        self.assertEqual(0, len(self.executor.tasks))

    def test_cancel_all_tasks(self):
        tasks = [TaskIdle() for _ in range(10)]
        for task in tasks:
            self.executor.add_task(task)
        self.executor.cancel_all_tasks()
        self.assertEqual(0, len(self.executor.tasks))

    def test_pause_all_tasks(self):
        tasks = [TaskIdle() for _ in range(10)]
        for task in tasks:
            self.executor.add_task(task)
        self.executor.pause_all_tasks()
        self.assertEqual([1 for _ in range(10)], self.executor.paused_tasks)

    def test_start_all_tasks(self):
        tasks = [TaskIdle() for _ in range(10)]
        for task in tasks:
            self.executor.add_task(task)
        self.executor.pause_all_tasks()
        self.executor.start_all_tasks()
        self.assertEqual([0 for _ in range(10)], self.executor.paused_tasks)


if __name__ == '__main__':
    main()
