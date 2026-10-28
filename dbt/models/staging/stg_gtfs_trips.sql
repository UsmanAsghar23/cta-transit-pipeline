select
    trip_id,
    route_id,
    service_id,
    try_to_number(direction_id) as direction_id,
    direction,
    block_id,
    shape_id,
    -- CTA's scheduling-system trip number; intended join key to live buses for v2.
    schd_trip_id
from {{ source('raw', 'gtfs_trips') }}
