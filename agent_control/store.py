import sqlite3
import time
import uuid


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, owner INTEGER NOT NULL, chat INTEGER NOT NULL,
          agent TEXT NOT NULL, project TEXT NOT NULL, native_id TEXT,
          created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (
          id INTEGER PRIMARY KEY, session TEXT NOT NULL, status TEXT NOT NULL,
          started REAL NOT NULL, finished REAL, exit_code INTEGER, output TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        self.db.execute("UPDATE runs SET status='interrupted', finished=? WHERE status='running'", (time.time(),))
        self.db.commit()

    def offset(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='offset'").fetchone()
        return int(row[0]) if row else 0

    def advance(self, offset):
        with self.db:
            self.db.execute("INSERT INTO settings VALUES ('offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(offset),))

    def create(self, owner, chat, agent, project):
        sid = uuid.uuid4().hex[:12]
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?)', (sid, owner, chat, agent, project, None, time.time()))
        return self.session(sid, owner)

    def session(self, sid, owner):
        row = self.db.execute('SELECT * FROM sessions WHERE id=? AND owner=?', (sid, owner)).fetchone()
        if not row:
            raise ValueError('Session not found.')
        return dict(row)

    def sessions(self, owner):
        return [dict(r) for r in self.db.execute('SELECT * FROM sessions WHERE owner=? ORDER BY created DESC LIMIT 20', (owner,))]

    def native(self, sid, value):
        if isinstance(value, str) and 0 < len(value) <= 200 and not value.startswith('-'):
            with self.db:
                self.db.execute('UPDATE sessions SET native_id=? WHERE id=?', (value, sid))

    def start(self, sid):
        with self.db:
            return self.db.execute("INSERT INTO runs(session,status,started) VALUES (?,'running',?)", (sid, time.time())).lastrowid

    def append(self, rid, text):
        with self.db:
            self.db.execute('UPDATE runs SET output=substr(output || ?, -24000) WHERE id=?', (text + '\n', rid))

    def finish(self, rid, status, code=None):
        with self.db:
            self.db.execute('UPDATE runs SET status=?,exit_code=?,finished=? WHERE id=?', (status, code, time.time(), rid))

    def latest(self, sid):
        row = self.db.execute('SELECT * FROM runs WHERE session=? ORDER BY id DESC LIMIT 1', (sid,)).fetchone()
        return dict(row) if row else None

    def history(self, sid):
        return [dict(r) for r in self.db.execute('SELECT id,status,exit_code FROM runs WHERE session=? ORDER BY id DESC LIMIT 10', (sid,))]
