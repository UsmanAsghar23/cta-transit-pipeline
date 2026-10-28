{{
    config(
        materialized='incremental',
        unique_key=['vehicle_id', 'recorded_at'],
        incremental_strategy='merge'
    )
}}

with source as (

    select record, loaded_at
    from {{ source('raw', 'bus_positions_raw') }}
    {{ raw_positions_filter() }}

),

parsed as (

    select
        record:vid::string                                         as vehicle_id,
        record:rt::string                                          as route_id,
        record:des::string                                         as destination,
        record:pid::string                                         as pattern_id,
        record:tatripid::string                                    as schedule_trip_id,
        record:tablockid::string                                   as block_id,
        -- Chicago local time, as reported by Bus Tracker. During the November DST
        -- fall-back hour the same wall-clock time occurs twice.
        to_timestamp_ntz(record:tmstmp::string, 'YYYYMMDD HH24:MI:SS') as recorded_at,
        try_to_double(record:lat::string)                          as latitude,
        try_to_double(record:lon::string)                          as longitude,
        try_to_number(record:hdg::string)                          as heading,
        -- Older API versions omit dly unless the bus is delayed, so missing means on time.
        coalesce(record:dly::boolean, false)                       as is_delayed,
        convert_timezone('UTC', to_timestamp_tz(record:ingested_at::string))::timestamp_ntz as ingested_at,
        loaded_at
    from source

)

select *
from parsed
-- A bus that hasn't reported since the last poll appears again with the same
-- timestamp; keep one row per actual position report.
qualify row_number() over (
    partition by vehicle_id, recorded_at
    order by ingested_at desc
) = 1
