# GRE 3000 词离线桌面应用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 从用户提供的 GRE 词表 PDF 构建一个完全离线、支持双模式连续学习、搜索、生词本、进度恢复和 Windows 英文朗读的单文件 Windows EXE。

**Architecture:** 构建阶段用 PyMuPDF 按版面坐标解析 PDF，经过规范化、覆盖修正和审计后生成只读 words.db；运行阶段用 PySide6 展示界面，通过独立的仓储、学习会话、用户状态和语音服务访问只读内容库及可写 user.db。最终使用 pyside6-deploy/Nuitka 打包，词库嵌入 EXE，用户数据写入 Windows 标准应用数据目录。

**Tech Stack:** Python 3.12、PySide6 6.x、PyMuPDF 1.x、SQLite、pytest、pytest-qt、pyside6-deploy/Nuitka、PowerShell。

## Global Constraints

- 仅支持 Windows 10/11 x64。
- 最终交付为可双击运行、无控制台窗口、不要求管理员权限的单文件 EXE。
- 不使用网络、微信、账号、遥测、云同步或原 PDF 运行时依赖。
- PDF 每条词表记录都必须进入最终词库；自动解析失败项必须人工覆盖修正，禁止静默丢弃。
- 阅读与回忆模式共享当前词、收藏和浏览位置；切换模式不跳词。
- 连续学习无每日目标；同时支持 PDF 源顺序和持久化无重复随机队列。
- Windows 英文语音不可用时降级为无朗读，不阻塞其他功能。
- 用户进度保存在 Windows 用户应用数据目录，替换 EXE 不得覆盖。
- 不复制原小程序的商标、二维码、广告、课程或下载入口。
- 词库数据库、审计报告和最终 EXE 是本地生成物，不提交包含完整派生词库的文件到 Git。

---

## File Map

- pyproject.toml：项目元数据、运行与测试依赖、pytest 配置。
- .gitignore：忽略虚拟环境、缓存、视觉草图、构建产物和完整派生词库。
- main.py：桌面应用入口。
- src/gre_vocab_app/domain.py：不可变领域模型和枚举。
- src/gre_vocab_app/paths.py：内容库、用户库、日志和资源路径解析。
- src/gre_vocab_app/importer/types.py：版面 span、原始行、规范化草稿类型。
- src/gre_vocab_app/importer/layout.py：PyMuPDF span 提取、列分配和行恢复。
- src/gre_vocab_app/importer/normalize.py：中英文拆分、空白修复和质量标记。
- src/gre_vocab_app/importer/build.py：完整 PDF 导入、覆盖修正和 SQLite 生成 CLI。
- src/gre_vocab_app/importer/audit.py：审计 JSON 和 HTML 报告。
- src/gre_vocab_app/importer/overrides.json：以页码和词头为键的可重复人工修正。
- src/gre_vocab_app/db/schema.py：内容库和用户库 schema/version。
- src/gre_vocab_app/db/content.py：只读词库查询仓储。
- src/gre_vocab_app/db/user.py：进度、设置、收藏和随机队列仓储。
- src/gre_vocab_app/services/study.py：顺序/随机学习会话和阅读/回忆状态。
- src/gre_vocab_app/services/speech.py：Qt TextToSpeech 适配器。
- src/gre_vocab_app/services/search.py：大小写不敏感的前缀/包含搜索。
- src/gre_vocab_app/ui/theme.py：绿色桌面主题 QSS。
- src/gre_vocab_app/ui/word_detail.py：共享词条详情控件。
- src/gre_vocab_app/ui/home_page.py：首页、搜索结果和入口信号。
- src/gre_vocab_app/ui/study_page.py：阅读/回忆双模式学习页和快捷键。
- src/gre_vocab_app/ui/favorites_page.py：生词本。
- src/gre_vocab_app/ui/settings_dialog.py：模式、语音、语速和数据重置设置。
- src/gre_vocab_app/ui/main_window.py：页面栈和窗口状态。
- src/gre_vocab_app/controller.py：连接 UI、仓储和服务。
- src/gre_vocab_app/bootstrap.py：数据库校验、用户库恢复、日志和启动错误。
- resources/app.svg、resources/app.ico：独立的通用书本图标。
- scripts/build_release.ps1：测试、导入、打包和 outputs 复制。
- tests/：与上述边界一一对应的单元、Qt 组件和冒烟测试。

### Task 1: Project foundation, domain types, and path policy

**Files:**
- Create: .gitignore
- Create: pyproject.toml
- Create: src/gre_vocab_app/__init__.py
- Create: src/gre_vocab_app/domain.py
- Create: src/gre_vocab_app/paths.py
- Create: tests/conftest.py
- Test: tests/test_domain.py
- Test: tests/test_paths.py

**Interfaces:**
- Produces: StudyMode, BrowseOrder, WordEntry, SessionSnapshot, AppPaths.resolve(content_override, user_root).
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing domain and path tests**

~~~python
# tests/test_domain.py
from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry

def test_word_entry_is_immutable_and_preserves_quality_flags():
    word = WordEntry(
        id=7, source_order=4, source_section="list1", source_page=5,
        headword="abate", phonetic="[əˈbeɪt]",
        definition_en="v. to become weaker", definition_zh="减弱",
        synonyms="mitigate", example_en="The pain began to abate.",
        example_zh="疼痛开始减轻。", raw_definition="v. to become weaker 减弱",
        raw_example="The pain began to abate. 疼痛开始减轻。",
        quality_flags=("reviewed_split",),
    )
    assert word.headword == "abate"
    assert word.quality_flags == ("reviewed_split",)
    assert StudyMode.READING.value == "reading"
    assert BrowseOrder.RANDOM.value == "random"
~~~

~~~python
# tests/test_paths.py
from pathlib import Path
from gre_vocab_app.paths import AppPaths

def test_app_paths_keep_content_read_only_and_user_data_separate(tmp_path: Path):
    content = tmp_path / "bundle" / "words.db"
    user_root = tmp_path / "profile"
    paths = AppPaths.resolve(content_override=content, user_root=user_root)
    assert paths.content_db == content
    assert paths.user_db == user_root / "user.db"
    assert paths.log_file == user_root / "logs" / "app.log"
~~~

- [ ] **Step 2: Run tests and verify the import failure**

Run: python -m pytest tests/test_domain.py tests/test_paths.py -v

Expected: collection fails with ModuleNotFoundError for gre_vocab_app.

- [ ] **Step 3: Add project configuration and minimal domain implementation**

~~~toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gre-vocab-offline"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "PySide6>=6.8,<7",
  "PyMuPDF>=1.24,<2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<10",
  "pytest-qt>=4.4,<5",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
qt_api = "pyside6"
~~~

~~~python
# src/gre_vocab_app/domain.py
from dataclasses import dataclass
from enum import StrEnum

class StudyMode(StrEnum):
    READING = "reading"
    RECALL = "recall"

class BrowseOrder(StrEnum):
    SOURCE = "source"
    RANDOM = "random"

@dataclass(frozen=True, slots=True)
class WordEntry:
    id: int
    source_order: int
    source_section: str
    source_page: int
    headword: str
    phonetic: str
    definition_en: str
    definition_zh: str
    synonyms: str
    example_en: str
    example_zh: str
    raw_definition: str
    raw_example: str
    quality_flags: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    word: WordEntry
    index: int
    total: int
    mode: StudyMode
    order: BrowseOrder
    answer_visible: bool
    favorite: bool
    at_start: bool
    at_end: bool
~~~

~~~python
# tests/conftest.py
import pytest
from gre_vocab_app.domain import WordEntry

@pytest.fixture
def sample_word():
    return WordEntry(
        id=1, source_order=1, source_section="list1", source_page=5,
        headword="inevitable", phonetic="[ɪnˈevɪtəbl]",
        definition_en="adj. sure to happen", definition_zh="必然的",
        synonyms="unavoidable, preordained, ineluctable",
        example_en="It was inevitable.", example_zh="这是不可避免的。",
        raw_definition="adj. sure to happen 必然的",
        raw_example="It was inevitable. 这是不可避免的。",
    )
~~~

~~~python
# src/gre_vocab_app/paths.py
import os
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QStandardPaths

PACKAGE_ROOT = Path(__file__).resolve().parent

@dataclass(frozen=True, slots=True)
class AppPaths:
    content_db: Path
    user_db: Path
    log_file: Path

    @classmethod
    def resolve(cls, content_override: Path | None = None,
                user_root: Path | None = None) -> "AppPaths":
        content_env = os.environ.get("GRE_WORDS_DB")
        user_env = os.environ.get("GRE_APP_DATA_ROOT")
        content = content_override or (
            Path(content_env) if content_env else PACKAGE_ROOT / "data" / "words.db"
        )
        root = user_root or (
            Path(user_env) if user_env else Path(
                QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            )
        )
        return cls(content, root / "user.db", root / "logs" / "app.log")
~~~

- [ ] **Step 4: Install editable dependencies and run tests**

Run: python -m pip install -e ".[dev]"

Run: python -m pytest tests/test_domain.py tests/test_paths.py -v

Expected: 2 passed.

- [ ] **Step 5: Add ignores and commit**

~~~gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.superpowers/
work/
build/
dist/
outputs/*.exe
outputs/*.html
src/gre_vocab_app/data/words.db
*.log
~~~

Run: git add .gitignore pyproject.toml src tests/test_domain.py tests/test_paths.py

Run: git commit -m "chore: establish GRE desktop app domain"

### Task 2: Geometry-based PDF row extraction

**Files:**
- Create: src/gre_vocab_app/importer/__init__.py
- Create: src/gre_vocab_app/importer/types.py
- Create: src/gre_vocab_app/importer/layout.py
- Test: tests/importer/test_layout.py

**Interfaces:**
- Consumes: no runtime interfaces.
- Produces: TextSpan, RawWordRow, ParserState, extract_page_spans(page), group_spans_into_rows(spans, page_number, state).

- [ ] **Step 1: Write a failing synthetic geometry test**

~~~python
from gre_vocab_app.importer.layout import group_spans_into_rows
from gre_vocab_app.importer.types import ParserState, TextSpan

def span(x, y, text, size=10):
    return TextSpan(x0=x, y0=y, x1=x + 60, y1=y + 11, text=text, size=size)

def test_groups_five_columns_and_updates_mid_page_section():
    spans = [
        span(19, 48, "张巍GRE镇考3000词-乱序版 list1"),
        span(19, 70, "querulous"), span(100, 70, "['kwɛrələs]"),
        span(188, 70, "adj. habitually complaining"), span(188, 82, "抱怨的"),
        span(384, 70, "One gets unsettled."), span(384, 82, "人会心绪不宁。"),
        span(19, 108, "rote"), span(100, 108, "[roʊt]"),
        span(188, 108, "n. mechanical repetition"), span(188, 120, "死记硬背"),
    ]
    rows, state = group_spans_into_rows(
        spans, page_number=5, state=ParserState(next_order=1, section="unknown")
    )
    assert [row.columns[0] for row in rows] == ["querulous", "rote"]
    assert rows[0].columns[2] == "adj. habitually complaining\n抱怨的"
    assert rows[0].source_section == "list1"
    assert rows[1].source_order == 2
    assert state.next_order == 3
~~~

- [ ] **Step 2: Run the focused test**

Run: python -m pytest tests/importer/test_layout.py -v

Expected: collection fails because importer modules do not exist.

- [ ] **Step 3: Implement span extraction and row grouping**

~~~python
# src/gre_vocab_app/importer/types.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TextSpan:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float

@dataclass(frozen=True, slots=True)
class RawWordRow:
    source_page: int
    source_order: int
    source_section: str
    columns: tuple[str, str, str, str, str]
    flags: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class ParserState:
    next_order: int
    section: str
~~~

~~~python
# src/gre_vocab_app/importer/layout.py
import re
from collections import defaultdict
from typing import Iterable
from .types import ParserState, RawWordRow, TextSpan

COLUMN_BOUNDS = (0.0, 95.0, 180.0, 315.0, 380.0, 596.0)
HEADWORD = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
SECTION = re.compile(r"(补充重点单词\s*)?list\s*(\d+)", re.I)

def extract_page_spans(page) -> list[TextSpan]:
    result: list[TextSpan] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for item in line.get("spans", []):
                text = item["text"].strip()
                if text:
                    x0, y0, x1, y1 = item["bbox"]
                    result.append(TextSpan(x0, y0, x1, y1, text, item["size"]))
    return result

def _column(x0: float) -> int | None:
    for index in range(5):
        if COLUMN_BOUNDS[index] <= x0 < COLUMN_BOUNDS[index + 1]:
            return index
    return None

def _join_cell(spans: Iterable[TextSpan]) -> str:
    lines: dict[float, list[TextSpan]] = defaultdict(list)
    for item in spans:
        lines[round(item.y0, 1)].append(item)
    rendered = []
    for y in sorted(lines):
        rendered.append(" ".join(x.text for x in sorted(lines[y], key=lambda s: s.x0)))
    return "\n".join(rendered).strip()

def group_spans_into_rows(spans: list[TextSpan], page_number: int,
                          state: ParserState) -> tuple[list[RawWordRow], ParserState]:
    usable = [s for s in spans if 38 <= s.y0 <= 810 and s.size <= 25]
    events = sorted(
        ((s.y0, SECTION.search(s.text)) for s in usable if s.x0 < 180),
        key=lambda item: item[0],
    )
    section_events = [
        (y, ("supplement-" if match.group(1) else "list") + match.group(2))
        for y, match in events if match
    ]
    anchors = sorted(
        [s for s in usable if s.x0 < 95 and HEADWORD.fullmatch(s.text)],
        key=lambda s: s.y0,
    )
    rows: list[RawWordRow] = []
    current_section = state.section
    next_order = state.next_order
    for index, anchor in enumerate(anchors):
        for event_y, event_section in section_events:
            if event_y <= anchor.y0:
                current_section = event_section
        end_y = anchors[index + 1].y0 if index + 1 < len(anchors) else 810
        buckets: list[list[TextSpan]] = [[] for _ in range(5)]
        for item in usable:
            center_y = (item.y0 + item.y1) / 2
            column = _column(item.x0)
            if column is not None and anchor.y0 <= center_y < end_y:
                buckets[column].append(item)
        columns = tuple(_join_cell(bucket) for bucket in buckets)
        flags = ("missing_phonetic",) if not columns[1] else ()
        rows.append(RawWordRow(
            source_page=page_number, source_order=next_order,
            source_section=current_section, columns=columns, flags=flags,
        ))
        next_order += 1
    return rows, ParserState(next_order=next_order, section=current_section)
~~~

- [ ] **Step 4: Run extraction tests**

Run: python -m pytest tests/importer/test_layout.py -v

Expected: 1 passed.

- [ ] **Step 5: Add real-page bounded smoke test and commit**

~~~python
import os
import fitz
import pytest
from gre_vocab_app.importer.layout import extract_page_spans, group_spans_into_rows
from gre_vocab_app.importer.types import ParserState

@pytest.mark.parametrize("page_index", [4, 143, 287])
def test_real_pdf_sample_pages_have_five_column_rows(page_index):
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")
    with fitz.open(source) as document:
        spans = extract_page_spans(document[page_index])
    rows, _ = group_spans_into_rows(
        spans,
        page_number=page_index + 1,
        state=ParserState(next_order=1, section="sample"),
    )
    assert rows
    assert all(len(row.columns) == 5 for row in rows)
    assert all(row.columns[0] for row in rows)
~~~

Run: GRE_SOURCE_PDF="D:/桌面/LGU/GRE/张巍GRE镇考3000词-乱序（2026年）.pdf" python -m pytest tests/importer/test_layout.py -v

Expected: synthetic and three-page smoke tests pass.

Run: git add src/gre_vocab_app/importer tests/importer/test_layout.py

Run: git commit -m "feat: extract vocabulary rows by PDF geometry"

### Task 3: Row normalization and quality flags

**Files:**
- Create: src/gre_vocab_app/importer/normalize.py
- Test: tests/importer/test_normalize.py

**Interfaces:**
- Consumes: RawWordRow from Task 2.
- Produces: WordDraft and normalize_row(row) -> WordDraft.

- [ ] **Step 1: Write failing normalization tests**

~~~python
from gre_vocab_app.importer.normalize import normalize_row, split_bilingual
from gre_vocab_app.importer.types import RawWordRow

def test_split_bilingual_uses_first_cjk_character():
    assert split_bilingual("adj. sure to happen 必然的") == (
        "adj. sure to happen", "必然的"
    )

def test_normalize_row_preserves_raw_text_and_flags_missing_translation():
    row = RawWordRow(
        source_page=144, source_order=1400, source_section="list16",
        columns=(
            "halcyon", "['hælsɪən]", "n. calm, peaceful\n宁静的，太平的", "",
            "I savor the halcyon times.\n我享受这段太平时光。",
        ),
    )
    draft = normalize_row(row)
    assert draft.headword == "halcyon"
    assert draft.definition_en == "n. calm, peaceful"
    assert draft.definition_zh == "宁静的，太平的"
    assert draft.example_zh == "我享受这段太平时光。"
    assert draft.quality_flags == ()
~~~

- [ ] **Step 2: Verify tests fail**

Run: python -m pytest tests/importer/test_normalize.py -v

Expected: collection fails because normalize.py does not exist.

- [ ] **Step 3: Implement deterministic normalization**

~~~python
# src/gre_vocab_app/importer/normalize.py
import re
from dataclasses import dataclass
from .types import RawWordRow

CJK = re.compile(r"[\u3400-\u9fff]")
SPACE = re.compile(r"[ \t]+")

@dataclass(frozen=True, slots=True)
class WordDraft:
    source_order: int
    source_section: str
    source_page: int
    headword: str
    phonetic: str
    definition_en: str
    definition_zh: str
    synonyms: str
    example_en: str
    example_zh: str
    raw_definition: str
    raw_example: str
    quality_flags: tuple[str, ...]

def clean(text: str) -> str:
    return "\n".join(
        SPACE.sub(" ", line).strip() for line in text.splitlines() if line.strip()
    )

def split_bilingual(text: str) -> tuple[str, str]:
    value = clean(text).replace("\n", " ")
    match = CJK.search(value)
    if not match:
        return value.strip(), ""
    return value[:match.start()].strip(), value[match.start():].strip()

def normalize_row(row: RawWordRow) -> WordDraft:
    headword, phonetic, raw_definition, synonyms, raw_example = row.columns
    definition_en, definition_zh = split_bilingual(raw_definition)
    example_en, example_zh = split_bilingual(raw_example)
    flags = set(row.flags)
    if not headword.strip():
        flags.add("missing_headword")
    if not phonetic.strip():
        flags.add("missing_phonetic")
    if not definition_en or not definition_zh:
        flags.add("incomplete_definition")
    if raw_example and (not example_en or not example_zh):
        flags.add("incomplete_example")
    return WordDraft(
        source_order=row.source_order,
        source_section=row.source_section,
        source_page=row.source_page,
        headword=clean(headword).replace("\n", " "),
        phonetic=clean(phonetic).replace("\n", ""),
        definition_en=definition_en,
        definition_zh=definition_zh,
        synonyms=clean(synonyms).replace("\n", " "),
        example_en=example_en,
        example_zh=example_zh,
        raw_definition=clean(raw_definition),
        raw_example=clean(raw_example),
        quality_flags=tuple(sorted(flags)),
    )
~~~

- [ ] **Step 4: Add edge tests and pass the suite**

~~~python
def test_numbered_phrase_sense_and_missing_translation_flags():
    row = RawWordRow(
        source_page=288, source_order=3001, source_section="supplement-2",
        columns=(
            "per se", "[ˌpɜːr ˈseɪ]",
            "①phrase. by itself 本质上\n②phrase. intrinsically 内在地",
            "", "It is not wrong per se.",
        ),
    )
    draft = normalize_row(row)
    assert draft.headword == "per se"
    assert draft.synonyms == ""
    assert draft.phonetic == "[ˌpɜːr ˈseɪ]"
    assert draft.quality_flags == ("incomplete_example",)
~~~

~~~python
def test_phonetic_newline_is_removed_without_adding_space():
    row = RawWordRow(
        source_page=9, source_order=42, source_section="list1",
        columns=(
            "abate", "[ə\nˈbeɪt]", "v. to become weaker 减弱", "mitigate",
            "The pain began to abate. 疼痛开始减轻。",
        ),
    )
    assert normalize_row(row).phonetic == "[əˈbeɪt]"
~~~

Run: python -m pytest tests/importer/test_normalize.py -v

Expected: all normalization tests pass.

- [ ] **Step 5: Commit**

Run: git add src/gre_vocab_app/importer/normalize.py tests/importer/test_normalize.py

Run: git commit -m "feat: normalize extracted vocabulary fields"

### Task 4: Content database builder, overrides, and audit report

**Files:**
- Create: src/gre_vocab_app/db/__init__.py
- Create: src/gre_vocab_app/db/schema.py
- Create: src/gre_vocab_app/importer/build.py
- Create: src/gre_vocab_app/importer/audit.py
- Create: src/gre_vocab_app/importer/overrides.json
- Test: tests/importer/test_build.py
- Test: tests/importer/test_audit.py

**Interfaces:**
- Consumes: extract_page_spans, group_spans_into_rows, normalize_row, WordDraft.
- Produces: build_database(entries, output_path), apply_overrides(entries, overrides), write_audit(entries, json_path, html_path), CLI main(argv).

- [ ] **Step 1: Write failing database and override tests**

~~~python
import json
import sqlite3
from gre_vocab_app.importer.build import apply_overrides, build_database
from gre_vocab_app.importer.normalize import WordDraft

def draft(word, order, flags=()):
    return WordDraft(
        source_order=order, source_section="list1", source_page=5,
        headword=word, phonetic="[x]", definition_en="adj. sample",
        definition_zh="示例", synonyms="", example_en="", example_zh="",
        raw_definition="adj. sample 示例", raw_example="", quality_flags=flags,
    )

def test_override_clears_reviewed_flags_and_database_keeps_source_order(tmp_path):
    entries = [draft("beta", 2, ("split_token",)), draft("alpha", 1)]
    fixed = apply_overrides(entries, {
        "5:beta": {"definition_en": "adj. repaired", "reviewed": True}
    })
    assert fixed[0].definition_en == "adj. repaired"
    assert fixed[0].quality_flags == ("reviewed:split_token",)
    path = tmp_path / "words.db"
    build_database(fixed, path)
    with sqlite3.connect(path) as db:
        assert db.execute(
            "select headword from words order by source_order"
        ).fetchall() == [("alpha",), ("beta",)]
~~~

- [ ] **Step 2: Run and verify failure**

Run: python -m pytest tests/importer/test_build.py tests/importer/test_audit.py -v

Expected: collection fails because build and audit modules do not exist.

- [ ] **Step 3: Implement schemas and deterministic database generation**

~~~python
# src/gre_vocab_app/db/schema.py
CONTENT_SCHEMA_VERSION = 1
USER_SCHEMA_VERSION = 1

CONTENT_SCHEMA = """
create table metadata(key text primary key, value text not null);
create table words(
  id integer primary key,
  source_order integer not null unique,
  source_section text not null,
  source_page integer not null,
  headword text not null,
  phonetic text not null,
  definition_en text not null,
  definition_zh text not null,
  synonyms text not null,
  example_en text not null,
  example_zh text not null,
  raw_definition text not null,
  raw_example text not null,
  quality_flags text not null
);
create index words_headword_nocase on words(headword collate nocase);
create index words_source_order on words(source_order);
"""
~~~

Implement build_database so it writes to a temporary sibling file, inserts metadata schema_version and record_count, inserts entries sorted by source_order with compact JSON quality flags, runs pragma integrity_check, then atomically replaces the target. Reject duplicate source_order and blank headword with ValueError.

Implement apply_overrides with dataclasses.replace. Override keys use source_page:headword; reviewed true rewrites each existing flag as reviewed:<flag> so the audit can distinguish reviewed anomalies from unresolved ones.

- [ ] **Step 4: Implement audit output and CLI**

The audit JSON must contain source SHA-256, page count, record count, section counts, unresolved records, reviewed records, and duplicate headwords. The HTML must escape every value and show one compact table per category.

The CLI signature must be:

Run: python -m gre_vocab_app.importer.build --pdf INPUT.pdf --output build/generated/words.db --audit-json build/audit/report.json --audit-html outputs/词库导入审计报告.html --overrides src/gre_vocab_app/importer/overrides.json --strict

Strict mode exits with status 2 when any quality flag lacks the reviewed: prefix. It exits with status 1 on file, PDF, SQLite, or integrity errors. It prints one final line containing records=<count> unresolved=<count> reviewed=<count>.

- [ ] **Step 5: Run tests and commit**

Run: python -m pytest tests/importer/test_build.py tests/importer/test_audit.py -v

Expected: all builder and audit tests pass.

Run: git add src/gre_vocab_app/db src/gre_vocab_app/importer tests/importer

Run: git commit -m "feat: build audited offline vocabulary database"

### Task 5: Read-only content repository and recoverable user state

**Files:**
- Create: src/gre_vocab_app/db/content.py
- Create: src/gre_vocab_app/db/user.py
- Test: tests/db/test_content.py
- Test: tests/db/test_user.py

**Interfaces:**
- Consumes: WordEntry, CONTENT_SCHEMA_VERSION, USER_SCHEMA_VERSION.
- Produces: ContentRepository(path), UserRepository(path), QueueState, UserOpenResult.

- [ ] **Step 1: Write failing repository tests**

~~~python
import pytest
from gre_vocab_app.db.content import ContentRepository
from gre_vocab_app.db.user import UserRepository
from gre_vocab_app.importer.build import build_database
from gre_vocab_app.importer.normalize import WordDraft

def make_draft(word, order):
    return WordDraft(
        source_order=order, source_section="list1", source_page=5,
        headword=word, phonetic="[x]", definition_en="adj. sample",
        definition_zh="示例", synonyms="", example_en="", example_zh="",
        raw_definition="adj. sample 示例", raw_example="", quality_flags=(),
    )

@pytest.fixture
def content_repo(tmp_path):
    path = tmp_path / "words.db"
    build_database(
        [make_draft("abate", 1), make_draft("unabated", 2)], path
    )
    return ContentRepository(path)

@pytest.fixture
def user_repo(tmp_path):
    return UserRepository(tmp_path / "user.db")

def test_content_search_prefers_prefix_then_contains(content_repo):
    assert [w.headword for w in content_repo.search("abat", limit=10)] == [
        "abate", "unabated"
    ]

def test_user_repository_persists_favorite_and_session(user_repo):
    user_repo.set_favorite(7, True)
    user_repo.save_setting("study_mode", "recall")
    user_repo.save_queue("random", [7, 2, 9], position=1, seed=44)
    assert user_repo.is_favorite(7)
    assert user_repo.load_setting("study_mode") == "recall"
    assert user_repo.load_queue("random").word_ids == (7, 2, 9)
    assert user_repo.load_queue("random").position == 1
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/db/test_content.py tests/db/test_user.py -v

Expected: collection fails because repository modules do not exist.

- [ ] **Step 3: Implement ContentRepository**

ContentRepository opens SQLite with URI mode=ro, validates metadata schema_version, maps rows to WordEntry, and exposes:

~~~python
import json
import sqlite3
from pathlib import Path
from gre_vocab_app.domain import WordEntry
from gre_vocab_app.db.schema import CONTENT_SCHEMA_VERSION

class ContentRepository:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute(
            "select value from metadata where key='schema_version'"
        ).fetchone()
        if version is None or int(version[0]) != CONTENT_SCHEMA_VERSION:
            raise ValueError("词库版本不兼容")

    @staticmethod
    def _map(row: sqlite3.Row) -> WordEntry:
        return WordEntry(
            id=row["id"], source_order=row["source_order"],
            source_section=row["source_section"], source_page=row["source_page"],
            headword=row["headword"], phonetic=row["phonetic"],
            definition_en=row["definition_en"], definition_zh=row["definition_zh"],
            synonyms=row["synonyms"], example_en=row["example_en"],
            example_zh=row["example_zh"], raw_definition=row["raw_definition"],
            raw_example=row["raw_example"],
            quality_flags=tuple(json.loads(row["quality_flags"])),
        )

    def count(self) -> int:
        return int(self.db.execute("select count(*) from words").fetchone()[0])

    def get(self, word_id: int) -> WordEntry:
        row = self.db.execute("select * from words where id=?", (word_id,)).fetchone()
        if row is None:
            raise KeyError(word_id)
        return self._map(row)

    def ids_in_source_order(self) -> tuple[int, ...]:
        rows = self.db.execute(
            "select id from words order by source_order"
        ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def search(self, query: str, limit: int = 50) -> list[WordEntry]:
        value = query.strip()
        if not value:
            return []
        prefix = self.db.execute(
            "select * from words where headword like ? collate nocase "
            "order by length(headword), headword limit ?",
            (value + "%", limit),
        ).fetchall()
        result = [self._map(row) for row in prefix]
        remaining = limit - len(result)
        if remaining <= 0:
            return result
        seen = {word.id for word in result}
        contains = self.db.execute(
            "select * from words where headword like ? collate nocase "
            "order by length(headword), headword limit ?",
            ("%" + value + "%", limit),
        ).fetchall()
        result.extend(
            self._map(row) for row in contains if row["id"] not in seen
        )
        return result[:limit]

    def list_by_ids(self, ids: tuple[int, ...]) -> list[WordEntry]:
        return [self.get(word_id) for word_id in ids]
~~~

Search executes a prefix query first, then a contains query excluding IDs already returned; empty input returns an empty list.

- [ ] **Step 4: Implement UserRepository and corruption recovery**

UserRepository creates settings, favorites, word_progress, and session_queue tables in a short transaction. It exposes set_favorite, is_favorite, favorite_ids, record_seen, load_setting, save_setting, load_queue, save_queue, reset_position, and clear_all.

~~~python
@dataclass(frozen=True, slots=True)
class QueueState:
    word_ids: tuple[int, ...]
    position: int
    seed: int

@dataclass(frozen=True, slots=True)
class UserOpenResult:
    repository: "UserRepository"
    recovered_from: Path | None
~~~

Add UserRepository.open_recovering(path) -> UserOpenResult: on sqlite3.DatabaseError it renames the original file to user.db.corrupt-YYYYMMDD-HHMMSS, creates a fresh database, and returns recovered_from set to the backup path. It never deletes the backup.

- [ ] **Step 5: Run tests and commit**

Run: python -m pytest tests/db -v

Expected: repository, migration, and corruption recovery tests pass.

Run: git add src/gre_vocab_app/db tests/db

Run: git commit -m "feat: persist vocabulary and local study state"

### Task 6: Study session and search behavior

**Files:**
- Create: src/gre_vocab_app/services/__init__.py
- Create: src/gre_vocab_app/services/study.py
- Create: src/gre_vocab_app/services/search.py
- Test: tests/services/test_study.py
- Test: tests/services/test_search.py

**Interfaces:**
- Consumes: ContentRepository, UserRepository, StudyMode, BrowseOrder, SessionSnapshot.
- Produces: StudySession.start(order), current(), next(), previous(), set_mode(), toggle_answer(), reshuffle(); SearchService.search(query).

- [ ] **Step 1: Write failing session tests using fake repositories**

~~~python
import random
import pytest
from gre_vocab_app.db.user import QueueState
from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry
from gre_vocab_app.services.study import StudySession

class FakeContent:
    def __init__(self):
        self.words = {
            i: WordEntry(
                id=i, source_order=i, source_section="list1", source_page=5,
                headword=f"word{i}", phonetic="[x]",
                definition_en="adj. sample", definition_zh="示例",
                synonyms="", example_en="", example_zh="",
                raw_definition="adj. sample 示例", raw_example="",
            )
            for i in range(1, 11)
        }

    def ids_in_source_order(self):
        return tuple(self.words)

    def get(self, word_id):
        return self.words[word_id]

    def search(self, query, limit=50):
        value = query.casefold()
        return [
            word for word in self.words.values()
            if value in word.headword.casefold()
        ][:limit]

class FakeUser:
    def __init__(self):
        self.settings = {}
        self.queues = {}
        self.favorites = set()
        self.seen = []

    def load_setting(self, key, default=None):
        return self.settings.get(key, default)

    def save_setting(self, key, value):
        self.settings[key] = value

    def load_queue(self, name):
        return self.queues.get(name)

    def save_queue(self, name, word_ids, position, seed):
        self.queues[name] = QueueState(tuple(word_ids), position, seed)

    def is_favorite(self, word_id):
        return word_id in self.favorites

    def set_favorite(self, word_id, value):
        self.favorites.discard(word_id)
        if value:
            self.favorites.add(word_id)

    def record_seen(self, word_id):
        self.seen.append(word_id)

@pytest.fixture
def user_repo():
    return FakeUser()

@pytest.fixture
def session(user_repo):
    return StudySession(FakeContent(), user_repo, random.Random(1234))

def test_mode_switch_keeps_word_and_resets_answer_only_on_navigation(session):
    first = session.start(BrowseOrder.SOURCE)
    session.set_mode(StudyMode.RECALL)
    session.toggle_answer()
    assert session.current().word.id == first.word.id
    assert session.current().answer_visible is True
    after = session.next()
    assert after.word.id != first.word.id
    assert after.mode is StudyMode.RECALL
    assert after.answer_visible is False

def test_random_queue_has_no_repeat_and_persists(session, user_repo):
    seen = [session.start(BrowseOrder.RANDOM).word.id]
    seen.extend(session.next().word.id for _ in range(9))
    assert len(seen) == len(set(seen))
    assert user_repo.load_queue("random").position == 9
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/services/test_study.py tests/services/test_search.py -v

Expected: collection fails because service modules do not exist.

- [ ] **Step 3: Implement StudySession**

StudySession receives repositories and random.Random. Source mode uses ids_in_source_order. Random mode restores a saved queue only when it contains exactly the current content ID set; otherwise it shuffles a fresh list with a saved seed. next stops at the last item and returns a SessionSnapshot with at_end=True; it never wraps. previous stops at zero and returns at_start=True. A word is recorded as seen only when it becomes current through start or navigation, not when switching display mode.

- [ ] **Step 4: Implement SearchService**

SearchService trims input, delegates to ContentRepository.search, and returns at most 50 results. It never writes search history or user state.

- [ ] **Step 5: Run tests and commit**

Run: python -m pytest tests/services -v

Expected: source, random, persistence, boundary, mode, favorite, and search tests pass.

Run: git add src/gre_vocab_app/services tests/services

Run: git commit -m "feat: add continuous dual-mode study sessions"

### Task 7: Windows speech adapter

**Files:**
- Create: src/gre_vocab_app/services/speech.py
- Test: tests/services/test_speech.py

**Interfaces:**
- Consumes: QtTextToSpeech.QTextToSpeech through QtSpeechBackend.
- Produces: VoiceOption, SpeechBackend, QtSpeechBackend, SpeechService.available, voice_names(), select_voice(name), set_rate(value), speak(headword).

- [ ] **Step 1: Write a failing test with a fake speech engine**

~~~python
class FakeSpeechBackend:
    def __init__(self, available=True):
        self.available = available
        self.rate = 0.0
        self.selected = ""
        self.spoken = []

    def voices(self):
        return (VoiceOption(name="Microsoft David", locale="en-US"),)

    def select_voice(self, name):
        self.selected = name
        return name == "Microsoft David"

    def set_rate(self, value):
        self.rate = value

    def say(self, text):
        self.spoken.append(text)
        return self.available

def test_speech_service_uses_selected_english_voice():
    backend = FakeSpeechBackend()
    service = SpeechService(backend=backend)
    assert service.voice_names() == ("Microsoft David",)
    service.select_voice("Microsoft David")
    service.set_rate(0.2)
    service.speak("inevitable")
    assert backend.spoken == ["inevitable"]
    assert backend.rate == 0.2

def test_unavailable_engine_does_not_raise():
    service = SpeechService(backend=FakeSpeechBackend(available=False))
    assert service.available is False
    assert service.speak("abate") is False
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/services/test_speech.py -v

Expected: import fails because SpeechService does not exist.

- [ ] **Step 3: Implement the adapter**

VoiceOption is a frozen dataclass with name and locale. SpeechBackend is a Protocol with available, voices, select_voice, set_rate, and say. QtSpeechBackend adapts QTextToSpeech/QVoice to that protocol. SpeechService chooses voices whose locale name begins with en, exposes immutable display names, clamps rate to -1.0 through 1.0, and returns False instead of raising when no engine or voice is available. Engine errors are emitted through a Qt signal carrying a user-facing Chinese message and a technical log string.

- [ ] **Step 4: Run tests and commit**

Run: python -m pytest tests/services/test_speech.py -v

Expected: available and unavailable paths pass.

Run: git add src/gre_vocab_app/services/speech.py tests/services/test_speech.py

Run: git commit -m "feat: speak words with Windows text to speech"

### Task 8: Reusable word view, home, search, and favorites UI

**Files:**
- Create: src/gre_vocab_app/ui/__init__.py
- Create: src/gre_vocab_app/ui/theme.py
- Create: src/gre_vocab_app/ui/word_detail.py
- Create: src/gre_vocab_app/ui/home_page.py
- Create: src/gre_vocab_app/ui/favorites_page.py
- Test: tests/ui/test_home_page.py
- Test: tests/ui/test_word_detail.py
- Test: tests/ui/test_favorites_page.py

**Interfaces:**
- Consumes: WordEntry and lists of WordEntry.
- Produces: HomePage signals continueRequested, sourceRequested, randomRequested, favoriteRequested, wordSelected; FavoritesPage wordSelected and favoriteRemoved; WordDetail.set_word(word, reveal).

- [ ] **Step 1: Write failing Qt component tests**

~~~python
def test_home_search_emits_trimmed_query(qtbot):
    page = HomePage()
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.searchRequested) as signal:
        page.search_edit.setText("  abat ")
    assert signal.args == ["abat"]

def test_word_detail_hides_and_reveals_meaning(qtbot, sample_word):
    detail = WordDetail()
    qtbot.addWidget(detail)
    detail.set_word(sample_word, reveal=False)
    assert not detail.meaning_panel.isVisible()
    detail.set_revealed(True)
    assert detail.meaning_panel.isVisible()
    assert "必然的" in detail.definition_label.text()
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/ui/test_home_page.py tests/ui/test_word_detail.py tests/ui/test_favorites_page.py -v

Expected: collection fails because UI modules do not exist.

- [ ] **Step 3: Implement theme and WordDetail**

Use QWidget/QVBoxLayout only, not QML or WebEngine. WordDetail contains headword, phonetic, speech button, POS/definition, synonyms, example and translation labels. Every label uses word wrap and selectable text. set_word clears stale optional fields before applying the next word. set_revealed controls one meaning_panel container.

- [ ] **Step 4: Implement HomePage and FavoritesPage**

HomePage contains search QLineEdit, progress cards, four action buttons, and a QListWidget search result panel. FavoritesPage contains search, empty state, list, open and remove actions. Expose methods set_stats(total, seen, favorites), set_results(words), and set_words(words) so pages remain free of repositories.

- [ ] **Step 5: Run tests and commit**

Run: python -m pytest tests/ui/test_home_page.py tests/ui/test_word_detail.py tests/ui/test_favorites_page.py -v

Expected: signal, empty-state, long-text, and reveal tests pass.

Run: git add src/gre_vocab_app/ui tests/ui

Run: git commit -m "feat: build offline vocabulary browsing views"

### Task 9: Dual-mode study page, settings, window, and controller

**Files:**
- Create: src/gre_vocab_app/ui/study_page.py
- Create: src/gre_vocab_app/ui/settings_dialog.py
- Create: src/gre_vocab_app/ui/main_window.py
- Create: src/gre_vocab_app/controller.py
- Test: tests/ui/test_study_page.py
- Test: tests/ui/test_settings_dialog.py
- Test: tests/test_controller.py

**Interfaces:**
- Consumes: StudySession, SpeechService, SearchService, HomePage, FavoritesPage.
- Produces: MainWindow and ApplicationController.start().

- [ ] **Step 1: Write failing interaction tests**

~~~python
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
import pytest
from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode
from gre_vocab_app.ui.study_page import StudyPage

@pytest.fixture
def study_page(qtbot):
    page = StudyPage()
    qtbot.addWidget(page)
    return page

@pytest.fixture
def sample_snapshot(sample_word):
    return SessionSnapshot(
        word=sample_word, index=0, total=10, mode=StudyMode.RECALL,
        order=BrowseOrder.SOURCE, answer_visible=False, favorite=False,
        at_start=True, at_end=False,
    )

def test_study_page_mode_switch_does_not_emit_navigation(qtbot, study_page):
    next_spy = QSignalSpy(study_page.nextRequested)
    with qtbot.waitSignal(study_page.modeRequested) as mode_signal:
        study_page.recall_button.click()
    assert mode_signal.args == [StudyMode.RECALL]
    assert next_spy.count() == 0

def test_space_reveals_only_in_recall_mode(qtbot, study_page, sample_snapshot):
    study_page.render(sample_snapshot)
    study_page.setFocus()
    with qtbot.waitSignal(study_page.answerToggleRequested):
        qtbot.keyClick(study_page, Qt.Key_Space)

def test_right_arrow_requests_next_word(qtbot, study_page):
    with qtbot.waitSignal(study_page.nextRequested):
        qtbot.keyClick(study_page, Qt.Key_Right)
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/ui/test_study_page.py tests/ui/test_settings_dialog.py tests/test_controller.py -v

Expected: collection fails because the modules do not exist.

- [ ] **Step 3: Implement StudyPage and SettingsDialog**

StudyPage uses two checkable buttons in an exclusive QButtonGroup for 阅读模式 and 回忆模式. It renders SessionSnapshot through WordDetail, shows index/total, disables next at the end, and maps Left, Right, Space, P, and S with QShortcut. Space is ignored when an editable child has focus. SettingsDialog lists available English voices, rate slider -10 through 10 mapped to -1.0 through 1.0, default mode, reset position, and clear-all buttons. Destructive clear requires a QMessageBox confirmation naming the local data affected.

- [ ] **Step 4: Implement MainWindow and ApplicationController**

MainWindow owns a QStackedWidget with home, study, and favorites pages plus SettingsDialog. ApplicationController is the only object connecting page signals to repositories/services. It refreshes stats after every favorite or navigation change, persists settings immediately, and shows non-blocking status-bar messages for boundaries and speech errors.

- [ ] **Step 5: Run tests and commit**

Run: python -m pytest tests/ui/test_study_page.py tests/ui/test_settings_dialog.py tests/test_controller.py -v

Expected: dual-mode, navigation, shortcut, persistence, and destructive confirmation tests pass.

Run: git add src/gre_vocab_app/ui src/gre_vocab_app/controller.py tests/ui tests/test_controller.py

Run: git commit -m "feat: connect dual-mode desktop learning workflow"

### Task 10: Bootstrap, logging, real PDF import, and audit closure

**Files:**
- Create: src/gre_vocab_app/bootstrap.py
- Create: src/gre_vocab_app/__main__.py
- Create: main.py
- Modify: src/gre_vocab_app/importer/overrides.json
- Create: tests/test_bootstrap.py
- Generate ignored: build/generated/words.db
- Generate ignored: build/audit/report.json
- Generate ignored: outputs/词库导入审计报告.html

**Interfaces:**
- Consumes: AppPaths, repositories, services, MainWindow, ApplicationController.
- Produces: BootstrapResult and bootstrap(paths) -> BootstrapResult; executable development entry.

- [ ] **Step 1: Write failing bootstrap tests**

~~~python
def test_bootstrap_refuses_missing_content_database(tmp_path):
    paths = AppPaths.resolve(
        content_override=tmp_path / "missing.db", user_root=tmp_path / "user"
    )
    with pytest.raises(ContentDatabaseError, match="词库文件缺失"):
        bootstrap(paths)

def test_bootstrap_recovers_corrupt_user_database(content_db, tmp_path):
    paths = AppPaths.resolve(content_override=content_db, user_root=tmp_path)
    paths.user_db.write_bytes(b"not sqlite")
    result = bootstrap(paths)
    assert result.recovery_notice
    assert list(tmp_path.glob("user.db.corrupt-*"))
~~~

- [ ] **Step 2: Verify failure**

Run: python -m pytest tests/test_bootstrap.py -v

Expected: collection fails because bootstrap.py does not exist.

- [ ] **Step 3: Implement bootstrap and entry points**

bootstrap validates content schema version and pragma integrity_check before opening the main window, creates log directories, configures a rotating 1 MB local log with three backups, uses UserRepository.open_recovering, and returns a small BootstrapResult containing controller, window, and optional recovery_notice. main.py creates QApplication, sets organization/application names, installs theme, shows the window, and exits with app.exec().

- [ ] **Step 4: Run the full real-PDF import in non-strict mode**

Run: python -m gre_vocab_app.importer.build --pdf "D:/桌面/LGU/GRE/张巍GRE镇考3000词-乱序（2026年）.pdf" --output build/generated/words.db --audit-json build/audit/report.json --audit-html outputs/词库导入审计报告.html --overrides src/gre_vocab_app/importer/overrides.json

Expected: exit 0, record count is written to metadata and report.json, and every unresolved record appears in the HTML report.

- [ ] **Step 5: Close every audit finding with repeatable overrides**

For each unresolved row, compare the rendered PDF page with raw fields and add a complete replacement for only the incorrect fields under the source_page:headword key in overrides.json. Mark reviewed true. Do not edit generated words.db directly.

Run the same importer command with --strict.

Expected: final line contains unresolved=0, integrity_check is ok, every PDF word-row anchor maps to exactly one database source_order, and the HTML report lists reviewed repairs separately.

- [ ] **Step 6: Run application smoke test and commit source corrections**

Run: GRE_WORDS_DB="build/generated/words.db" python main.py

Manual verification: open home, search abate, start source study, switch reading/recall without changing the word, play speech, favorite the word, close, reopen, and confirm position/mode/favorite persist.

Run: python -m pytest -v

Expected: all automated tests pass.

Run: git add main.py src/gre_vocab_app/bootstrap.py src/gre_vocab_app/__main__.py src/gre_vocab_app/importer/overrides.json tests/test_bootstrap.py

Run: git commit -m "feat: bootstrap audited offline GRE application"

### Task 11: Icon, packaging, release script, and end-to-end verification

**Files:**
- Create: resources/app.svg
- Create: resources/app.ico
- Create: pysidedeploy.spec
- Create: scripts/build_release.ps1
- Create: README.md
- Create: tests/test_packaged_paths.py
- Generate ignored: outputs/GRE 3000 词离线版.exe
- Create: outputs/使用说明.txt

**Interfaces:**
- Consumes: main.py, build/generated/words.db, all tests.
- Produces: the three approved user-facing deliverables in outputs.

- [ ] **Step 1: Write a failing packaged-resource path test**

~~~python
def test_packaged_content_override_points_to_embedded_database(tmp_path, monkeypatch):
    bundled = tmp_path / "bundle" / "gre_vocab_app" / "data" / "words.db"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"content")
    monkeypatch.setattr(paths_module, "PACKAGE_ROOT", bundled.parents[1])
    assert AppPaths.resolve(user_root=tmp_path / "user").content_db == bundled
~~~

- [ ] **Step 2: Verify failure, then make packaged path explicit**

Run: python -m pytest tests/test_packaged_paths.py -v

Expected: fails until paths.py exposes PACKAGE_ROOT and resolves gre_vocab_app/data/words.db consistently in source and onefile extraction layouts.

- [ ] **Step 3: Add independent icon and packaging configuration**

Create an SVG showing a simple open book and the letters GRE in the approved green palette, with no copied logo. Convert it to ICO using Pillow during the build script. Initialize pyside6-deploy configuration and set:

- input file: main.py
- title: GRE 3000 词离线版
- icon: resources/app.ico
- mode: onefile
- Qt modules: Core, Gui, Widgets, Sql, TextToSpeech
- Nuitka extra data: build/generated/words.db to gre_vocab_app/data/words.db
- Windows console mode: disabled

- [ ] **Step 4: Implement scripts/build_release.ps1**

The script must stop on any nonzero exit and perform these commands in order:

1. python -m pytest -v
2. strict importer command from Task 10
3. verify SQLite metadata record_count equals audit JSON record_count
4. generate resources/app.ico from resources/app.svg
5. pyside6-deploy -c pysidedeploy.spec
6. copy the produced EXE to outputs/GRE 3000 词离线版.exe
7. run the EXE with GRE_APP_DATA_ROOT pointing to a fresh build/smoke-profile
8. verify process starts, main window appears, no console window is created, then close it normally
9. compute and print SHA-256 and byte size

Use Start-Process -PassThru for the smoke launch, wait up to 20 seconds for MainWindowTitle, and fail with a clear message if it never appears.

- [ ] **Step 5: Write user instructions and run release build**

outputs/使用说明.txt must explain double-click launch, local data location, keyboard shortcuts, reading/recall switch, source/random modes, speech dependency, unsigned SmartScreen possibility, and how replacing the EXE preserves user data.

Run: powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1

Expected: tests and strict audit pass, EXE smoke launch succeeds, and outputs contains the EXE, 使用说明.txt, and 词库导入审计报告.html.

- [ ] **Step 6: Final verification and commit**

Run: python -m pytest -v

Run: git diff --check

Run: git status --short

Expected: tests pass; diff check is clean; generated database/build files plus the ignored EXE and audit HTML remain outside committed source, while 使用说明.txt is committed.

Run: git add resources pysidedeploy.spec scripts README.md tests/test_packaged_paths.py outputs/使用说明.txt

Run: git commit -m "build: package GRE vocabulary offline release"

Record final EXE SHA-256, byte size, test count, imported record count, reviewed repair count, and smoke result in the task handoff.

---

## Plan Self-Review Checklist

- [x] Spec sections 1-3 map to Global Constraints and Tasks 8-11.
- [x] Architecture and data design map to Tasks 1-7 and 10.
- [x] Page behavior and keyboard interaction map to Tasks 6, 8, and 9.
- [x] Error handling maps to Tasks 5, 7, 9, and 10.
- [x] Parser, application, packaging, and smoke verification map to Tasks 2-4 and 10-11.
- [x] The importer has both synthetic tests and bounded real-PDF integration checks.
- [x] No generated full词库数据库 is added to Git.
- [x] Repository, service, and UI interface names are consistent across tasks.
- [x] Every task has a failing test, focused implementation, passing verification, and commit.
- [x] The final build reruns tests, strict audit, packaged-path test, and EXE smoke launch.
- [x] The only unresolved user action after execution is handling an optional Windows SmartScreen warning for an unsigned personal build.
