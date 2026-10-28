select
    route_id,
    route_short_name,
    -- Some CTA route names carry trailing spaces.
    trim(route_long_name)     as route_long_name,
    try_to_number(route_type) as route_type,
    -- GTFS route_type: 1 = subway/metro ('L' trains), 3 = bus
    case try_to_number(route_type)
        when 1 then 'train'
        when 3 then 'bus'
    end as mode,
    route_color
from {{ source('raw', 'gtfs_routes') }}
