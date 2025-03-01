CREATE TABLE free_vs_paid_comparison
(
    subscription_level String,
    event_date Date,
    total_song_plays UInt32,
    avg_listening_duration Float64,
    date DATE
) ENGINE = HDFS('hdfs://namenode:9000/gold/free_vs_paid_comparison/gold_free_vs_paid/*/*/*/*', 'Parquet');