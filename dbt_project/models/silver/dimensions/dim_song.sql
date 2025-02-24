{{ config(materialized='view', file_format='parquet') }}

select distinct 
    concat(artist, '_', song) as song_id,
    song,
    artist,
    duration
from {{ ref('bronze_listen_events') }}
