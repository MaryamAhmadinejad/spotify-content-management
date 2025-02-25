{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/silver/fact_status_change_events',
    external=true,
    partition_by=['year', 'month', 'day']
) }}

select
  md5(concat(cast(userId as string), cast(ts as string), auth)) as status_change_id,
  userId,
  cast(from_unixtime(ts/1000) as timestamp) as ts_normalized,
  cast(unix_timestamp(from_unixtime(ts/1000)) as string) as time_id,
  md5(concat(city, state, cast(lon as string), cast(lat as string))) as location_id,
  auth,
  level,
  year(from_unixtime(ts/1000)) as year,
  month(from_unixtime(ts/1000)) as month,
  day(from_unixtime(ts/1000)) as day
from {{ ref('bronze_status_change_events') }}
