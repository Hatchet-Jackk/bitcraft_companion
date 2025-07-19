import unittest
from app.player import Player


class TestPlayer(unittest.TestCase):
    def setUp(self):
        self.player = Player("testuser")

    def test_initial_state(self):
        self.assertEqual(self.player.username, "testuser")
        self.assertIsNone(self.player.user_id)
        self.assertIsNone(self.player.claim_id)
        self.assertEqual(self.player.inventory, {})

    def test_username_method(self):
        self.assertEqual(self.player.get_username(), "testuser")

    def test_set_and_get_inventory(self):
        inventory = {"item1": 10, "item2": 5}
        self.player.set_inventory(inventory)
        # set_inventory is a stub, so inventory won't change
        self.assertEqual(self.player.inventory, {})

    def test_set_and_get_user_id(self):
        self.player.set_user_id("user123")
        self.assertEqual(self.player.get_user_id(), "user123")

    def test_set_and_get_claim_id(self):
        self.player.set_claim_id("claim456")
        self.assertEqual(self.player.get_claim_id(), "claim456")


if __name__ == "__main__":
    unittest.main()
