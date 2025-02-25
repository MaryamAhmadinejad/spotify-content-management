{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/gold/avg_session_duration',
    external=true,
    partition_by=['year', 'month', 'day'],
    unique_key='(userId, session_date)'
) }}

with page_views as (
  select
    userId,
    ts_normalized
  from {{ ref('fact_page_view_events') }}
  {% if is_incremental() %}
    where ts_normalized > (
      select coalesce(max(ts_normalized), '1900-01-01') from {{ this }}
    )
  {% endif %}
)
, sessions as (
  select
    userId,
    date(ts_normalized) as session_date,
    unix_timestamp(max(ts_normalized)) - unix_timestamp(min(ts_normalized)) as session_duration,
    year(date(ts_normalized)) as year,
    month(date(ts_normalized)) as month,
    day(date(ts_normalized)) as day
  from page_views
  group by userId, date(ts_normalized)
)
select * from sessions;
