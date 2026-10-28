select
    trip_id,
    stop_id,
    try_to_number(stop_sequence)                      as stop_sequence,
    arrival_time,
    departure_time,
    {{ gtfs_time_to_seconds('arrival_time') }}        as arrival_seconds,
    {{ gtfs_time_to_seconds('departure_time') }}      as departure_seconds,
    stop_headsign
from {{ source('raw', 'gtfs_stop_times') }}
