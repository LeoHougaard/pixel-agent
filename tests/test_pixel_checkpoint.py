import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('checkpoint', Path(__file__).parents[1] / 'pixel-checkpoint.py')
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


class CheckpointTest(unittest.TestCase):
    def test_backup_includes_wal_and_preserves_uncommitted_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            db = home / '.t3/userdata/state.sqlite'
            db.parent.mkdir(parents=True)
            projects = home / 'projects'
            projects.mkdir()
            draft = projects / 'unsaved-to-git.txt'
            draft.write_text('work in progress')
            with closing(sqlite3.connect(db)) as live:
                live.execute('PRAGMA journal_mode=WAL')
                live.execute('CREATE TABLE messages(body TEXT)')
                live.execute("INSERT INTO messages VALUES ('saved conversation')")
                live.commit()
                checkpoint.checkpoint(home)
                with closing(sqlite3.connect(home / '.local/state/pixel-agent/checkpoint/t3.sqlite')) as backup:
                    self.assertEqual('saved conversation', backup.execute('SELECT body FROM messages').fetchone()[0])
            self.assertEqual('work in progress', draft.read_text())
