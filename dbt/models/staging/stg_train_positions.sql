{{
    config(
        materialized='incremental',
        unique_key=['line', 'run_number', 'recorded_at'],
        incremental_strategy='merge'
    )
}}

with source as (

    select record, loaded_at
    from {{ source('raw', 'train_positions_raw') }}
    {{ raw_positions_filter() }}

),

parsed as (

    select
        record:rn::string                                          as run_number,
        lower(record:line::string)                                 as line,
        record:destNm::string                                      as destination,
        record:nextStaId::string                                   as next_station_id,
        record:nextStaNm::string                                   as next_station_name,
        -- The JSON feed uses ISO timestamps (unlike the XML docs); Chicago local time.
        try_to_timestamp_ntz(record:prdt::string, 'YYYY-MM-DD"T"HH24:MI:SS') as recorded_at,
        -- Trains have no GPS; positions are inferred from track circuits, and
        -- CTA sends 0,0 when it can't place a train. Treat that as unknown.
        nullif(try_to_double(record:lat::string), 0)               as latitude,
        nullif(try_to_double(record:lon::string), 0)               as longitude,
        try_to_number(record:heading::string)                      as heading,
        record:isDly::string = '1'                                 as is_delayed,
        convert_timezone('UTC', to_timestamp_tz(record:ingested_at::string))::timestamp_ntz as ingested_at,
        loaded_at
    from source

)

select *
from parsed
qualify row_number() over (
    partition by line, run_number, recorded_at
    order by ingested_at desc
) = 1
