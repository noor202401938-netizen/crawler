"""
tests/test_webapp.py
Unit tests for the Flask web dashboard.
"""

import os
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from webapp import app


class WebappTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        import gc

        gc.collect()
        for f in os.listdir(self.tmpdir):
            try:
                os.remove(os.path.join(self.tmpdir, f))
            except PermissionError:
                pass
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_renders(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        empty_contacts: list[dict[str, Any]] = []
        mock_db.get_all_contacts.return_value = empty_contacts
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Universal Crawler", response.data)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_shows_contacts(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = [
            {"website": "https://test.com", "name": "Test Org", "emails": "a@b.com"}
        ]
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Org", response.data)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_search_filter(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = [
            {"website": "https://test.com", "name": "Test Org", "emails": "a@b.com"},
            {"website": "https://other.com", "name": "Other Org", "emails": "x@y.com"},
        ]
        response = self.client.get("/?q=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Org", response.data)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_status_endpoint(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        empty_websites: list[dict[str, Any]] = []
        empty_contacts: list[dict[str, Any]] = []
        mock_db.get_all_websites.return_value = empty_websites
        mock_db.get_all_contacts.return_value = empty_contacts
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["running"])
        self.assertEqual(data["phase"], "idle")

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    def test_cancel_endpoint(self) -> None:
        import webapp

        webapp.state["running"] = True
        response = self.client.post("/cancel")
        self.assertEqual(response.status_code, 204)
        self.assertTrue(webapp.state["cancel"])
        webapp.state["running"] = False
        webapp.state["cancel"] = False

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_download_unknown_file_404(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        empty_contacts: list[dict[str, Any]] = []
        mock_db.get_all_contacts.return_value = empty_contacts
        response = self.client.get("/download/secret.env")
        self.assertEqual(response.status_code, 404)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_empty_state(self, mock_db_cls: Any) -> None:
        mock_db = mock_db_cls.return_value
        empty_contacts: list[dict[str, Any]] = []
        mock_db.get_all_contacts.return_value = empty_contacts
        response = self.client.get("/")
        self.assertIn(b"No contacts yet", response.data)

    @patch("webapp.run_phase_1_and_2_and_3")
    @patch("webapp.run_phase_4_and_5")
    @patch("webapp.export_all")
    @patch("webapp.SQLiteManager")
    @patch("webapp.Checkpoint")
    def test_run_crawl_restores_config(
        self, mock_cp: Any, mock_db: Any, mock_exp: Any, mock_p45: Any, mock_p123: Any
    ) -> None:
        import config
        from webapp import run_crawl

        orig_email = config.EXTRACT_EMAILS
        orig_prompt = config.CUSTOM_PROMPT

        # Run crawl with overridden extract flags and prompt
        run_crawl(["https://seed.test"], ["phones"], "custom instruction test")

        # Verify config was restored back to original values in finally block
        self.assertEqual(config.EXTRACT_EMAILS, orig_email)
        self.assertEqual(config.CUSTOM_PROMPT, orig_prompt)

    @patch("webapp.run_phase_1_and_2_and_3")
    @patch("webapp.run_phase_4_and_5")
    @patch("webapp.export_all")
    @patch("webapp.SQLiteManager")
    @patch("webapp.Checkpoint")
    def test_run_crawl_cancelled_phase(
        self, mock_cp: Any, mock_db: Any, mock_exp: Any, mock_p45: Any, mock_p123: Any
    ) -> None:
        import webapp
        from webapp import run_crawl

        def fake_p123(
            seeds: list[str], db: Any, cp: Any, cancel_check: Any = None
        ) -> None:
            webapp.state["cancel"] = True

        mock_p123.side_effect = fake_p123

        run_crawl(["https://seed.test"], ["emails"], "")
        self.assertEqual(webapp.state["phase"], "cancelled")
        self.assertFalse(webapp.state["running"])
        mock_p45.assert_not_called()
        mock_exp.assert_not_called()
        webapp.state["cancel"] = False


if __name__ == "__main__":
    unittest.main()
