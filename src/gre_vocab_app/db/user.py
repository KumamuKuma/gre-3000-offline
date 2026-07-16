from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Self, Sequence

from .schema import USER_SCHEMA_VERSION


USER_SCHEMA = """
create table if not exists settings(
  key text primary key,
  value text not null
);
create table if not exists favorites(
  word_id integer primary key,
  created_at text not null
);
create table if not exists word_progress(
  word_id integer primary key,
  seen_count integer not null,
  last_seen_at text not null
);
create table if not exists session_queue(
  name text primary key,
  word_ids text not null,
  position integer not null,
  seed integer not null
);
"""


@dataclass(frozen=True, slots=True)
class QueueState:
    word_ids: tuple[int, ...]
    position: int
    seed: int


class UserRepository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        try:
            self._initialize()
        except Exception:
            self.db.close()
            raise

    def _initialize(self) -> None:
        check = self.db.execute("pragma quick_check").fetchone()
        if check is None or check[0] != "ok":
            raise sqlite3.DatabaseError(f"user database quick check failed: {check}")
        version = int(self.db.execute("pragma user_version").fetchone()[0])
        if version not in (0, USER_SCHEMA_VERSION):
            raise ValueError("user database version is incompatible")
        version_statement = (
            f"pragma user_version={USER_SCHEMA_VERSION};" if version == 0 else ""
        )
        try:
            self.db.executescript(
                f"begin immediate;\n{USER_SCHEMA}\n{version_statement}\ncommit;"
            )
        except sqlite3.DatabaseError:
            if self.db.in_transaction:
                self.db.rollback()
            raise

    @classmethod
    def open_recovering(cls, path: Path) -> UserOpenResult:
        try:
            return UserOpenResult(cls(path), None)
        except sqlite3.DatabaseError:
            if not path.exists():
                raise
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = path.with_name(f"{path.name}.corrupt-{timestamp}")
            suffix = 1
            while backup.exists():
                backup = path.with_name(
                    f"{path.name}.corrupt-{timestamp}-{suffix}"
                )
                suffix += 1
            path.replace(backup)
            return UserOpenResult(cls(path), backup)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def set_favorite(self, word_id: int, favorite: bool) -> None:
        with self.db:
            if favorite:
                self.db.execute(
                    "insert into favorites(word_id, created_at) values(?, ?) "
                    "on conflict(word_id) do nothing",
                    (word_id, self._now()),
                )
            else:
                self.db.execute("delete from favorites where word_id=?", (word_id,))

    def is_favorite(self, word_id: int) -> bool:
        return (
            self.db.execute(
                "select 1 from favorites where word_id=?", (word_id,)
            ).fetchone()
            is not None
        )

    def favorite_ids(self) -> tuple[int, ...]:
        rows = self.db.execute(
            "select word_id from favorites order by created_at desc, rowid desc"
        ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def record_seen(self, word_id: int) -> None:
        with self.db:
            self.db.execute(
                """
                insert into word_progress(word_id, seen_count, last_seen_at)
                values(?, 1, ?)
                on conflict(word_id) do update set
                  seen_count=word_progress.seen_count + 1,
                  last_seen_at=excluded.last_seen_at
                """,
                (word_id, self._now()),
            )

    def seen_word_count(self) -> int:
        return int(
            self.db.execute("select count(*) from word_progress").fetchone()[0]
        )

    def load_setting(self, key: str) -> str | None:
        row = self.db.execute(
            "select value from settings where key=?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    def save_setting(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute(
                "insert into settings(key, value) values(?, ?) "
                "on conflict(key) do update set value=excluded.value",
                (key, value),
            )

    def load_queue(self, name: str) -> QueueState:
        row = self.db.execute(
            "select word_ids, position, seed from session_queue where name=?",
            (name,),
        ).fetchone()
        if row is None:
            return QueueState((), 0, 0)
        return QueueState(
            tuple(int(word_id) for word_id in json.loads(row[0])),
            int(row[1]),
            int(row[2]),
        )

    def save_queue(
        self,
        name: str,
        word_ids: Sequence[int],
        *,
        position: int,
        seed: int,
    ) -> None:
        values = tuple(int(word_id) for word_id in word_ids)
        if not name.strip():
            raise ValueError("queue name cannot be blank")
        if position < 0 or (values and position >= len(values)):
            raise ValueError("queue position is out of range")
        if not values and position != 0:
            raise ValueError("empty queue position must be zero")
        encoded = json.dumps(values, separators=(",", ":"))
        with self.db:
            self.db.execute(
                """
                insert into session_queue(name, word_ids, position, seed)
                values(?, ?, ?, ?)
                on conflict(name) do update set
                  word_ids=excluded.word_ids,
                  position=excluded.position,
                  seed=excluded.seed
                """,
                (name, encoded, position, seed),
            )

    def reset_position(self, name: str) -> None:
        with self.db:
            self.db.execute(
                "update session_queue set position=0 where name=?", (name,)
            )

    def clear_all(self) -> None:
        with self.db:
            for table in ("settings", "favorites", "word_progress", "session_queue"):
                self.db.execute(f"delete from {table}")


@dataclass(frozen=True, slots=True)
class UserOpenResult:
    repository: UserRepository
    recovered_from: Path | None
