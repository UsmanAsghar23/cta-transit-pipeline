select
    stop_id,
    stop_code,
    stop_name,
    try_to_double(stop_lat)          as latitude,
    try_to_double(stop_lon)          as longitude,
    try_to_number(location_type)     as location_type,
    nullif(parent_station, '')       as parent_station_id
from {{ source('raw', 'gtfs_stops') }}
