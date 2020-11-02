import unittest
from unittest import TestCase
from map import GridHandler


class TestGridHandler(TestCase):

    def test_normalize_position(self):
        positions = [(31, 64), (157, 0.78), (0, 0), (720.5, 111)]
        normalized = [(25, 60), (175, 20), (25, 20), (725, 100)]
        for i, position in enumerate(positions):
            x, y = position
            self.assertEqual(
                GridHandler.normalize_position(x, y), normalized[i]
            )


if __name__ == '__main__':
    unittest.main()
