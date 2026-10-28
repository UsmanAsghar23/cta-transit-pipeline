{#
  On-time performance by mode, route, and hour (Chicago local time).

  Version 1 (this model): "delayed" means CTA's own flag on each position ping
  (bus `dly`, train `isDly`). It's simple and comparable across modes, but it's
  CTA's definition, not ours.

  Version 2 (planned): compute delay ourselves by comparing actual positions
  against GTFS scheduled times, matching live trips to GTFS trips via
  schedule_trip_id -> schd_trip_id. Note: in a sample of 365 live buses neither
  tatripid nor origtatripno matched schd_trip_id, so v2 needs a different join
  (likely route + block + scheduled start).
#}

with positions as (

    select 'bus' as mode, route_id, vehicle_id, recorded_at, is_delayed
    from {{ ref('stg_bus_positions') }}

    union all

    select 'train' as mode, line as route_id, run_number as vehicle_id, recorded_at, is_delayed
    from {{ ref('stg_train_positions') }}

),

routes as (

    select route_id, route_long_name
    from {{ ref('stg_gtfs_routes') }}

),

hourly as (

    select
        p.mode,
        -- Train lines arrive as 'red', GTFS uses 'Red'; prefer the GTFS spelling.
        coalesce(r.route_id, p.route_id)       as route_id,
        r.route_long_name                      as route_name,
        date_trunc('hour', p.recorded_at)      as hour_start,
        count(*)                               as position_pings,
        count(distinct p.vehicle_id)           as active_vehicles,
        count_if(p.is_delayed)                 as delayed_pings
    from positions as p
    left join routes as r
        on lower(p.route_id) = lower(r.route_id)
    where p.recorded_at is not null
    group by 1, 2, 3, 4

)

select
    mode,
    route_id,
    route_name,
    hour_start,
    hour_start::date                                       as service_date,
    hour(hour_start)                                       as hour_of_day,
    position_pings,
    active_vehicles,
    delayed_pings,
    round(1 - delayed_pings / position_pings, 4)           as on_time_ratio
from hourly
