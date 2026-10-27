-- Load the run's hour and the previous hour for one source.
-- COPY remembers which files it already loaded (for 64 days), so overlapping
-- windows, retries, and backfills never create duplicate rows.
{% set run_hour = logical_date or dag_run.run_after %}
{% for hour in [run_hour - macros.timedelta(hours=1), run_hour] %}
COPY INTO CTA.RAW.{{ params.table }} (record, source_file)
  FROM (
    SELECT $1, METADATA$FILENAME
    FROM @CTA.RAW.CTA_LAKE/vehicles/source={{ params.source }}/date={{ hour.strftime('%Y-%m-%d') }}/hour={{ hour.strftime('%H') }}/
  )
  FILE_FORMAT = (FORMAT_NAME = 'CTA.RAW.JSON_GZ');
{% endfor %}
