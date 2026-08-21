export type DictionarySenseWithTranslation = {
  translation: string;
  part_of_speech?: string;
};

export type DisplayDictionarySense<T extends DictionarySenseWithTranslation> = {
  sense: T;
  displayTranslation: string;
};

export type DisplayDictionaryEntry<T extends DictionarySenseWithTranslation> = {
  senses: DisplayDictionarySense<T>[];
  summaryTranslation: string;
};

const PART_OF_SPEECH_PREFIX = /^(?:(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr|s|r)\.)\s*/i;

const TRANSLATION_POSITIONS: Record<string, string> = {
  v: "v",
  vt: "v",
  vi: "v",
  aux: "v",
  a: "adj",
  adj: "adj",
  s: "adj",
  ad: "adv",
  adv: "adv",
  r: "adv",
};

/** Return a stable comparison key for a Chinese translation. */
export function dictionaryTranslationKey(value: string): string {
  return value
    .normalize("NFKC")
    .split(/\r?\n/)
    .map((line) => line.trim().replace(PART_OF_SPEECH_PREFIX, "").trim())
    .filter(Boolean)
    .join("\n")
    .replace(/\s+/g, " ")
    .replace(/\s*([,;:])\s*/g, "$1")
    .toLocaleLowerCase();
}

function dictionaryTranslationPos(value: string): string {
  const text = value.trim();
  const prefixMatch = text.match(PART_OF_SPEECH_PREFIX);
  if (prefixMatch) {
    const raw = prefixMatch[0].trim().replace(/\.$/, "").toLocaleLowerCase();
    return TRANSLATION_POSITIONS[raw] ?? raw;
  }
  const bareMatch = text.match(/^(n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr|s|r)\.?$/i);
  if (!bareMatch) return "";
  const raw = bareMatch[1].toLocaleLowerCase();
  return TRANSLATION_POSITIONS[raw] ?? raw;
}

function removeDisplayedTranslations(
  summary: string,
  displayedAllKeys: Set<string>,
  displayedWildcardKeys: Set<string>,
  displayedPosKeys: Set<string>,
): string {
  const seenSummaryKeys = new Set<string>();
  const isDisplayed = (line: string, part?: string): boolean => {
    const summaryPos = dictionaryTranslationPos(line);
    const key = dictionaryTranslationKey(part ?? line);
    if (!key) return false;
    if (summaryPos) {
      return displayedWildcardKeys.has(key)
        || displayedPosKeys.has(`${summaryPos}\u0000${key}`);
    }
    // A summary line without a POS cannot disambiguate. Preserve the
    // historical de-duplication behavior and hide it when any precise sense
    // already supplies the same Chinese text.
    return displayedAllKeys.has(key);
  };
  const remainingLines: string[] = [];
  for (const rawLine of summary.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (isDisplayed(line)) continue;

    const prefixMatch = line.match(PART_OF_SPEECH_PREFIX);
    const prefix = prefixMatch?.[0] ?? "";
    const body = line.slice(prefix.length).trim();
    const parts = body.split(/[,，;；、]/).map((part) => part.trim()).filter(Boolean);
    if (parts.length > 1) {
      const seenLineParts = new Set<string>();
      const remainingParts = parts.filter((part) => {
        const key = dictionaryTranslationKey(part);
        const summaryKey = `${dictionaryTranslationPos(line)}\u0000${key}`;
        if (
          !key
          || isDisplayed(line, part)
          || seenLineParts.has(key)
          || seenSummaryKeys.has(summaryKey)
        ) return false;
        seenLineParts.add(key);
        seenSummaryKeys.add(summaryKey);
        return true;
      });
      if (!remainingParts.length) continue;
      remainingLines.push(`${prefix}${remainingParts.join("，")}`);
      continue;
    }
    const key = dictionaryTranslationKey(body);
    const summaryKey = `${dictionaryTranslationPos(line)}\u0000${key}`;
    if (key && seenSummaryKeys.has(summaryKey)) continue;
    if (key) seenSummaryKeys.add(summaryKey);
    remainingLines.push(line);
  }
  return remainingLines.join("\n");
}

/**
 * Keep every English sense and example, while showing duplicate Chinese text
 * only once. The broad entry-level translation is trimmed only for meanings
 * already shown by a sense card; unmatched ECDICT meanings remain available.
 */
export function dictionaryEntryForDisplay<T extends DictionarySenseWithTranslation>(
  senses: readonly T[],
  summaryTranslation: string,
): DisplayDictionaryEntry<T> {
  const firstSenseByTranslation = new Map<string, number>();
  const displayedSenses = senses.map((sense, senseIndex) => {
    const parts = sense.translation
      .split(/[,，;；、]|\r?\n/)
      .map((part) => part.trim())
      .filter(Boolean);
    const localKeys = new Set<string>();
    const newParts: string[] = [];
    const repeatedSenses: number[] = [];
    for (const part of parts) {
      const key = dictionaryTranslationKey(part);
      if (!key || localKeys.has(key)) continue;
      localKeys.add(key);
      const previousSense = firstSenseByTranslation.get(key);
      if (previousSense === undefined) {
        firstSenseByTranslation.set(key, senseIndex + 1);
        newParts.push(part);
      } else if (!repeatedSenses.includes(previousSense)) {
        repeatedSenses.push(previousSense);
      }
    }
    const displayValues: string[] = [];
    if (newParts.length) {
      displayValues.push(
        !repeatedSenses.length && newParts.length === parts.length
          ? sense.translation.trim()
          : newParts.join("；"),
      );
    }
    if (repeatedSenses.length) {
      displayValues.push(`同译见义项 ${repeatedSenses.join("、")}`);
    }
    const displayTranslation = displayValues.join("\n");
    return { sense, displayTranslation };
  });
  const summaryHiddenAllKeys = new Set<string>();
  const summaryHiddenWildcardKeys = new Set<string>();
  const summaryHiddenPosKeys = new Set<string>();
  for (const { sense } of displayedSenses) {
    const senseHasPos = sense.part_of_speech !== undefined;
    const sensePos = dictionaryTranslationPos(sense.part_of_speech ?? "");
    for (const rawLine of sense.translation.split(/\r?\n/)) {
      const line = rawLine.trim();
      const linePos = dictionaryTranslationPos(line) || sensePos;
      const body = line.replace(PART_OF_SPEECH_PREFIX, "").trim();
      for (const part of body.split(/[,，;；、]/)) {
        const key = dictionaryTranslationKey(part);
        if (!key) continue;
        summaryHiddenAllKeys.add(key);
        if (linePos && senseHasPos) {
          summaryHiddenPosKeys.add(`${linePos}\u0000${key}`);
        } else if (!senseHasPos) {
          // Legacy callers may omit part_of_speech. Treat those senses as a
          // wildcard so their existing summary de-duplication remains stable.
          summaryHiddenWildcardKeys.add(key);
        }
      }
    }
  }
  return {
    senses: displayedSenses,
    summaryTranslation: removeDisplayedTranslations(
      summaryTranslation,
      summaryHiddenAllKeys,
      summaryHiddenWildcardKeys,
      summaryHiddenPosKeys,
    ),
  };
}

export function dictionarySensesForDisplay<T extends DictionarySenseWithTranslation>(
  senses: readonly T[],
): DisplayDictionarySense<T>[] {
  return dictionaryEntryForDisplay(senses, "").senses;
}
