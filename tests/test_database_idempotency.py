"""
tests/test_database_idempotency.py
Regression tests ensuring database schema initialization is idempotent
and does NOT drop or erase existing tables/data (preventing data loss).
"""

import gc
import os
import tempfile
import unittest

from database.sqlite_manager import SQLiteManager


class TestDatabaseIdempotency(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self) -> None:
        gc.collect()
        for ext in ("", "-wal", "-shm"):
            path = self.db_path + ext
            if os.path.exists(path):
                try:
                    os.remove(path)
                except PermissionError:
                    pass

    def test_schema_init_does_not_drop_contacts(self) -> None:
        """
        Critical regression test: Initializing SQLiteManager multiple times
        against the same database file MUST NOT drop or clear the 'contacts' table.
        """
        # 1. First initialization
        db1 = SQLiteManager(db_path=self.db_path)
        sample_contact = {
            "website": "https://example.com",
            "detail_page_url": "https://example.com/details",
            "name": "Dr. Jane Doe",
            "organization": "Acme Health",
            "emails": "jane@example.com",
            "phones": "+1-555-0100",
        }
        db1.save_contact(sample_contact)

        contacts_before = db1.get_all_contacts()
        self.assertEqual(len(contacts_before), 1)
        self.assertEqual(contacts_before[0]["emails"], "jane@example.com")

        # 2. Second initialization (simulates webapp request or resumed crawl)
        db2 = SQLiteManager(db_path=self.db_path)
        contacts_after = db2.get_all_contacts()

        # Contacts MUST still exist!
        self.assertEqual(len(contacts_after), 1, "Contacts table was dropped or wiped on re-init!")
        self.assertEqual(contacts_after[0]["emails"], "jane@example.com")
        self.assertEqual(contacts_after[0]["name"], "Dr. Jane Doe")

    def test_incremental_contacts_preserved(self) -> None:
        """Verify that appending records across multiple manager lifecycles works seamlessly."""
        db1 = SQLiteManager(db_path=self.db_path)
        db1.save_contact({"website": "https://a.com", "detail_page_url": "https://a.com/1", "name": "A"})

        db2 = SQLiteManager(db_path=self.db_path)
        db2.save_contact({"website": "https://b.com", "detail_page_url": "https://b.com/1", "name": "B"})

        db3 = SQLiteManager(db_path=self.db_path)
        all_contacts = db3.get_all_contacts()
        self.assertEqual(len(all_contacts), 2)
        names = {c["name"] for c in all_contacts}
        self.assertEqual(names, {"A", "B"})
