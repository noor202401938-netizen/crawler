"""
tests/test_checkpoint.py
Unit tests for checkpoint resume functionality.
"""

import os
import tempfile
import unittest

from utils.checkpoint import Checkpoint


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.checkpoint_path = os.path.join(self.tmpdir, "checkpoint.json")

    def tearDown(self):
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
        os.rmdir(self.tmpdir)

    def test_fresh_checkpoint_starts_empty(self):
        cp = Checkpoint(path=self.checkpoint_path)
        self.assertEqual(cp.state["completed_seeds"], [])
        self.assertEqual(cp.state["completed_websites"], [])

    def test_mark_seed_done(self):
        cp = Checkpoint(path=self.checkpoint_path)
        cp.mark_seed_done("https://example.com")
        self.assertTrue(cp.is_seed_done("https://example.com"))
        self.assertFalse(cp.is_seed_done("https://other.com"))

    def test_mark_website_done(self):
        cp = Checkpoint(path=self.checkpoint_path)
        cp.mark_website_done("https://site.com")
        self.assertTrue(cp.is_website_done("https://site.com"))
        self.assertFalse(cp.is_website_done("https://other.com"))

    def test_persists_to_disk(self):
        cp = Checkpoint(path=self.checkpoint_path)
        cp.mark_seed_done("https://seed.com")
        cp.mark_website_done("https://web.com")

        # Load a new instance from the same file
        cp2 = Checkpoint(path=self.checkpoint_path)
        self.assertTrue(cp2.is_seed_done("https://seed.com"))
        self.assertTrue(cp2.is_website_done("https://web.com"))

    def test_no_duplicate_seeds(self):
        cp = Checkpoint(path=self.checkpoint_path)
        cp.mark_seed_done("https://seed.com")
        cp.mark_seed_done("https://seed.com")  # duplicate
        self.assertEqual(len(cp.state["completed_seeds"]), 1)

    def test_corrupt_file_starts_fresh(self):
        with open(self.checkpoint_path, "w") as f:
            f.write("not valid json {{{")

        # Should not raise, just start fresh
        cp = Checkpoint(path=self.checkpoint_path)
        self.assertEqual(cp.state["completed_seeds"], [])

    def test_multiple_seeds_and_websites(self):
        cp = Checkpoint(path=self.checkpoint_path)
        for i in range(5):
            cp.mark_seed_done(f"https://seed{i}.com")
            cp.mark_website_done(f"https://web{i}.com")

        self.assertEqual(len(cp.state["completed_seeds"]), 5)
        self.assertEqual(len(cp.state["completed_websites"]), 5)


if __name__ == "__main__":
    unittest.main()
