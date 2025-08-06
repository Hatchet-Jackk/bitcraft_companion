import unittest
import sys
import customtkinter as ctk
from app.ui.main_window import MainWindow


class TestMainWindow(unittest.TestCase):
    def setUp(self):
        self.app = MainWindow()

    def tearDown(self):
        self.app.destroy()

    def test_main_window_elements(self):
        # Check window title
        self.assertEqual(self.app.title(), "Bitcraft Companion")
        # Check claim info header exists
        self.assertIsNotNone(self.app.claim_info)
        # Check tab_frame and tab_buttons exist
        self.assertIsNotNone(self.app.tab_frame)
        self.assertIsInstance(self.app.tab_buttons, dict)
        for name in ["Claim Inventory", "Passive Crafting", "Travellers", "Other"]:
            self.assertIn(name, self.app.tab_buttons)
        # Check search field exists
        self.assertIsNotNone(self.app.search_field)
        # Check table frame exists
        self.assertIsNotNone(self.app.table_frame)


if __name__ == "__main__":
    unittest.main()
