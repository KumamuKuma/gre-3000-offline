export type DictionarySenseWithTranslation = {
  translation: string;
};

export type DisplayDictionarySense<T extends DictionarySenseWithTranslation> = {
  sense: T;
  displayTranslation: string;
};

export type DisplayDictionaryEntry<T extends DictionarySenseWithTranslation> = {
  senses: DisplayDictionarySense<T>[];
  summaryTranslation: string;
};

const PART_OF_SPEECH_PREFIX = /^(?:(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr)\.)\s*/i;

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

function removeDisplayedTranslations(summary: string, displayedKeys: Set<string>): string {
  const remainingLines: string[] = [];
  for (const rawLine of summary.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (displayedKeys.has(dictionaryTranslationKey(line))) continue;

    const prefixMatch = line.match(PART_OF_SPEECH_PREFIX);
    const prefix = prefixMatch?.[0] ?? "";
    const body = line.slice(prefix.length).trim();
    const parts = body.split(/[,，;；、]/).map((part) => part.trim()).filter(Boolean);
    if (parts.length > 1) {
      const remainingParts = parts.filter(
        (part) => !displayedKeys.has(dictionaryTranslationKey(part)),
      );
      if (!remainingParts.length) continue;
      remainingLines.push(`${prefix}${remainingParts.join("，")}`);
      continue;
    }
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
  const seenTranslations = new Set<string>();
  const displayedSenses = senses.map((sense) => {
    const key = dictionaryTranslationKey(sense.translation);
    const displayTranslation = key && !seenTranslations.has(key)
      ? sense.translation.trim()
      : "";
    if (key) seenTranslations.add(key);
    return { sense, displayTranslation };
  });
  const summaryHiddenKeys = new Set(seenTranslations);
  for (const { displayTranslation } of displayedSenses) {
    for (const rawLine of displayTranslation.split(/\r?\n/)) {
      const body = rawLine.trim().replace(PART_OF_SPEECH_PREFIX, "").trim();
      for (const part of body.split(/[,，;；、]/)) {
        const key = dictionaryTranslationKey(part);
        if (key) summaryHiddenKeys.add(key);
      }
    }
  }
  return {
    senses: displayedSenses,
    summaryTranslation: removeDisplayedTranslations(summaryTranslation, summaryHiddenKeys),
  };
}

export function dictionarySensesForDisplay<T extends DictionarySenseWithTranslation>(
  senses: readonly T[],
): DisplayDictionarySense<T>[] {
  return dictionaryEntryForDisplay(senses, "").senses;
}
