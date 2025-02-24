{{ config(
    materialized='table',
    file_format='parquet',
    external_location='hdfs://namenode:9000/output/auth_events'
) }}

select * from parquet.`hdfs://namenode:9000/output/auth_events`
