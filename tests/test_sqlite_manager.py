"""
tests/test_sqlite_manager.py
Unit tests for database/sqlite_manager.py
"""

import gc
import os
import tempfile
import unittest

from database.sqlite_manager import SQLiteManager


class SQLiteManagerTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = SQLiteManager(db_path=self.db_path)

    def tearDown(self):
        # Force garbage collection to close any lingering SQLite connections
        del self.db
        gc.collect()
        for ext in ("", "-wal", "-shm"):
            path = self.db_path + ext
            if os.path.exists(path):
                try:
                    os.remove(path)
                except PermissionError:
                    pass

    # ---- crawl_queue ----

    def test_enqueue_and_get_pending(self):
        self.db.enqueue("https://a.com", "seed")
        pending = self.db.get_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["url"], "https://a.com")
        self.assertEqual(pending[0]["url_type"], "seed")

    def test_enqueue_duplicate_is_ignored(self):
        self.db.enqueue("https://a.com", "seed")
        self.db.enqueue("https://a.com", "seed")
        pending = self.db.get_pending()
        self.assertEqual(len(pending), 1)

    def test_get_pending_filtered_by_type(self):
        self.db.enqueue("https://a.com", "seed")
        self.db.enqueue("https://b.com", "website")
        pending = self.db.get_pending(url_type="seed")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["url_type"], "seed")

    def test_mark_status(self):
        self.db.enqueue("https://a.com", "seed")
        self.db.mark_status("https://a.com", "done")
        pending = self.db.get_pending()
        self.assertEqual(len(pending), 0)

    def test_get_pending_limit(self):
        for i in range(10):
            self.db.enqueue(f"https://a{i}.com", "seed")
        pending = self.db.get_pending(limit=3)
        self.assertEqual(len(pending), 3)

    # ---- discovered_urls ----

    def test_save_discovered_url(self):
        self.db.save_discovered_url("https://profile.com", "https://seed.com")
        urls = self.db.get_all_discovered_urls()
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["profile_url"], "https://profile.com")
        self.assertEqual(urls[0]["source_url"], "https://seed.com")

    def test_save_discovered_url_upsert(self):
        self.db.save_discovered_url("https://profile.com", "https://seed.com", "discovered")
        self.db.save_discovered_url("https://profile.com", "https://seed.com", "crawled")
        urls = self.db.get_all_discovered_urls()
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["crawl_status"], "crawled")

    # ---- websites ----

    def test_save_website(self):
        self.db.save_website("https://site.com", "https://profile.com")
        websites = self.db.get_all_websites()
        self.assertEqual(len(websites), 1)
        self.assertEqual(websites[0]["canonical_url"], "https://site.com")

    def test_save_website_duplicate_ignored(self):
        self.db.save_website("https://site.com", "https://profile.com")
        self.db.save_website("https://site.com", "https://profile2.com")
        websites = self.db.get_all_websites()
        self.assertEqual(len(websites), 1)

    # ---- contacts ----

    def test_save_contact(self):
        record = {
            "website": "https://site.com",
            "detail_page_url": "https://site.com/about",
            "name": "Test Org",
            "emails": "test@mycompany.org",
            "phones": "+15551234567",
            "crawl_status": "complete",
        }
        self.db.save_contact(record)
        contacts = self.db.get_all_contacts()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["website"], "https://site.com")
        self.assertEqual(contacts[0]["emails"], "test@mycompany.org")

    def test_save_contact_upsert(self):
        record1 = {
            "website": "https://site.com",
            "detail_page_url": "https://site.com/about",
            "emails": "old@mycompany.org",
            "phones": "",
            "crawl_status": "partial",
        }
        record2 = {
            "website": "https://site.com",
            "detail_page_url": "https://site.com/about",
            "emails": "new@mycompany.org",
            "phones": "+15551234567",
            "crawl_status": "complete",
        }
        self.db.save_contact(record1)
        self.db.save_contact(record2)
        contacts = self.db.get_all_contacts()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["emails"], "new@mycompany.org")
        self.assertEqual(contacts[0]["phones"], "+15551234567")

    def test_save_multiple_contacts(self):
        for i in range(5):
            self.db.save_contact(
                {
                    "website": f"https://site{i}.com",
                    "detail_page_url": f"https://site{i}.com/about",
                }
            )
        contacts = self.db.get_all_contacts()
        self.assertEqual(len(contacts), 5)

    # ---- empty state ----

    def test_empty_db_returns_empty_lists(self):
        self.assertEqual(self.db.get_all_contacts(), [])
        self.assertEqual(self.db.get_all_websites(), [])
        self.assertEqual(self.db.get_all_discovered_urls(), [])
        self.assertEqual(self.db.get_pending(), [])


if __name__ == "__main__":
    unittest.main()
