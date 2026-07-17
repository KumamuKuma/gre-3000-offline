from __future__ import annotations

import random
import uuid
from typing import Any, Sequence

from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode


class StudySession:
    def __init__(
        self,
        content_repository: Any,
        user_repository: Any,
        random_source: random.Random,
    ):
        self._content = content_repository
        self._user = user_repository
        self._random = random_source
        self._ids: tuple[int, ...] = ()
        self._position = 0
        self._seed = 0
        self._mode = StudyMode.READING
        self._order = BrowseOrder.SOURCE
        self._answer_visible = False
        self._started = False

    @staticmethod
    def _valid_position(position: int, ids: Sequence[int]) -> bool:
        return bool(ids) and 0 <= position < len(ids)

    @staticmethod
    def _same_id_set(saved_ids: Sequence[int], current_ids: Sequence[int]) -> bool:
        return len(saved_ids) == len(current_ids) and set(saved_ids) == set(current_ids)

    def _fresh_random_queue(
        self, content_ids: tuple[int, ...]
    ) -> tuple[tuple[int, ...], int]:
        seed = self._random.randrange(0, 2**63)
        shuffled = list(content_ids)
        random.Random(seed).shuffle(shuffled)
        return tuple(shuffled), seed

    def _save_navigation(self) -> None:
        self._user.save_navigation(
            self._order.value,
            self._ids,
            position=self._position,
            seed=self._seed,
            seen_word_id=self._ids[self._position],
            event_id=uuid.uuid4().hex,
        )

    def _load_mode(self) -> StudyMode:
        value = self._user.load_setting("study_mode")
        try:
            return StudyMode(value) if value else StudyMode.READING
        except ValueError:
            return StudyMode.READING

    def start(self, order: BrowseOrder) -> SessionSnapshot:
        self._order = BrowseOrder(order)
        self._mode = self._load_mode()
        content_ids = tuple(self._content.ids_in_source_order())
        if not content_ids:
            raise ValueError("content database is empty")
        saved = self._user.load_queue(self._order.value)

        if self._order is BrowseOrder.SOURCE:
            if (
                saved is not None
                and tuple(saved.word_ids) == content_ids
                and self._valid_position(saved.position, content_ids)
            ):
                self._ids = content_ids
                self._position = int(saved.position)
                self._seed = 0
            else:
                self._ids = content_ids
                self._position = 0
                self._seed = 0
        elif (
            saved is not None
            and self._same_id_set(saved.word_ids, content_ids)
            and self._valid_position(saved.position, saved.word_ids)
        ):
            self._ids = tuple(int(word_id) for word_id in saved.word_ids)
            self._position = int(saved.position)
            self._seed = int(saved.seed)
        else:
            self._ids, self._seed = self._fresh_random_queue(content_ids)
            self._position = 0

        self._answer_visible = False
        self._started = True
        self._user.save_setting("browse_order", self._order.value)
        self._save_navigation()
        return self.current()

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("study session has not started")

    def current(self) -> SessionSnapshot:
        self._require_started()
        word = self._content.get(self._ids[self._position])
        return SessionSnapshot(
            word=word,
            index=self._position,
            total=len(self._ids),
            mode=self._mode,
            order=self._order,
            answer_visible=self._answer_visible,
            favorite=bool(self._user.is_favorite(word.id)),
            at_start=self._position == 0,
            at_end=self._position == len(self._ids) - 1,
        )

    def _move(self, position: int) -> SessionSnapshot:
        self._position = position
        self._answer_visible = False
        self._save_navigation()
        return self.current()

    def next(self) -> SessionSnapshot:
        self._require_started()
        if self._position >= len(self._ids) - 1:
            return self.current()
        return self._move(self._position + 1)

    def previous(self) -> SessionSnapshot:
        self._require_started()
        if self._position <= 0:
            return self.current()
        return self._move(self._position - 1)

    def set_mode(self, mode: StudyMode) -> SessionSnapshot:
        self._require_started()
        self._mode = StudyMode(mode)
        self._user.save_setting("study_mode", self._mode.value)
        return self.current()

    def toggle_answer(self) -> SessionSnapshot:
        self._require_started()
        if self._mode is StudyMode.RECALL:
            self._answer_visible = not self._answer_visible
        return self.current()

    def set_favorite(self, favorite: bool) -> SessionSnapshot:
        self._require_started()
        self._user.set_favorite(self._ids[self._position], favorite)
        return self.current()

    def toggle_favorite(self) -> SessionSnapshot:
        return self.set_favorite(not self.current().favorite)

    def reshuffle(self) -> SessionSnapshot:
        self._require_started()
        if self._order is not BrowseOrder.RANDOM:
            raise ValueError("only a random session can be reshuffled")
        content_ids = tuple(self._content.ids_in_source_order())
        self._ids, self._seed = self._fresh_random_queue(content_ids)
        self._position = 0
        self._answer_visible = False
        self._save_navigation()
        return self.current()

