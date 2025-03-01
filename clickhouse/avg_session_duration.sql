CREATE TABLE avg_session_duration
(
    userId String,
    session_date Date,
    session_duration UInt32,
    date DATE
) ENGINE = HDFS('hdfs://namenode:9000/gold/avg_session_duration/gold_avg_session_duration/*/*/*/*', 'Parquet');