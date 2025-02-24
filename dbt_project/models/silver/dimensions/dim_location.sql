{{ config(materialized='view', file_format='parquet') }}

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
