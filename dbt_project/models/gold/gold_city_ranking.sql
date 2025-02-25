{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/gold/city_ranking_active_users',
    external=true,
    partition_by=['year', 'month', 'day'],
    unique_key='(city, state, event_date)'
) }}

with active_auth as (
  select
    userId,
    ts_normalized
  from {{ ref('fact_auth_events') }}
  where success = true
  {% if is_incremental() %}
    and ts_normalized > (
      select coalesce(max(ts_normalized), '1900-01-01') from {{ this }}
    )
  {% endif %}
)
, user_dates as (
  select
    userId,
    date(ts_normalized) as event_date,
    year(ts_normalized) as year,
    month(ts_normalized) as month,
    day(ts_normalized) as day
  from active_auth
)
select
  u.city,
  u.state,
  ud.event_date,
  count(distinct ud.userId) as active_user_count,
  ud.year,
  ud.month,
  ud.day
from user_dates ud
join {{ ref('dim_user') }} u on ud.userId = u.userId
group by u.city, u.state, ud.event_date, ud.year, ud.month, ud.day
order by active_user_count desc;
