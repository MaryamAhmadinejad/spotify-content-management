{{ config(
    materialized='table',
    file_format='parquet',
    external_location='hdfs://namenode:9000/output/status_change_events'
) }}

select * from parquet.`hdfs://namenode:9000/output/status_change_events`
