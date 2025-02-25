{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/silver/dim_user',
    external=true
) }}

with all_users as (
    select 
        userId, firstName, lastName, gender, city, state, zip, registration, level
    from {{ ref('bronze_auth_events') }}
    union
    select 
        userId, firstName, lastName, gender, city, state, zip, registration, level
    from {{ ref('bronze_listen_events') }}
    union
    select 
        userId, firstName, lastName, gender, city, state, zip, registration, level
    from {{ ref('bronze_page_view_events') }}
)
select
    userId,
    max(firstName) as first_name,
    max(lastName) as last_name,
    max(gender) as gender,
    max(city) as city,
    max(state) as state,
    max(zip) as zip,
    min(registration) as registration,
    max(level) as level
from all_users
group by userId
