-- GTFS is a full snapshot, not a stream, so each table is replaced wholesale.
-- FORCE = TRUE reloads even though the file name hasn't changed since last week.
{% for file, table in params.tables.items() %}
TRUNCATE TABLE CTA.RAW.{{ table }};

COPY INTO CTA.RAW.{{ table }}
  FROM @CTA.RAW.CTA_LAKE/gtfs/latest/
  FILES = ('{{ file }}.txt.gz')
  FILE_FORMAT = (FORMAT_NAME = 'CTA.RAW.GTFS_CSV')
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  FORCE = TRUE;
{% endfor %}
