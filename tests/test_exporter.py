"""
tests/test_exporter.py
Unit tests for utils/exporter.py
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from utils.exporter import export_all


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

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

    @patch("utils.exporter.config")
    @patch("utils.exporter.dedup_records", side_effect=lambda x, k: x)
    def test_export_creates_csv_files(self, _mock_dedup, mock_config):
        mock_config.OUTPUT_DIR = self.tmpdir
        mock_config.CSV_DISCOVERED_URLS = os.path.join(self.tmpdir, "discovered_urls.csv")
        mock_config.CSV_WEBSITES = os.path.join(self.tmpdir, "websites.csv")
        mock_config.CSV_CONTACTS = os.path.join(self.tmpdir, "contacts.csv")
        mock_config.XLSX_MASTER = os.path.join(self.tmpdir, "master_database.xlsx")

        db = MagicMock()
        db.get_all_discovered_urls.return_value = [
            {"profile_url": "https://p1.com", "source_url": "https://s1.com"}
        ]
        db.get_all_websites.return_value = [
            {"canonical_url": "https://w1.com", "source_profile_url": "https://p1.com"}
        ]
        db.get_all_contacts.return_value = [
            {
                "website": "https://w1.com",
                "name": "Test",
                "emails": "a@test.com, b@test.com",
                "phones": "+15551234567",
            }
        ]

        export_all(db)

        self.assertTrue(os.path.exists(mock_config.CSV_DISCOVERED_URLS))
        self.assertTrue(os.path.exists(mock_config.CSV_WEBSITES))
        self.assertTrue(os.path.exists(mock_config.CSV_CONTACTS))
        self.assertTrue(os.path.exists(mock_config.XLSX_MASTER))

    @patch("utils.exporter.config")
    @patch("utils.exporter.dedup_records", side_effect=lambda x, k: x)
    def test_export_explodes_emails(self, _mock_dedup, mock_config):
        mock_config.OUTPUT_DIR = self.tmpdir
        mock_config.CSV_DISCOVERED_URLS = os.path.join(self.tmpdir, "discovered_urls.csv")
        mock_config.CSV_WEBSITES = os.path.join(self.tmpdir, "websites.csv")
        mock_config.CSV_CONTACTS = os.path.join(self.tmpdir, "contacts.csv")
        mock_config.XLSX_MASTER = os.path.join(self.tmpdir, "master_database.xlsx")

        db = MagicMock()
        db.get_all_discovered_urls.return_value = []
        db.get_all_websites.return_value = []
        db.get_all_contacts.return_value = [
            {
                "website": "https://w1.com",
                "emails": "a@test.com, b@test.com",
            }
        ]

        export_all(db)

        df = pd.read_csv(mock_config.CSV_CONTACTS)
        # Should have 2 rows (one per email) after explode
        self.assertEqual(len(df), 2)
        self.assertIn("email", df.columns)

    @patch("utils.exporter.config")
    @patch("utils.exporter.dedup_records", side_effect=lambda x, k: x)
    def test_export_empty_contacts(self, _mock_dedup, mock_config):
        mock_config.OUTPUT_DIR = self.tmpdir
        mock_config.CSV_DISCOVERED_URLS = os.path.join(self.tmpdir, "discovered_urls.csv")
        mock_config.CSV_WEBSITES = os.path.join(self.tmpdir, "websites.csv")
        mock_config.CSV_CONTACTS = os.path.join(self.tmpdir, "contacts.csv")
        mock_config.XLSX_MASTER = os.path.join(self.tmpdir, "master_database.xlsx")

        db = MagicMock()
        db.get_all_discovered_urls.return_value = []
        db.get_all_websites.return_value = []
        db.get_all_contacts.return_value = []

        export_all(db)

        # Files should still be created (even if empty)
        self.assertTrue(os.path.exists(mock_config.CSV_CONTACTS))


if __name__ == "__main__":
    unittest.main()
