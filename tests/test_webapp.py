"""
tests/test_webapp.py
Unit tests for the Flask web dashboard.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from webapp import app


class WebappTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
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
    def test_home_page_renders(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = []
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Universal Crawler", response.data)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_shows_contacts(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = [
            {"website": "https://test.com", "name": "Test Org", "emails": "a@b.com"}
        ]
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Org", response.data)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_search_filter(self, mock_db_cls):
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
    def test_status_endpoint(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.get_all_websites.return_value = []
        mock_db.get_all_contacts.return_value = []
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["running"])
        self.assertEqual(data["phase"], "idle")

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    def test_cancel_endpoint(self):
        import webapp

        webapp.state["running"] = True
        response = self.client.post("/cancel")
        self.assertEqual(response.status_code, 204)
        self.assertTrue(webapp.state["cancel"])
        webapp.state["running"] = False
        webapp.state["cancel"] = False

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_download_unknown_file_404(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = []
        response = self.client.get("/download/secret.env")
        self.assertEqual(response.status_code, 404)

    @patch("webapp.state", {"running": False, "error": None, "phase": "idle", "cancel": False})
    @patch("webapp.SQLiteManager")
    def test_home_page_empty_state(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.get_all_contacts.return_value = []
        response = self.client.get("/")
        self.assertIn(b"No contacts yet", response.data)


if __name__ == "__main__":
    unittest.main()
