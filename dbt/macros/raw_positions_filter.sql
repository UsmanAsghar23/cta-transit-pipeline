{#
  Which raw rows a position model should read on this run.
  - Incremental runs: only rows loaded since the last run, with a 1-hour overlap
    so a slow load can't slip through; the merge on the unique key absorbs the overlap.
  - CI target: only the last few days, since CI always builds from scratch.
#}
{% macro raw_positions_filter() %}
    where true
    {% if is_incremental() %}
        and loaded_at > (select dateadd(hour, -1, max(loaded_at)) from {{ this }})
    {% endif %}
    {% if target.name == 'ci' %}
        and loaded_at >= dateadd(day, -{{ var('ci_lookback_days') }}, sysdate())
    {% endif %}
{% endmacro %}
