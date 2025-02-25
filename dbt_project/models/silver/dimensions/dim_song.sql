{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/silver/dim_song',
    external=true
) }}

select distinct 
    concat(artist, '_', song) as song_id,
    song,
    artist,
    duration
from {{ ref('bronze_listen_events') }}
