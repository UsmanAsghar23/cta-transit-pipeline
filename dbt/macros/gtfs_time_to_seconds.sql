{#
  GTFS times are HH:MM:SS measured from the start of the service day, and can
  exceed 24:00:00 for trips that run past midnight (e.g. 25:30:00). Snowflake's
  TIME type rejects those, so convert to seconds after midnight instead.
#}
{% macro gtfs_time_to_seconds(column) %}
    (
        try_to_number(split_part(trim({{ column }}), ':', 1)) * 3600
        + try_to_number(split_part(trim({{ column }}), ':', 2)) * 60
        + try_to_number(split_part(trim({{ column }}), ':', 3))
    )
{% endmacro %}
