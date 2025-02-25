{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/silver/dim_time',
    external=true
) }}

with time_events as (
  select ts_normalized as timestamp from {{ ref('bronze_auth_events') }}
  union
  select ts_normalized as timestamp from {{ ref('bronze_listen_events') }}
  union
  select ts_normalized as timestamp from {{ ref('bronze_page_view_events') }}
  union
  select ts_normalized as timestamp from {{ ref('bronze_status_change_events') }}
)
select
  cast(unix_timestamp(timestamp) as string) as time_id,
  timestamp,
  year(timestamp) as year,
  month(timestamp) as month,
  day(timestamp) as day,
  hour(timestamp) as hour,
  minute(timestamp) as minute,
  date_format(timestamp, 'E') as weekday
from (select distinct timestamp from time_events) t
