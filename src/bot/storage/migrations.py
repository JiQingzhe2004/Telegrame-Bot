from __future__ import annotations

from dataclasses import dataclass

from bot.storage.db import Database


@dataclass(frozen=True)
class Migration:
    version: str
    sql: str


MIGRATIONS: list[Migration] = [
    Migration(
        version="0001_init",
        sql="""
        CREATE TABLE IF NOT EXISTS schema_migrations(
          version TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats(
          chat_id INTEGER PRIMARY KEY,
          title TEXT,
          type TEXT,
          created_at TEXT,
          updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS chat_settings(
          chat_id INTEGER PRIMARY KEY,
          mode TEXT,
          ai_enabled INTEGER,
          ai_threshold REAL,
          action_policy TEXT,
          rate_limit_policy TEXT,
          language TEXT,
          level3_mute_seconds INTEGER DEFAULT 604800,
          updated_at TEXT,
          FOREIGN KEY(chat_id) REFERENCES chats(chat_id)
        );
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY,
          username TEXT,
          first_name TEXT,
          last_name TEXT,
          is_bot INTEGER,
          updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages(
          chat_id INTEGER,
          message_id INTEGER,
          user_id INTEGER,
          date TEXT,
          text TEXT,
          meta TEXT,
          PRIMARY KEY(chat_id, message_id)
        );
        CREATE TABLE IF NOT EXISTS moderation_decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER,
          message_id INTEGER,
          user_id INTEGER,
          rule_hit TEXT,
          ai_used INTEGER,
          ai_model TEXT,
          ai_input_ref TEXT,
          ai_output TEXT,
          final_level INTEGER,
          confidence REAL,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS enforcements(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER,
          user_id INTEGER,
          message_id INTEGER,
          action TEXT,
          duration_seconds INTEGER,
          reason TEXT,
          operator TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS user_strikes(
          chat_id INTEGER,
          user_id INTEGER,
          score INTEGER,
          last_violation_at TEXT,
          PRIMARY KEY(chat_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS whitelists(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER,
          type TEXT,
          value TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS blacklists(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER,
          type TEXT,
          value TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS appeals(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          message TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS enforcement_rollbacks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          enforcement_id INTEGER NOT NULL,
          chat_id INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          status TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date);
        CREATE INDEX IF NOT EXISTS idx_messages_chat_user_date ON messages(chat_id, user_id, date);
        CREATE INDEX IF NOT EXISTS idx_moderation_chat_created ON moderation_decisions(chat_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_enforcement_chat_created ON enforcements(chat_id, created_at);
        """,
    )
    ,
    Migration(
        version="0002_system_config",
        sql="""
        CREATE TABLE IF NOT EXISTS system_config(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS setup_sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          expires_at TEXT NOT NULL,
          consumed_at TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_setup_sessions_kind ON setup_sessions(kind);
        """,
    ),
]


def migrate(db: Database) -> None:
    with db.connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        existing = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        for m in MIGRATIONS:
            if m.version in existing:
                continue
            conn.executescript(m.sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES(?, datetime('now'))",
                (m.version,),
            )
