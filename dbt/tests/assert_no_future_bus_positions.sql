-- A bus can't report from the future. Anything over an hour ahead of Chicago's
-- current time points to a timestamp-parsing or time zone bug.
select
    vehicle_id,
    recorded_at
from {{ ref('stg_bus_positions') }}
where recorded_at > dateadd(
    hour, 1, convert_timezone('America/Chicago', current_timestamp())::timestamp_ntz
)
