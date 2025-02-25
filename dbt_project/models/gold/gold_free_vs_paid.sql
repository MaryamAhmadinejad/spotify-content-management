{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/gold/free_vs_paid_comparison',
    external=true,
    partition_by=['year', 'month', 'day'],
    unique_key='(subscription_level, event_date)'
) }}

with listen_events as (
  select
    userId,
    ts_normalized,
    duration
  from {{ ref('fact_listen_events') }}
  {% if is_incremental() %}
    where ts_normalized > (
      select coalesce(max(ts_normalized), '1900-01-01') from {{ this }}
    )
  {% endif %}
)
, event_dates as (
  select
    userId,
    date(ts_normalized) as event_date,
    duration,
    year(ts_normalized) as year,
    month(ts_normalized) as month,
    day(ts_normalized) as day
  from listen_events
)
select
  u.level as subscription_level,
  ed.event_date,
  count(ed.userId) as total_song_plays,
  avg(ed.duration) as avg_listening_duration,
  ed.year,
  ed.month,
  ed.day
from event_dates ed
join {{ ref('dim_user') }} u on ed.userId = u.userId
group by u.level, ed.event_date, ed.year, ed.month, ed.day
order by ed.event_date;
