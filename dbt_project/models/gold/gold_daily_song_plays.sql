{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/gold/daily_song_plays',
    external=true,
    partition_by=['year', 'month', 'day'],
    unique_key='(userId, event_date)'
) }}

with filtered_listens as (
  select
    userId,
    ts_normalized
  from {{ ref('fact_listen_events') }}
  {% if is_incremental() %}
    where ts_normalized > (
      select coalesce(max(ts_normalized), '1900-01-01') from {{ this }}
    )
  {% endif %}
)
, aggregated as (
  select
    userId,
    date(ts_normalized) as event_date,
    count(*) as total_song_plays,
    year(ts_normalized) as year,
    month(ts_normalized) as month,
    day(ts_normalized) as day
  from filtered_listens
  group by userId, date(ts_normalized), year(ts_normalized), month(ts_normalized), day(ts_normalized)
)
select * from aggregated;
