CREATE TABLE daily_song_plays
(
    userId String,
    event_date Date,
    total_song_plays UInt32,
    date DATE
) ENGINE = HDFS('hdfs://namenode:9000/gold/daily_song_plays/gold_daily_song_plays/*/*/*/*', 'Parquet');