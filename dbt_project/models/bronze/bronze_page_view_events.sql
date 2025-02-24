{{ config(
    materialized='table',
    file_format='parquet',
    location_root='hdfs://namenode:9000/bronze/page_view_events',
    external=true
) }}

select * from parquet.`hdfs://namenode:9000/output/page_view_events`
