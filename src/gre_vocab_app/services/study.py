from __future__ import annotations

import random
import uuid
from dataclasses import replace
from typing import Any, Sequence

from gre_vocab_app.domain import (
    BrowseOrder,
    SessionSnapshot,
    StudyMode,
    WordEntry,
)


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
        self._queue_name = BrowseOrder.SOURCE.value
        self._star_filter: int | None = None
        self._list_key: str | None = None
        self._list_label = ""
        self._answer_visible = False
        self._quiz_choices: tuple[str, ...] = ()
        self._quiz_correct_index: int | None = None
        self._quiz_selected_index: int | None = None
        self._started = False

    @staticmethod
    def _valid_position(position: int, ids: Sequence[int]) -> bool:
        return bool(ids) and 0 <= position < len(ids)

    @staticmethod
    def _coerce_mode(mode: StudyMode | str) -> StudyMode:
        if mode == "full":
            return StudyMode.READING
        return StudyMode(mode)

    @staticmethod
    def _validate_star_filter(star_rating: object) -> int | None:
        if star_rating is None:
            return None
        if type(star_rating) is not int or not 0 <= star_rating <= 3:
            raise ValueError("star rating filter must be an integer from 0 through 3")
        return star_rating

    @classmethod
    def _position_after_filter_change(
        cls,
        saved: Any,
        current_ids: tuple[int, ...],
        source_ids: tuple[int, ...],
    ) -> int:
        """Keep the saved source-order anchor when a star queue changes.

        A word can leave or enter a filtered queue when its rating is edited.
        If the saved current word left the queue, resume at the next matching
        word in source order; at the end, use the final remaining word.
        """

        if saved is None:
            return 0
        saved_ids = tuple(int(word_id) for word_id in saved.word_ids)
        if not cls._valid_position(saved.position, saved_ids):
            return 0
        source_positions = {
            word_id: position for position, word_id in enumerate(source_ids)
        }
        if any(word_id not in source_positions for word_id in saved_ids):
            return 0
        anchor_id = saved_ids[int(saved.position)]
        if anchor_id in current_ids:
            return current_ids.index(anchor_id)
        anchor_position = source_positions[anchor_id]
        for position, word_id in enumerate(current_ids):
            if source_positions[word_id] > anchor_position:
                return position
        return len(current_ids) - 1

    def _save_navigation(self) -> None:
        self._user.save_navigation(
            self._queue_name,
            self._ids,
            position=self._position,
            seed=self._seed,
            seen_word_id=self._ids[self._position],
            event_id=uuid.uuid4().hex,
        )

    def _load_mode(self) -> StudyMode:
        value = self._user.load_setting("study_mode")
        try:
            return self._coerce_mode(value) if value else StudyMode.READING
        except ValueError:
            return StudyMode.READING

    @staticmethod
    def _definition_text(word: WordEntry, field: str) -> str:
        value = getattr(word, field, "")
        return value.strip() if isinstance(value, str) else ""

    def _quiz_for_word(
        self, word: WordEntry
    ) -> tuple[tuple[str, ...], int]:
        correct = self._definition_text(word, "definition_zh")
        if not correct:
            correct = self._definition_text(word, "definition_en")
        if not correct:
            raise ValueError("quiz word has no usable definition")

        other_words = [
            self._content.get(word_id)
            for word_id in self._content.ids_in_source_order()
            if word_id != word.id
        ]
        if len(other_words) < 3:
            raise ValueError("quiz requires at least four vocabulary entries")

        def candidates(field: str) -> list[tuple[str, int]]:
            result: list[tuple[str, int]] = []
            seen = {correct}
            for candidate_word in other_words:
                text = self._definition_text(candidate_word, field)
                if not text or text in seen:
                    continue
                seen.add(text)
                result.append((text, candidate_word.id))
            self._random.shuffle(result)
            return result

        selected: list[tuple[str, int]] = []
        selected_ids: set[int] = set()
        for text, word_id in candidates("definition_zh"):
            selected.append((text, word_id))
            selected_ids.add(word_id)
            if len(selected) == 3:
                break

        if len(selected) < 3:
            used_text = {correct, *(text for text, _word_id in selected)}
            english = candidates("definition_en")
            for allow_reused_word in (False, True):
                for text, word_id in english:
                    if text in used_text:
                        continue
                    if not allow_reused_word and word_id in selected_ids:
                        continue
                    selected.append((text, word_id))
                    selected_ids.add(word_id)
                    used_text.add(text)
                    if len(selected) == 3:
                        break
                if len(selected) == 3:
                    break

        if len(selected) != 3:
            raise ValueError("quiz requires four distinct definition choices")

        choices = [text for text, _word_id in selected]
        choices.append(correct)
        self._random.shuffle(choices)
        result = tuple(choices)
        return result, result.index(correct)

    def _prepare_quiz(self) -> None:
        self._quiz_choices = ()
        self._quiz_correct_index = None
        self._quiz_selected_index = None
        if self._mode is StudyMode.QUIZ:
            word = self._content.get(self._ids[self._position])
            (
                self._quiz_choices,
                self._quiz_correct_index,
            ) = self._quiz_for_word(word)

    def start(
        self,
        order: BrowseOrder = BrowseOrder.SOURCE,
        *,
        source_section: str,
        star_rating: int | None = None,
    ) -> SessionSnapshot:
        try:
            parsed_order = BrowseOrder(order)
        except (TypeError, ValueError) as error:
            raise ValueError("only source-order study is supported") from error
        if parsed_order is not BrowseOrder.SOURCE:  # pragma: no cover - one-value enum
            raise ValueError("only source-order study is supported")

        star_filter = self._validate_star_filter(star_rating)
        if not isinstance(source_section, str) or not source_section.strip():
            raise ValueError("source section cannot be blank")
        source_section = source_section.strip()
        try:
            source_list = self._content.source_list(source_section)
            content_ids = tuple(self._content.ids_for_section(source_section))
        except KeyError as error:
            raise ValueError(f"unknown source section: {source_section}") from error
        if not content_ids:
            raise ValueError(f"source section is empty: {source_section}")
        if star_filter is None:
            ids = content_ids
            queue_name = f"source:list:{source_section}:all"
            filter_setting = "all"
        else:
            ids = tuple(
                word_id
                for word_id in content_ids
                if self._user.star_rating(word_id) == star_filter
            )
            queue_name = f"source:list:{source_section}:star:{star_filter}"
            filter_setting = f"star:{star_filter}"
        if not ids:
            raise ValueError(f"no words match star rating {star_filter}")

        saved = self._user.load_queue(queue_name)
        if (
            saved is not None
            and tuple(saved.word_ids) == ids
            and self._valid_position(saved.position, ids)
        ):
            position = int(saved.position)
        elif star_filter is not None:
            position = self._position_after_filter_change(
                saved,
                ids,
                content_ids,
            )
        else:
            position = 0

        self._order = parsed_order
        self._mode = self._load_mode()
        self._ids = ids
        self._position = position
        self._seed = 0
        self._queue_name = queue_name
        self._star_filter = star_filter
        self._list_key = source_section
        self._list_label = str(source_list.label)
        self._answer_visible = False
        self._started = True
        self._user.save_setting("browse_order", self._order.value)
        self._user.save_setting("study_list", source_section)
        self._user.save_setting("study_filter", filter_setting)
        self._prepare_quiz()
        self._save_navigation()
        return self.current()

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("study session has not started")

    def _snapshot(
        self,
        word: WordEntry,
        *,
        index: int,
        total: int,
        at_start: bool,
        at_end: bool,
        mode: StudyMode,
        answer_visible: bool,
        star_filter: int | None,
        quiz_choices: tuple[str, ...] = (),
        quiz_correct_index: int | None = None,
        quiz_selected_index: int | None = None,
        list_key: str | None = None,
        list_label: str = "",
    ) -> SessionSnapshot:
        root_lookup = getattr(self._content, "root_families", None)
        lookalike_lookup = getattr(self._content, "lookalikes", None)
        equivalent_lookup = getattr(self._content, "equivalents", None)
        machine7_lookup = getattr(self._content, "in_machine7", None)
        root_families = (
            tuple(root_lookup(word.id)) if callable(root_lookup) else ()
        )
        lookalikes = (
            tuple(lookalike_lookup(word.id))
            if callable(lookalike_lookup)
            else ()
        )
        equivalents = (
            tuple(equivalent_lookup(word.id))
            if callable(equivalent_lookup)
            else ()
        )
        in_machine7 = (
            bool(machine7_lookup(word.id))
            if callable(machine7_lookup)
            else False
        )
        return SessionSnapshot(
            word=word,
            index=index,
            total=total,
            mode=mode,
            order=BrowseOrder.SOURCE,
            answer_visible=answer_visible,
            at_start=at_start,
            at_end=at_end,
            star_rating=int(self._user.star_rating(word.id)),
            star_filter=star_filter,
            list_key=list_key,
            list_label=list_label,
            can_complete_round=(
                list_key is not None and star_filter is None and at_end
            ),
            root_families=root_families,
            lookalikes=lookalikes,
            equivalents=equivalents,
            in_machine7=in_machine7,
            quiz_choices=quiz_choices,
            quiz_correct_index=quiz_correct_index,
            quiz_selected_index=quiz_selected_index,
        )

    def current(self) -> SessionSnapshot:
        self._require_started()
        word = self._content.get(self._ids[self._position])
        return self._snapshot(
            word,
            index=self._position,
            total=len(self._ids),
            at_start=self._position == 0,
            at_end=self._position == len(self._ids) - 1,
            mode=self._mode,
            answer_visible=self._answer_visible,
            star_filter=self._star_filter,
            quiz_choices=self._quiz_choices,
            quiz_correct_index=self._quiz_correct_index,
            quiz_selected_index=self._quiz_selected_index,
            list_key=self._list_key,
            list_label=self._list_label,
        )

    def detail_snapshot(
        self, word: WordEntry, mode: StudyMode | str
    ) -> SessionSnapshot:
        parsed_mode = self._coerce_mode(mode)
        choices: tuple[str, ...] = ()
        correct_index: int | None = None
        if parsed_mode is StudyMode.QUIZ:
            choices, correct_index = self._quiz_for_word(word)
        return self._snapshot(
            word,
            index=0,
            total=1,
            at_start=True,
            at_end=True,
            mode=parsed_mode,
            answer_visible=False,
            star_filter=None,
            quiz_choices=choices,
            quiz_correct_index=correct_index,
            list_key=None,
            list_label="",
        )

    @staticmethod
    def answer_detail_quiz(
        snapshot: SessionSnapshot, index: int
    ) -> SessionSnapshot:
        if snapshot.mode is not StudyMode.QUIZ:
            raise ValueError("detail snapshot is not in quiz mode")
        if type(index) is not int or not 0 <= index < len(snapshot.quiz_choices):
            raise ValueError("quiz choice index is out of range")
        if snapshot.quiz_selected_index is not None:
            return snapshot
        return replace(snapshot, quiz_selected_index=index)

    def _move(self, position: int) -> SessionSnapshot:
        self._position = position
        self._answer_visible = False
        self._prepare_quiz()
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

    def set_mode(self, mode: StudyMode | str) -> SessionSnapshot:
        self._require_started()
        parsed_mode = self._coerce_mode(mode)
        if parsed_mode is self._mode:
            return self.current()
        previous_mode = self._mode
        self._mode = parsed_mode
        try:
            self._prepare_quiz()
        except Exception:
            self._mode = previous_mode
            self._prepare_quiz()
            raise
        self._user.save_setting("study_mode", self._mode.value)
        return self.current()

    def toggle_answer(self) -> SessionSnapshot:
        self._require_started()
        if self._mode is StudyMode.RECALL:
            self._answer_visible = not self._answer_visible
        return self.current()

    def answer_quiz(self, index: int) -> SessionSnapshot:
        self._require_started()
        if self._mode is not StudyMode.QUIZ:
            raise ValueError("study session is not in quiz mode")
        if type(index) is not int or not 0 <= index < len(self._quiz_choices):
            raise ValueError("quiz choice index is out of range")
        if self._quiz_selected_index is not None:
            return self.current()
        self._quiz_selected_index = index
        return self.current()

    def set_star_rating(self, star_rating: int) -> SessionSnapshot:
        self._require_started()
        self._user.set_star_rating(self._ids[self._position], star_rating)
        return self.current()

    def cycle_star_rating(self) -> SessionSnapshot:
        self._require_started()
        self._user.cycle_star_rating(self._ids[self._position])
        return self.current()

    def complete_round(self) -> int:
        self._require_started()
        if self._list_key is None or self._star_filter is not None:
            raise RuntimeError("only a complete unfiltered List can be finished")
        if self._position != len(self._ids) - 1:
            raise RuntimeError("the current List has not reached its final word")
        count = int(self._user.increment_list_completion(self._list_key))
        self._user.reset_position(self._queue_name)
        self._position = 0
        return count
