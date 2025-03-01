CREATE TABLE city_ranking_active_users
(
    city String,
    state String,
    event_date Date,
    active_user_count UInt64,
    date DATE
) ENGINE = HDFS('hdfs://namenode:9000/gold/city_ranking_active_users/gold_city_ranking/*/*/*/*', 'Parquet');