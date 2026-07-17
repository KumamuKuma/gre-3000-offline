CONTENT_SCHEMA_VERSION = 1
USER_SCHEMA_VERSION = 2


CONTENT_SCHEMA = """
create table metadata(
  key text primary key,
  value text not null
);
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

