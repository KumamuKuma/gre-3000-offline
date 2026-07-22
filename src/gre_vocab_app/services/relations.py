from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence

from gre_vocab_app.domain import RelatedWord, RootFamily, WordEntry


_LETTERS = re.compile(r"[^a-z]")
_MEANING_PUNCTUATION = re.compile(r"[^\w\u3400-\u9fff]")
_MEANING_SEPARATOR = re.compile(r"[,，;；/、|]+")

# Conservative, high-value GRE roots. Variants in one group share the same
# historical root. Short, highly ambiguous fragments are intentionally omitted.
_ROOT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("anthrop（人）", ("anthrop",)),
    ("aud（听）", ("audi", "audit")),
    ("bene（好）", ("bene",)),
    ("bibli（书）", ("bibli",)),
    ("bio（生命）", ("bio",)),
    ("cap / capt / cept（取、拿）", ("capt", "cept")),
    ("ced / ceed / cess（走、让步）", ("cede", "ceed", "cess")),
    ("celer（迅速）", ("celer",)),
    ("chron（时间）", ("chron",)),
    ("claim / clam（呼喊）", ("claim", "clamor", "clamation")),
    ("clud / clus（关闭）", ("clud", "clus")),
    ("cogn / gnos（知道）", ("cogn", "gnos")),
    ("corp（身体）", ("corp",)),
    ("cred / credit（相信）", ("cred",)),
    ("cur / curs（跑）", ("curr", "cursi", "cursor")),
    ("culp（罪责）", ("culp",)),
    ("dict（说）", ("dict",)),
    ("duc / duct（引导）", ("duc", "duct")),
    ("fac / fact / fect（做）", ("fact", "fect")),
    ("flect / flex（弯曲）", ("flect", "flex")),
    ("fid（相信、忠诚）", ("fidel", "fiduc")),
    ("fin（结束、界限）", ("finit", "defin")),
    ("fract / frag（打破）", ("fract", "frag")),
    ("gen（产生、种类）", ("gene", "geni", "genous")),
    ("grad / gress（走、步）", ("grad", "gress")),
    ("graph（写、画）", ("graph",)),
    ("greg（群体）", ("greg",)),
    ("humil（低、谦卑）", ("humil",)),
    ("ject（投、掷）", ("ject",)),
    ("jur（法律、发誓）", ("jur",)),
    ("leg / lect（选择、读）", ("lect",)),
    ("liber（自由）", ("liber",)),
    ("loc（地方）", ("locat", "local")),
    ("log / logue（言说、学科）", ("logy", "logue", "logic")),
    ("luc / lum（光）", ("lucid", "elucid", "pellucid", "lumin", "lucub")),
    ("magn（大）", ("magn",)),
    ("manu（手）", ("manu",)),
    ("meter / metr（测量）", ("meter", "metr")),
    ("migr（迁移）", ("migr",)),
    ("miss / mit（送）", ("miss", "mitt")),
    ("mob / mot / mov（移动）", ("mobil", "mot", "mov")),
    ("morph（形态）", ("morph",)),
    ("mort（死亡）", ("mort",)),
    ("nasc / nat（出生）", ("nasc", "natal", "native")),
    ("nom / nym（名称）", ("nomen", "onym")),
    ("nov（新）", ("nov",)),
    ("path（感受、疾病）", ("path",)),
    ("ped / pod（脚）", ("pedi", "pod")),
    ("pend / pens（悬挂、称量）", ("pend", "pens")),
    ("phil（爱）", ("phil",)),
    ("phon（声音）", ("phon",)),
    ("photo（光）", ("photo",)),
    ("plac / pleas（取悦）", ("placid", "placat", "complac", "implac", "placab", "pleas")),
    ("pli / ply（折叠）", ("plic", "plex")),
    ("pon / pos（放置）", ("posit", "postur")),
    ("psych（心智）", ("psych",)),
    ("quer / quis（寻求、询问）", ("quer", "quisit", "inquir", "acquir", "requir", "questi")),
    ("rect / reg（直、规则）", ("rect", "regul")),
    ("rog / rogat（询问、提出）", ("rogat",)),
    ("rupt（破裂）", ("rupt",)),
    ("scrib / script（写）", ("scrib", "script")),
    ("sect（切）", ("sect",)),
    ("sens / sent（感觉）", ("sens", "sentiment")),
    ("sequ / secu（跟随）", ("sequ", "secut")),
    ("simil / sembl（相似）", ("simil", "sembl")),
    ("solv / solu（松开、解决）", ("solv", "solut")),
    ("spec / spect（看）", ("spec", "spect")),
    ("spir（呼吸）", ("spir",)),
    ("stat / stit（站立、放置）", ("status", "static", "stately", "state", "stitut", "stiti", "hypostat", "substanti")),
    ("strict / strain / string（拉紧）", ("strict", "strain", "string")),
    ("struct（建造）", ("struct",)),
    ("surg / surrect（升起）", ("surg", "surrect")),
    ("tact / tang（接触）", ("tact", "tang")),
    ("tempor（时间）", ("tempor",)),
    ("tenu（细、薄）", ("tenu",)),
    ("ten / tain / tin（持有）", ("tain", "tinu")),
    ("tract（拉）", ("tract",)),
    ("urb（城市）", ("urban",)),
    ("vac（空）", ("vacu",)),
    ("ven / vent（来）", ("vent",)),
    ("ver（真实）", ("verit", "verac")),
    ("vid / vis（看）", ("vision", "visual", "visible", "eviden", "providen", "invidi", "envis")),
    ("voc / vok（声音、召唤）", ("vocat", "vocal", "vocif", "voke", "vok", "equivoc", "advoc", "provoc", "invoc", "evoc")),
    ("vol（意愿）", ("volunt",)),
    ("vor（吃）", ("vorac", "devour")),
)

_ROOT_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "bio（生命）": ("dubious",),
    "ced / ceed / cess（走、让步）": ("necess",),
    "clud / clus（关闭）": ("cluster",),
    "fract / frag（打破）": ("suffrage",),
    "leg / lect（选择、读）": ("deflect", "reflect"),
    "liber（自由）": ("deliberate",),
    "luc / lum（光）": ("voluminous",),
    "miss / mit（送）": ("amiss",),
    "mob / mot / mov（移动）": ("behemoth", "motley", "smother"),
    "nasc / nat（出生）": ("alternative",),
    "nom / nym（名称）": ("phenomen",),
    "ped / pod（脚）": ("encyclopedic", "hodgepodge"),
    "pend / pens（悬挂、称量）": ("upend",),
    "phil（爱）": ("philistine",),
    "phon（声音）": ("siphon",),
    "quer / quis（寻求、询问）": ("querulous",),
    "rect / reg（直、规则）": ("insurrection", "resurrect"),
    "sequ / secu（跟随）": ("sequester",),
    "spir（呼吸）": ("spiral",),
    "stat / stit（站立、放置）": ("devastate",),
    "tact / tang（接触）": ("tactic",),
    "ten / tain / tin（持有）": ("taint",),
    "ven / vent（来）": ("fervent", "insolvent"),
}

# Exact, manually reviewed lexical families. These cover high-value families
# whose spelling changes are too irregular for safe suffix heuristics. Keeping
# them explicit prevents unrelated lookalikes from being mislabeled as roots.
_CURATED_WORD_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ambigu（两可）", ("ambiguous", "unambiguous")),
    ("balanc（平衡）", ("balanced", "unbalanced", "counterbalance")),
    ("civil（公民、礼貌）", ("civility", "incivility")),
    ("compar（比较）", ("comparable", "incomparable")),
    ("compat（相容）", ("compatible", "incompatible")),
    ("decor（礼节）", ("decorous", "indecorous")),
    ("econom（管理、经济）", ("economic", "economy")),
    ("episod（片段）", ("episode", "episodic")),
    ("feebl（虚弱）", ("feeble", "enfeeble")),
    ("found（建立、根据）", ("founder", "foundation", "unfounded")),
    ("grudg（怨恨、勉强）", ("grudge", "begrudge")),
    ("inform（告知）", ("informative", "uninformative")),
    ("impeach（控告）", ("impeachable", "unimpeachable")),
    ("iter（重复）", ("iterate", "reiterate")),
    ("lud（玩、戏）", ("allude", "collude", "delude", "elude")),
    ("minut（小）", ("minute", "minutia", "minutiae", "diminutive")),
    ("moment（移动、时刻）", ("momentary", "momentous", "momentum")),
    ("orthodox（正统）", ("orthodox", "unorthodox")),
    ("ostentat（展示）", ("ostentatious", "unostentatious")),
    ("perme（穿过）", ("permeable", "permeate")),
    ("pertinent（相关）", ("pertinent", "impertinent")),
    ("politic（治理、策略）", ("politic", "impolitic")),
    ("prepossess（预先影响）", ("prepossessing", "unprepossessing")),
    ("prud（预见、审慎）", ("prudent", "imprudent")),
    ("riv（裂开）", ("rive", "riven")),
    ("seemly（得体）", ("seemly", "unseemly")),
    ("tenable（可守、可持）", ("tenable", "untenable")),
    ("tether（拴系）", ("tether", "untether")),
)

# Same lexical item, spelling variant, or reviewed overlapping meaning: these
# must never be presented as different-meaning lookalikes.
_LOOKALIKE_EXCLUSIONS = {
    frozenset(("bloom", "boom")),
    frozenset(("mold", "mould")),
    frozenset(("musty", "fusty")),
    frozenset(("rein", "reign")),
}

_STEM_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "impart": ("impartial",),
}

# A small set of established confusing pairs that are two edits apart. All
# other automatic pairs must be only one edit apart, or share a long unchanged
# beginning/end; this keeps the panel useful instead of flooding it with loose
# similarities.
_CURATED_LOOKALIKE_PAIRS = {
    frozenset(("eminent", "imminent")),
    frozenset(("elicit", "illicit")),
    frozenset(("personal", "personnel")),
    frozenset(("council", "counsel")),
}

_SUFFIXES = (
    "ational",
    "ization",
    "isation",
    "fulness",
    "ousness",
    "iveness",
    "ability",
    "ibility",
    "ation",
    "ition",
    "ution",
    "ement",
    "ments",
    "ances",
    "ences",
    "ically",
    "ality",
    "ility",
    "ivity",
    "ous",
    "ive",
    "ance",
    "ence",
    "able",
    "ible",
    "ment",
    "ness",
    "less",
    "ful",
    "ary",
    "ory",
    "ism",
    "ist",
    "ize",
    "ise",
    "ify",
    "tion",
    "sion",
    "ant",
    "ent",
    "ial",
    "ical",
    "ic",
    "al",
    "ly",
    "ing",
    "ed",
    "er",
    "or",
    "es",
    "s",
)


def _word_key(value: str) -> str:
    return _LETTERS.sub("", value.casefold())


def _meaning_key(value: str) -> str:
    return _MEANING_PUNCTUATION.sub("", value.casefold())


def _meaning_phrases(value: str) -> frozenset[str]:
    return frozenset(
        phrase
        for part in _MEANING_SEPARATOR.split(value.casefold())
        if len(phrase := _meaning_key(part)) >= 2
    )


def _display_meaning(word: WordEntry) -> str:
    value = word.definition_zh or word.definition_en
    return " ".join(value.split())


def _related_word(word: WordEntry) -> RelatedWord:
    return RelatedWord(word.id, word.headword, _display_meaning(word))


def _stem_key(value: str) -> str | None:
    key = _word_key(value)
    if len(key) < 6:
        return None
    base = key
    for suffix in _SUFFIXES:
        if base.endswith(suffix) and len(base) - len(suffix) >= 5:
            base = base[: -len(suffix)]
            break
    if base.endswith("y") and len(base) >= 5:
        base = base[:-1] + "i"
    return base if len(base) >= 5 else None


def _deletes(value: str, distance: int = 2) -> set[str]:
    results = {value}
    frontier = {value}
    for _ in range(distance):
        next_frontier: set[str] = set()
        for item in frontier:
            next_frontier.update(item[:index] + item[index + 1 :] for index in range(len(item)))
        next_frontier -= results
        results.update(next_frontier)
        frontier = next_frontier
    return results


def _common_prefix_length(left: str, right: str) -> int:
    result = 0
    for left_character, right_character in zip(left, right, strict=False):
        if left_character != right_character:
            break
        result += 1
    return result


def _common_suffix_length(left: str, right: str) -> int:
    return _common_prefix_length(left[::-1], right[::-1])


def _osa_distance(left: str, right: str, cutoff: int = 2) -> int:
    """Optimal-string-alignment distance with an early length cutoff."""

    if left == right:
        return 0
    if abs(len(left) - len(right)) > cutoff:
        return cutoff + 1
    previous_previous: list[int] | None = None
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        row_minimum = left_index
        for right_index, right_character in enumerate(right, start=1):
            cost = 0 if left_character == right_character else 1
            value = min(
                current[right_index - 1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + cost,
            )
            if (
                previous_previous is not None
                and left_index > 1
                and right_index > 1
                and left_character == right[right_index - 2]
                and left[left_index - 2] == right_character
            ):
                value = min(value, previous_previous[right_index - 2] + 1)
            current.append(value)
            row_minimum = min(row_minimum, value)
        if row_minimum > cutoff:
            return cutoff + 1
        previous_previous, previous = previous, current
    return previous[-1]


class WordRelationIndex:
    """Build conservative root-family and confusing-lookalike relationships."""

    def __init__(
        self,
        words: Sequence[WordEntry],
        *,
        excluded_lookalike_pairs: Iterable[tuple[int, int]] = (),
    ):
        self._words = tuple(words)
        self._by_id = {word.id: word for word in self._words}
        self._keys = {word.id: _word_key(word.headword) for word in self._words}
        self._excluded_lookalike_pairs = {
            frozenset((int(left), int(right)))
            for left, right in excluded_lookalike_pairs
            if int(left) != int(right)
        }
        self._root_families_by_word = self._build_root_families()
        self._lookalikes_by_word = self._build_lookalikes()

    def _build_root_families(self) -> dict[int, tuple[RootFamily, ...]]:
        family_members: list[tuple[str, tuple[int, ...]]] = []
        for label, variants in _ROOT_GROUPS:
            exclusions = _ROOT_EXCLUSIONS.get(label, ())
            members = tuple(
                word.id
                for word in self._words
                if any(variant in self._keys[word.id] for variant in variants)
                and not any(
                    exclusion in self._keys[word.id]
                    for exclusion in exclusions
                )
            )
            if len(members) >= 2:
                family_members.append((label, members))

        ids_by_key: dict[str, list[int]] = defaultdict(list)
        for word in self._words:
            ids_by_key[self._keys[word.id]].append(word.id)
        for label, headwords in _CURATED_WORD_FAMILIES:
            members = tuple(
                word_id
                for headword in headwords
                for word_id in ids_by_key.get(_word_key(headword), ())
            )
            if len(members) >= 2:
                family_members.append((label, members))

        reviewed_member_sets = tuple(
            frozenset(members) for _label, members in family_members
        )

        stems: dict[str, list[int]] = defaultdict(list)
        for word in self._words:
            stem = _stem_key(word.headword)
            if stem is not None:
                stems[stem].append(word.id)
        for stem, members in stems.items():
            member_set = frozenset(members)
            if len(members) < 2 or any(
                excluded in self._keys[word_id]
                for excluded in _STEM_EXCLUSIONS.get(stem, ())
                for word_id in members
            ):
                continue
            if any(member_set <= reviewed for reviewed in reviewed_member_sets):
                continue
            family_members.append((f"{stem}（同族）", tuple(members)))

        result: dict[int, list[RootFamily]] = defaultdict(list)
        seen_sets: dict[int, set[frozenset[int]]] = defaultdict(set)
        for label, members in family_members:
            member_set = frozenset(members)
            for word_id in members:
                other_ids = tuple(item for item in members if item != word_id)
                if not other_ids or member_set in seen_sets[word_id]:
                    continue
                seen_sets[word_id].add(member_set)
                related = tuple(
                    _related_word(self._by_id[item])
                    for item in sorted(
                        other_ids,
                        key=lambda item: self._by_id[item].source_order,
                    )
                )
                result[word_id].append(RootFamily(label, related))

        return {
            word.id: tuple(result.get(word.id, ()))
            for word in self._words
        }

    def _build_lookalikes(self) -> dict[int, tuple[RelatedWord, ...]]:
        signature_index: dict[str, list[int]] = defaultdict(list)
        for word in self._words:
            key = self._keys[word.id]
            if len(key) < 4:
                continue
            for signature in _deletes(key):
                signature_index[signature].append(word.id)

        root_related: dict[int, set[int]] = {}
        for word in self._words:
            root_related[word.id] = {
                related.word_id
                for family in self._root_families_by_word.get(word.id, ())
                for related in family.words
            }

        result: dict[int, tuple[RelatedWord, ...]] = {}
        for word in self._words:
            key = self._keys[word.id]
            if len(key) < 4:
                result[word.id] = ()
                continue
            candidate_ids: set[int] = set()
            for signature in _deletes(key):
                candidate_ids.update(signature_index.get(signature, ()))
            candidate_ids.discard(word.id)
            source_meaning = _meaning_key(_display_meaning(word))
            source_phrases = _meaning_phrases(_display_meaning(word))
            scored: list[tuple[int, int, int]] = []
            for candidate_id in candidate_ids:
                if candidate_id in root_related[word.id]:
                    continue
                if frozenset((word.id, candidate_id)) in self._excluded_lookalike_pairs:
                    continue
                candidate = self._by_id[candidate_id]
                candidate_key = self._keys[candidate_id]
                word_pair = frozenset((key, candidate_key))
                if word_pair in _LOOKALIKE_EXCLUSIONS:
                    continue
                if (
                    (" " in word.headword.strip() or " " in candidate.headword.strip())
                    and word_pair not in _CURATED_LOOKALIKE_PAIRS
                ):
                    continue
                maximum = max(len(key), len(candidate_key))
                cutoff = 1 if maximum <= 6 else 2
                distance = _osa_distance(key, candidate_key, cutoff=cutoff)
                if distance == 0 or distance > cutoff:
                    continue
                if distance == 2 and maximum < 8:
                    continue
                if distance == 2:
                    curated = frozenset((key, candidate_key)) in _CURATED_LOOKALIKE_PAIRS
                    shares_long_edge = (
                        _common_prefix_length(key, candidate_key) >= 5
                        or _common_suffix_length(key, candidate_key) >= 5
                    )
                    if not curated and not shares_long_edge:
                        continue
                candidate_meaning = _meaning_key(_display_meaning(candidate))
                if source_meaning and source_meaning == candidate_meaning:
                    continue
                if source_phrases & _meaning_phrases(_display_meaning(candidate)):
                    continue
                scored.append((distance, abs(len(key) - len(candidate_key)), candidate_id))
            scored.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                    self._by_id[item[2]].headword.casefold(),
                    self._by_id[item[2]].source_order,
                )
            )
            result[word.id] = tuple(
                _related_word(self._by_id[candidate_id])
                for _distance, _length_gap, candidate_id in scored[:8]
            )
        return result

    def root_families(self, word_id: int) -> tuple[RootFamily, ...]:
        return self._root_families_by_word.get(int(word_id), ())

    def lookalikes(self, word_id: int) -> tuple[RelatedWord, ...]:
        return self._lookalikes_by_word.get(int(word_id), ())


def family_word_ids(families: Iterable[RootFamily]) -> set[int]:
    return {
        word.word_id
        for family in families
        for word in family.words
    }
