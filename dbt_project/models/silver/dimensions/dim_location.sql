{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/silver/dim_location',
    external=true
) }}

with location_data as (
  select city, state, lon, lat from {{ ref('bronze_auth_events') }}
  union
  select city, state, lon, lat from {{ ref('bronze_listen_events') }}
  union
  select city, state, lon, lat from {{ ref('bronze_page_view_events') }}
  union
  select city, state, lon, lat from {{ ref('bronze_status_change_events') }}
)
select
  md5(concat(city, state, cast(lon as string), cast(lat as string))) as location_id,
  city,
  state,
  lon,
  lat
from location_data
