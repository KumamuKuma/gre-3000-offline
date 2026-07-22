from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self, Sequence

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


SEEN_EVENTS_SCHEMA = """
create table if not exists seen_events(
  event_id text primary key,
  word_id integer not null,
  created_at text not null
);
"""


WORD_ANNOTATIONS_SCHEMA = """
create table if not exists word_annotations(
  word_id integer primary key,
  star_rating integer not null check(star_rating between 0 and 5),
  manual_review_count integer not null check(manual_review_count >= 0),
  updated_at text not null
);
"""


LIST_PROGRESS_SCHEMA = """
alter table word_annotations rename to word_annotations_v3;
create table word_annotations(
  word_id integer primary key,
  star_rating integer not null check(star_rating between 0 and 3),
  updated_at text not null
);
insert into word_annotations(word_id, star_rating, updated_at)
select word_id,
       case when star_rating > 3 then 3 else star_rating end,
       updated_at
from word_annotations_v3;
drop table word_annotations_v3;
create table list_progress(
  source_section text primary key,
  completed_count integer not null check(completed_count >= 0),
  updated_at text not null
);
"""


_EXPECTED_SCHEMA = {
    "settings": (
        ("key", "TEXT", 0, None, 1),
        ("value", "TEXT", 1, None, 0),
    ),
    "favorites": (
        ("word_id", "INTEGER", 0, None, 1),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "word_progress": (
        ("word_id", "INTEGER", 0, None, 1),
        ("seen_count", "INTEGER", 1, None, 0),
        ("last_seen_at", "TEXT", 1, None, 0),
    ),
    "session_queue": (
        ("name", "TEXT", 0, None, 1),
        ("word_ids", "TEXT", 1, None, 0),
        ("position", "INTEGER", 1, None, 0),
        ("seed", "INTEGER", 1, None, 0),
    ),
    "seen_events": (
        ("event_id", "TEXT", 0, None, 1),
        ("word_id", "INTEGER", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "word_annotations": (
        ("word_id", "INTEGER", 0, None, 1),
        ("star_rating", "INTEGER", 1, None, 0),
        ("updated_at", "TEXT", 1, None, 0),
    ),
    "list_progress": (
        ("source_section", "TEXT", 0, None, 1),
        ("completed_count", "INTEGER", 1, None, 0),
        ("updated_at", "TEXT", 1, None, 0),
    ),
}


class UserDatabaseError(RuntimeError):
    """Raised when the local user database cannot be opened safely."""


class UserSchemaError(UserDatabaseError, ValueError):
    """Raised for a physically healthy but incompatible user schema."""


class _UserDatabaseCorruptError(UserDatabaseError):
    """Internal marker used only for confirmed physical corruption."""


@dataclass(frozen=True, slots=True)
class PersistenceIssue:
    user_message: str
    technical: str


@dataclass(frozen=True, slots=True)
class QueueState:
    word_ids: tuple[int, ...]
    position: int
    seed: int


@dataclass(frozen=True, slots=True)
class _Mutation:
    kind: str
    values: tuple[Any, ...]


class UserRepository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=0.05)
        self._closed = False
        self._pending: list[_Mutation] = []
        self._last_issue: PersistenceIssue | None = None
        try:
            self.db.execute("pragma busy_timeout=50")
            self._initialize()
            self._load_state()
        except Exception:
            self.db.close()
            raise

    def _initialize(self) -> None:
        check = self.db.execute("pragma quick_check").fetchone()
        if check is None or check[0] != "ok":
            raise _UserDatabaseCorruptError(
                f"user database quick check failed: {check}"
            )

        version = int(self.db.execute("pragma user_version").fetchone()[0])
        if version < 0 or version > USER_SCHEMA_VERSION:
            raise UserSchemaError(
                f"user database version is incompatible: {version}"
            )
        while version < USER_SCHEMA_VERSION:
            if version == 0:
                self._migrate_0_to_1()
            elif version == 1:
                self._migrate_1_to_2()
            elif version == 2:
                self._migrate_2_to_3()
            elif version == 3:
                self._migrate_3_to_4()
            else:  # pragma: no cover - guarded by the version bounds above
                raise UserSchemaError(f"no migration from user schema {version}")
            version += 1
        self._validate_schema()

    def _migrate_0_to_1(self) -> None:
        self._run_migration(USER_SCHEMA, target_version=1)

    def _migrate_1_to_2(self) -> None:
        self._run_migration(SEEN_EVENTS_SCHEMA, target_version=2)

    def _migrate_2_to_3(self) -> None:
        self._run_migration(WORD_ANNOTATIONS_SCHEMA, target_version=3)

    def _migrate_3_to_4(self) -> None:
        self._run_migration(LIST_PROGRESS_SCHEMA, target_version=4)

    def _run_migration(self, script: str, *, target_version: int) -> None:
        try:
            self.db.executescript(
                f"begin immediate;\n{script}\npragma user_version={target_version};\ncommit;"
            )
        except sqlite3.DatabaseError:
            if self.db.in_transaction:
                self.db.rollback()
            raise

    def _validate_schema(self) -> None:
        for table, expected in _EXPECTED_SCHEMA.items():
            rows = self.db.execute(f'pragma table_info("{table}")').fetchall()
            actual = tuple(
                (
                    str(row[1]),
                    str(row[2]).upper(),
                    int(row[3]),
                    row[4],
                    int(row[5]),
                )
                for row in rows
            )
            if actual != expected:
                raise UserSchemaError(
                    f"user database table {table} has invalid shape: "
                    f"expected {expected}, got {actual}"
                )
        row = self.db.execute(
            "select sql from sqlite_master where type='table' "
            "and name='word_annotations'"
        ).fetchone()
        definition = "" if row is None or row[0] is None else str(row[0])
        normalized = re.sub(r"\s+", "", definition.casefold())
        required_constraints = (
            "check(star_ratingbetween0and3)",
        )
        if any(fragment not in normalized for fragment in required_constraints):
            raise UserSchemaError(
                "user database table word_annotations is missing required "
                "rating constraint"
            )
        row = self.db.execute(
            "select sql from sqlite_master where type='table' "
            "and name='list_progress'"
        ).fetchone()
        definition = "" if row is None or row[0] is None else str(row[0])
        normalized = re.sub(r"\s+", "", definition.casefold())
        if "check(completed_count>=0)" not in normalized:
            raise UserSchemaError(
                "user database table list_progress is missing its count constraint"
            )

    @staticmethod
    def _decode_queue(
        name: object, encoded: object, position: object, seed: object
    ) -> tuple[str, QueueState]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("queue name cannot be blank")
        if not isinstance(encoded, str):
            raise ValueError("queue word_ids must be JSON text")
        values = json.loads(encoded)
        if not isinstance(values, list):
            raise ValueError("queue word_ids must be a JSON array")
        if any(type(word_id) is not int or word_id <= 0 for word_id in values):
            raise ValueError("queue word IDs must be positive integers")
        if len(values) != len(set(values)):
            raise ValueError("queue word IDs must be unique")
        if type(position) is not int or type(seed) is not int:
            raise ValueError("queue position and seed must be integers")
        if position < 0 or (values and position >= len(values)):
            raise ValueError("queue position is out of range")
        if not values and position != 0:
            raise ValueError("empty queue position must be zero")
        return name, QueueState(tuple(values), position, seed)

    @classmethod
    def _queue_state(
        cls,
        name: str,
        word_ids: Sequence[int],
        position: int,
        seed: int,
    ) -> tuple[str, QueueState]:
        encoded = json.dumps(list(word_ids), separators=(",", ":"))
        return cls._decode_queue(name, encoded, position, seed)

    def _load_state(self) -> None:
        self._settings = {
            str(row[0]): str(row[1])
            for row in self.db.execute("select key, value from settings")
        }
        self._favorites = {
            int(row[0]): str(row[1])
            for row in self.db.execute("select word_id, created_at from favorites")
        }
        self._seen_counts = {
            int(row[0]): int(row[1])
            for row in self.db.execute(
                "select word_id, seen_count from word_progress"
            )
        }
        self._seen_event_ids = {
            str(row[0]) for row in self.db.execute("select event_id from seen_events")
        }
        self._annotations: dict[int, tuple[int, str]] = {}
        for row in self.db.execute(
            "select word_id, star_rating, updated_at from word_annotations"
        ):
            word_id, star_rating, updated_at = row
            if (
                type(word_id) is not int
                or word_id <= 0
                or type(star_rating) is not int
                or not 0 <= star_rating <= 3
                or not isinstance(updated_at, str)
                or not updated_at.strip()
            ):
                raise UserSchemaError(
                    "word_annotations contains an invalid annotation row"
                )
            self._annotations[word_id] = (star_rating, updated_at)
        self._list_progress: dict[str, tuple[int, str]] = {}
        for row in self.db.execute(
            "select source_section, completed_count, updated_at from list_progress"
        ):
            source_section, completed_count, updated_at = row
            if (
                not isinstance(source_section, str)
                or not source_section.strip()
                or type(completed_count) is not int
                or completed_count < 0
                or not isinstance(updated_at, str)
                or not updated_at.strip()
            ):
                raise UserSchemaError("list_progress contains an invalid row")
            self._list_progress[source_section] = (completed_count, updated_at)
        self._queues: dict[str, QueueState] = {}
        malformed: list[int] = []
        for row in self.db.execute(
            "select rowid, name, word_ids, position, seed from session_queue"
        ):
            try:
                name, state = self._decode_queue(*row[1:])
            except (TypeError, ValueError, json.JSONDecodeError):
                malformed.append(int(row[0]))
            else:
                self._queues[name] = state
        if malformed:
            try:
                with self.db:
                    self.db.executemany(
                        "delete from session_queue where rowid=?",
                        ((rowid,) for rowid in malformed),
                    )
            except sqlite3.DatabaseError as error:
                raise UserDatabaseError(
                    "malformed study queue could not be isolated safely"
                ) from error

    @staticmethod
    def _is_confirmed_corruption(error: BaseException) -> bool:
        current: BaseException | None = error
        while current is not None:
            if isinstance(current, _UserDatabaseCorruptError):
                return True
            if isinstance(current, sqlite3.Error):
                code = getattr(current, "sqlite_errorcode", None)
                if isinstance(code, int) and (code & 0xFF) in {
                    sqlite3.SQLITE_CORRUPT,
                    sqlite3.SQLITE_NOTADB,
                }:
                    return True
            current = current.__cause__
        return False

    @classmethod
    def open_recovering(cls, path: Path) -> UserOpenResult:
        try:
            return UserOpenResult(cls(path), None)
        except Exception as error:
            if isinstance(error, UserSchemaError):
                raise
            if not cls._is_confirmed_corruption(error):
                if isinstance(error, UserDatabaseError):
                    raise
                raise UserDatabaseError(
                    f"user database is temporarily unavailable: {error}"
                ) from error
            if not path.exists():
                raise UserDatabaseError(
                    f"confirmed corrupt user database is missing: {path}"
                ) from error
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

    def close(self) -> bool:
        if self._closed:
            return True
        if not self.flush_pending():
            return False
        try:
            self.db.close()
        except sqlite3.DatabaseError as error:
            self._last_issue = PersistenceIssue(
                "本地数据暂时无法安全关闭；请重试。",
                f"{type(error).__name__}: {error}",
            )
            return False
        self._closed = True
        return True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _annotation_word_id(word_id: object) -> int:
        if type(word_id) is not int or word_id <= 0:
            raise ValueError("word ID must be a positive integer")
        return word_id

    @staticmethod
    def _star_value(star_rating: object) -> int:
        if type(star_rating) is not int or not 0 <= star_rating <= 3:
            raise ValueError("star rating must be an integer from 0 through 3")
        return star_rating

    @staticmethod
    def _source_section_value(source_section: object) -> str:
        if not isinstance(source_section, str) or not source_section.strip():
            raise ValueError("source section cannot be blank")
        return source_section.strip()

    def _apply_seen(self, event_id: str, word_id: int, created_at: str) -> None:
        cursor = self.db.execute(
            "insert or ignore into seen_events(event_id, word_id, created_at) "
            "values(?, ?, ?)",
            (event_id, word_id, created_at),
        )
        if cursor.rowcount:
            self.db.execute(
                """
                insert into word_progress(word_id, seen_count, last_seen_at)
                values(?, 1, ?)
                on conflict(word_id) do update set
                  seen_count=word_progress.seen_count + 1,
                  last_seen_at=excluded.last_seen_at
                """,
                (word_id, created_at),
            )

    def _apply_mutation(self, mutation: _Mutation) -> None:
        kind = mutation.kind
        values = mutation.values
        if kind == "favorite":
            word_id, favorite, created_at = values
            if favorite:
                self.db.execute(
                    "insert into favorites(word_id, created_at) values(?, ?) "
                    "on conflict(word_id) do update set created_at=excluded.created_at",
                    (word_id, created_at),
                )
            else:
                self.db.execute("delete from favorites where word_id=?", (word_id,))
        elif kind == "setting":
            self.db.execute(
                "insert into settings(key, value) values(?, ?) "
                "on conflict(key) do update set value=excluded.value",
                values,
            )
        elif kind == "seen":
            self._apply_seen(*values)
        elif kind == "queue":
            self._write_queue(*values)
        elif kind == "navigation":
            name, encoded, position, seed, event_id, word_id, created_at = values
            self._write_queue(name, encoded, position, seed)
            self._apply_seen(event_id, word_id, created_at)
        elif kind == "annotation":
            self.db.execute(
                """
                insert into word_annotations(word_id, star_rating, updated_at)
                values(?, ?, ?)
                on conflict(word_id) do update set
                  star_rating=excluded.star_rating,
                  updated_at=excluded.updated_at
                """,
                values,
            )
        elif kind == "list_completion":
            self.db.execute(
                """
                insert into list_progress(
                  source_section, completed_count, updated_at
                ) values(?, ?, ?)
                on conflict(source_section) do update set
                  completed_count=excluded.completed_count,
                  updated_at=excluded.updated_at
                """,
                values,
            )
        elif kind == "reset":
            self.db.execute(
                "update session_queue set position=0 where name=?", values
            )
        elif kind == "reset_all":
            self.db.execute("update session_queue set position=0")
        elif kind == "clear":
            for table in (
                "settings",
                "favorites",
                "word_progress",
                "session_queue",
                "seen_events",
                "word_annotations",
                "list_progress",
            ):
                self.db.execute(f"delete from {table}")
        else:  # pragma: no cover - mutations are created internally
            raise AssertionError(f"unknown user mutation: {kind}")

    def _write_queue(
        self, name: str, encoded: str, position: int, seed: int
    ) -> None:
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

    def _enqueue(self, mutation: _Mutation) -> bool:
        self._pending.append(mutation)
        return self.flush_pending()

    def flush_pending(self) -> bool:
        if not self._pending:
            self._last_issue = None
            return True
        if self._closed:
            self._last_issue = PersistenceIssue(
                "本地数据暂时无法保存；操作已保留，将在下次更改时重试。",
                "user database connection is closed",
            )
            return False
        try:
            self.db.execute("begin immediate")
            for mutation in self._pending:
                self._apply_mutation(mutation)
            self.db.commit()
        except sqlite3.DatabaseError as error:
            try:
                if self.db.in_transaction:
                    self.db.rollback()
            except sqlite3.DatabaseError:
                pass
            self._last_issue = PersistenceIssue(
                "本地数据暂时无法保存；操作已保留，将在下次更改时重试。",
                f"{type(error).__name__}: {error}",
            )
            return False
        self._pending.clear()
        self._last_issue = None
        return True

    def discard_pending_writes(self) -> None:
        self._pending.clear()
        self._last_issue = None

    def take_persistence_issue(self) -> PersistenceIssue | None:
        issue = self._last_issue
        self._last_issue = None
        return issue

    @property
    def has_pending_writes(self) -> bool:
        return bool(self._pending)

    @property
    def is_closed(self) -> bool:
        return self._closed

    def set_favorite(self, word_id: int, favorite: bool) -> bool:
        word_id = int(word_id)
        created_at = self._now()
        if favorite:
            self._favorites[word_id] = created_at
        else:
            self._favorites.pop(word_id, None)
        return self._enqueue(
            _Mutation("favorite", (word_id, bool(favorite), created_at))
        )

    def is_favorite(self, word_id: int) -> bool:
        return int(word_id) in self._favorites

    def favorite_ids(self) -> tuple[int, ...]:
        return tuple(
            word_id
            for word_id, _created_at in sorted(
                self._favorites.items(),
                key=lambda item: (item[1], item[0]),
                reverse=True,
            )
        )

    def star_rating(self, word_id: int) -> int:
        word_id = self._annotation_word_id(word_id)
        return self._annotations.get(word_id, (0, ""))[0]

    def _set_annotation(self, word_id: int, star_rating: int) -> bool:
        word_id = self._annotation_word_id(word_id)
        star_rating = self._star_value(star_rating)
        current = self._annotations.get(word_id)
        if current is not None and current[0] == star_rating:
            return self.flush_pending()
        if current is None and star_rating == 0:
            return self.flush_pending()
        updated_at = self._now()
        self._annotations[word_id] = (star_rating, updated_at)
        return self._enqueue(
            _Mutation(
                "annotation",
                (word_id, star_rating, updated_at),
            )
        )

    def set_star_rating(self, word_id: int, star_rating: int) -> bool:
        word_id = self._annotation_word_id(word_id)
        star_rating = self._star_value(star_rating)
        return self._set_annotation(word_id, star_rating)

    def cycle_star_rating(self, word_id: int) -> int:
        word_id = self._annotation_word_id(word_id)
        value = (self.star_rating(word_id) + 1) % 4
        self.set_star_rating(word_id, value)
        return value

    def star_counts(self, word_ids: Sequence[int]) -> dict[int, int]:
        counts = {rating: 0 for rating in range(4)}
        unique_ids: set[int] = set()
        for value in word_ids:
            word_id = self._annotation_word_id(value)
            if word_id in unique_ids:
                continue
            unique_ids.add(word_id)
            counts[self.star_rating(word_id)] += 1
        return counts

    def list_completion_count(self, source_section: str) -> int:
        key = self._source_section_value(source_section)
        return self._list_progress.get(key, (0, ""))[0]

    def list_completion_counts(self) -> dict[str, int]:
        return {
            key: value[0]
            for key, value in self._list_progress.items()
        }

    def set_list_completion_count(
        self, source_section: str, completed_count: int
    ) -> int:
        key = self._source_section_value(source_section)
        if type(completed_count) is not int or completed_count < 0:
            raise ValueError("completed count must be a non-negative integer")
        current = self.list_completion_count(key)
        if current == completed_count:
            self.flush_pending()
            return current
        updated_at = self._now()
        self._list_progress[key] = (completed_count, updated_at)
        self._enqueue(
            _Mutation("list_completion", (key, completed_count, updated_at))
        )
        return completed_count

    def adjust_list_completion(
        self, source_section: str, delta: int
    ) -> int:
        key = self._source_section_value(source_section)
        if type(delta) is not int:
            raise ValueError("completion adjustment must be an integer")
        value = max(0, self.list_completion_count(key) + delta)
        return self.set_list_completion_count(key, value)

    def increment_list_completion(self, source_section: str) -> int:
        return self.adjust_list_completion(source_section, 1)

    def record_seen(self, word_id: int) -> bool:
        return self._record_seen(int(word_id), uuid.uuid4().hex)

    def _record_seen(self, word_id: int, event_id: str) -> bool:
        created_at = self._now()
        if event_id not in self._seen_event_ids:
            self._seen_event_ids.add(event_id)
            self._seen_counts[word_id] = self._seen_counts.get(word_id, 0) + 1
        return self._enqueue(_Mutation("seen", (event_id, word_id, created_at)))

    def seen_word_count(self) -> int:
        return len(self._seen_counts)

    def load_setting(self, key: str) -> str | None:
        return self._settings.get(key)

    def save_setting(self, key: str, value: str) -> bool:
        key = str(key)
        value = str(value)
        self._settings[key] = value
        return self._enqueue(_Mutation("setting", (key, value)))

    def load_queue(self, name: str) -> QueueState:
        return self._queues.get(name, QueueState((), 0, 0))

    def save_queue(
        self,
        name: str,
        word_ids: Sequence[int],
        *,
        position: int,
        seed: int,
    ) -> bool:
        name, state = self._queue_state(name, word_ids, position, seed)
        self._queues[name] = state
        encoded = json.dumps(state.word_ids, separators=(",", ":"))
        return self._enqueue(
            _Mutation("queue", (name, encoded, state.position, state.seed))
        )

    def save_navigation(
        self,
        name: str,
        word_ids: Sequence[int],
        *,
        position: int,
        seed: int,
        seen_word_id: int,
        event_id: str,
    ) -> bool:
        name, state = self._queue_state(name, word_ids, position, seed)
        seen_word_id = int(seen_word_id)
        if seen_word_id <= 0 or seen_word_id not in state.word_ids:
            raise ValueError("seen word must be a positive member of the queue")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("navigation event ID cannot be blank")
        self._queues[name] = state
        if event_id not in self._seen_event_ids:
            self._seen_event_ids.add(event_id)
            self._seen_counts[seen_word_id] = self._seen_counts.get(seen_word_id, 0) + 1
        created_at = self._now()
        encoded = json.dumps(state.word_ids, separators=(",", ":"))
        return self._enqueue(
            _Mutation(
                "navigation",
                (
                    name,
                    encoded,
                    state.position,
                    state.seed,
                    event_id,
                    seen_word_id,
                    created_at,
                ),
            )
        )

    def reset_position(self, name: str) -> bool:
        state = self._queues.get(name)
        if state is not None:
            self._queues[name] = QueueState(state.word_ids, 0, state.seed)
        return self._enqueue(_Mutation("reset", (name,)))

    def reset_all_positions(self) -> bool:
        self._queues = {
            name: QueueState(state.word_ids, 0, state.seed)
            for name, state in self._queues.items()
        }
        return self._enqueue(_Mutation("reset_all", ()))

    def clear_all(self) -> bool:
        self._settings.clear()
        self._favorites.clear()
        self._seen_counts.clear()
        self._seen_event_ids.clear()
        self._queues.clear()
        self._annotations.clear()
        self._list_progress.clear()
        self._pending = [_Mutation("clear", ())]
        return self.flush_pending()


@dataclass(frozen=True, slots=True)
class UserOpenResult:
    repository: UserRepository
    recovered_from: Path | None
