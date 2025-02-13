from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, to_timestamp, from_unixtime, expr, coalesce, regexp_replace, trim, lower, when, isnan, isnull, year, month, dayofmonth
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, BooleanType
import time
import os
import logging
# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
HDFS_NAMENODE = os.getenv("HDFS_NAMENODE", "namenode:9000")
HDFS_OUTPUT_PATH = f"hdfs://{HDFS_NAMENODE}/output"
CHECKPOINT_LOCATION = f"hdfs://{HDFS_NAMENODE}/checkpoint"
KAFKA_TOPICS = "auth_events,listen_events,page_view_events,status_change_events"  # Add all topics here

time.sleep(30)

# --- Spark Session Setup ---
spark = SparkSession.builder \
    .appName("KafkaToHDFS_MultiTopic") \
    .master("spark://spark-master:7077") \
    .config("spark.sql.catalogImplementation", "hive") \
    .enableHiveSupport() \
    .config("spark.executor.memory", "3g") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# --- Kafka Source ---
df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", KAFKA_TOPICS) \
    .option("startingOffsets", "earliest") \
    .load()

# Extract topic and message (key-value pairs)
kafka_df = df.selectExpr("topic", "CAST(key AS STRING)", "CAST(value AS STRING)")

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_auth_events(df):
    """
    Process the 'auth_events' topic.
    """
    schema_auth_events = StructType([
        StructField("ts", LongType(), True),
        StructField("sessionId", LongType(), True),
        StructField("level", StringType(), True),
        StructField("itemInSession", LongType(), True),
        StructField("city", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("state", StringType(), True),
        StructField("userAgent", StringType(), True),
        StructField("lon", DoubleType(), True),
        StructField("lat", DoubleType(), True),
        StructField("userId", LongType(), True),
        StructField("lastName", StringType(), True),
        StructField("firstName", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("registration", LongType(), True),
        StructField("success", BooleanType(), True),
        StructField("_unparsed", StringType(), True)  # Add this
    ])

    auth_events_df = df.filter(col("topic") == "auth_events") \
        .select(col("key"), from_json(col("value"), schema_auth_events).alias("data")) \
        .select("key", "data.*")

    ###################
    
    #3 Get the expected columns from the schema
    expected_columns = [field.name for field in schema_auth_events]

    # Find columns in the data that are NOT in the schema
    extra_columns = [c for c in auth_events_df.columns if c not in expected_columns and c != 'key']

    # Concatenate extra columns into _unparsed (if any)
    if extra_columns:
        auth_events_df = auth_events_df.withColumn("_unparsed", expr(f"concat_ws(',', {', '.join(extra_columns)})"))
        # Drop the individual extra columns
        auth_events_df = auth_events_df.drop(*extra_columns)
    
    #####################

    # Normalize Timestamp
    auth_events_df = auth_events_df.withColumn("ts_normalized", to_timestamp(from_unixtime(col("ts") / 1000))) \
        .withColumn("year", year(col("ts_normalized"))) \
        .withColumn("month", month(col("ts_normalized"))) \
        .withColumn("day", dayofmonth(col("ts_normalized")))

    # Handle Null Values (Coalesce)
    auth_events_df = auth_events_df \
        .withColumn("success", coalesce(col("success"), expr("false"))) \
        .withColumn("city", coalesce(col("city"), expr("'Unknown'"))) \
        .withColumn("state", coalesce(col("state"), expr("'Unknown'")))

    # String Cleaning
    auth_events_df = auth_events_df \
        .withColumn("userAgent", trim(lower(col("userAgent")))) \
        .withColumn("city", trim(regexp_replace(col("city"), "[^a-zA-Z0-9\\s+]", ""))) \
        .withColumn("state", trim(regexp_replace(col("state"), "[^a-zA-Z]", ""))) \
        .withColumn("lastName", trim(lower(col("lastName")))) \
        .withColumn("firstName", trim(lower(col("firstName")))) \
        .withColumn("gender", when(lower(col("gender")) == 'f', "female")
                            .when(lower(col("gender")) == 'm', "male")
                            .otherwise(None))  # Or a default like "Unknown"

    # Numeric Value Checks
    auth_events_df = auth_events_df.withColumn("lon",
        when(col("lon").isNull() | isnan(col("lon")) | (col("lon") < -180) | (col("lon") > 180), None).otherwise(col("lon"))
    ).withColumn("lat",
        when(col("lat").isNull() | isnan(col("lat")) | (col("lat") < -90) | (col("lat") > 90), None).otherwise(col("lat"))
    )

    # Data Type Consistency
    auth_events_df = auth_events_df \
        .withColumn("sessionId", col("sessionId").cast(LongType())) \
        .withColumn("userId", col("userId").cast(LongType())) \
        .withColumn("success", col("success").cast(BooleanType()))

    # Critical Columns Filtering
    critical_columns = ["ts_normalized", "sessionId", "userId", "success"]
    auth_events_df = auth_events_df.na.drop(subset=critical_columns)

    # Write to HDFS
    try:
        query = auth_events_df \
            .writeStream \
            .outputMode("append") \
            .format("parquet") \
            .option("path", f"{HDFS_OUTPUT_PATH}/auth_events") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/auth_events") \
            .partitionBy("year", "month", "day") \
            .trigger(processingTime='1 minute') \
            .start()
        return query
    except Exception as e:
        logger.error(f"Error processing auth_events: {e}")
        return None  

def process_listen_events(df):
    """
    Process the 'listen_events' topic.
    """
    # Define schema for listen_events
    schema_listen_events = StructType([
        StructField("artist", StringType(), True),
        StructField("song", StringType(), True),
        StructField("duration", DoubleType(), True),
        StructField("ts", LongType(), True),
        StructField("sessionId", LongType(), True),
        StructField("auth", StringType(), True),
        StructField("level", StringType(), True),
        StructField("itemInSession", LongType(), True),
        StructField("city", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("state", StringType(), True),
        StructField("userAgent", StringType(), True),
        StructField("lon", DoubleType(), True),
        StructField("lat", DoubleType(), True),
        StructField("userId", LongType(), True),
        StructField("lastName", StringType(), True),
        StructField("firstName", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("registration", LongType(), True),
        StructField("_unparsed", StringType(), True)
    ])

    listen_events_df = df.filter(col("topic") == "listen_events") \
        .select(col("key"), from_json(col("value"), schema_listen_events).alias("data")) \
        .select("key", "data.*")

    # --- Schema Robustness (listen_events) ---
    expected_columns = [field.name for field in schema_listen_events]
    extra_columns = [c for c in listen_events_df.columns if c not in expected_columns and c != 'key']
    if extra_columns:
        listen_events_df = listen_events_df.withColumn("_unparsed", expr(f"concat_ws(',', {', '.join(extra_columns)})"))
        listen_events_df = listen_events_df.drop(*extra_columns)
    # --- End Schema Robustness ---

    # Normalize Timestamp
    listen_events_df = listen_events_df.withColumn("ts_normalized", to_timestamp(from_unixtime(col("ts") / 1000))) \
        .withColumn("year", year(col("ts_normalized"))) \
        .withColumn("month", month(col("ts_normalized"))) \
        .withColumn("day", dayofmonth(col("ts_normalized")))

    # Handle Null Values (Coalesce)
    listen_events_df = listen_events_df \
        .withColumn("city", coalesce(col("city"), expr("'Unknown'"))) \
        .withColumn("state", coalesce(col("state"), expr("'Unknown'"))) \
        .withColumn("auth", coalesce(col("auth"), expr("'Unknown'"))) \
        .withColumn("level", coalesce(col("level"), expr("'Unknown'")))

    # String Cleaning
    listen_events_df = listen_events_df \
        .withColumn("userAgent", trim(lower(col("userAgent")))) \
        .withColumn("city", trim(regexp_replace(col("city"), "[^a-zA-Z0-9\\s+]", ""))) \
        .withColumn("state", trim(regexp_replace(col("state"), "[^a-zA-Z]", ""))) \
        .withColumn("lastName", trim(lower(col("lastName")))) \
        .withColumn("firstName", trim(lower(col("firstName")))) \
        .withColumn("gender", when(lower(col("gender")) == 'f', "female")
                            .when(lower(col("gender")) == 'm', "male")
                            .otherwise(None))  # Or a default like "Unknown"

    # Numeric Value Checks
    listen_events_df = listen_events_df.withColumn("lon",
        when(col("lon").isNull() | isnan(col("lon")) | (col("lon") < -180) | (col("lon") > 180), None).otherwise(col("lon"))
    ).withColumn("lat",
        when(col("lat").isNull() | isnan(col("lat")) | (col("lat") < -90) | (col("lat") > 90), None).otherwise(col("lat"))
    ).withColumn("duration",
        when(col("duration").isNull() | (col("duration") < 0), None).otherwise(col("duration"))
    )

    # Data Type Consistency
    listen_events_df = listen_events_df \
        .withColumn("sessionId", col("sessionId").cast(LongType())) \
        .withColumn("userId", col("userId").cast(LongType())) \
        .withColumn("duration", col("duration").cast(DoubleType()))

    # Critical Columns Filtering
    critical_columns = ["ts_normalized", "sessionId", "userId", "song", "artist"]
    listen_events_df = listen_events_df.na.drop(subset=critical_columns)

    # Write to HDFS
    # --- Error Handling (listen_events) ---
    try:
        query = listen_events_df \
            .writeStream \
            .outputMode("append") \
            .format("parquet") \
            .option("path", f"{HDFS_OUTPUT_PATH}/listen_events") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/listen_events") \
            .partitionBy("year", "month", "day") \
            .trigger(processingTime='1 minute') \
            .start()
        return query
    except Exception as e:
        logger.error(f"Error processing listen_events: {e}")
        return None
    # --- End Error Handling ---

def process_page_view_events(df):
    """
    Process the 'page_view_events' topic.
    """
    # Define schema for page_view_events
    schema_page_view_events = StructType([
        StructField("ts", LongType(), True),
        StructField("sessionId", LongType(), True),
        StructField("page", StringType(), True),
        StructField("auth", StringType(), True),
        StructField("method", StringType(), True),
        StructField("status", LongType(), True),
        StructField("level", StringType(), True),
        StructField("itemInSession", LongType(), True),
        StructField("city", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("state", StringType(), True),
        StructField("userAgent", StringType(), True),
        StructField("lon", DoubleType(), True),
        StructField("lat", DoubleType(), True),
        StructField("userId", LongType(), True),
        StructField("lastName", StringType(), True),
        StructField("firstName", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("registration", LongType(), True),
        StructField("artist", StringType(), True),
        StructField("song", StringType(), True),
        StructField("duration", DoubleType(), True),
        StructField("_unparsed", StringType(), True)
    ])

    page_view_events_df = df.filter(col("topic") == "page_view_events") \
        .select(col("key"), from_json(col("value"), schema_page_view_events).alias("data")) \
        .select("key", "data.*")

    # --- Schema Robustness (page_view_events) ---
    expected_columns = [field.name for field in schema_page_view_events]
    extra_columns = [c for c in page_view_events_df.columns if c not in expected_columns and c != 'key']
    if extra_columns:
        page_view_events_df = page_view_events_df.withColumn("_unparsed", expr(f"concat_ws(',', {', '.join(extra_columns)})"))
        page_view_events_df = page_view_events_df.drop(*extra_columns)   
        
    # --- End Schema Robustness ---

    # Normalize Timestamp
    page_view_events_df = page_view_events_df.withColumn("ts_normalized", to_timestamp(from_unixtime(col("ts") / 1000))) \
        .withColumn("year", year(col("ts_normalized"))) \
        .withColumn("month", month(col("ts_normalized"))) \
        .withColumn("day", dayofmonth(col("ts_normalized")))

    # Handle Null Values (Coalesce)
    page_view_events_df = page_view_events_df \
        .withColumn("city", coalesce(col("city"), expr("'Unknown'"))) \
        .withColumn("state", coalesce(col("state"), expr("'Unknown'"))) \
        .withColumn("auth", coalesce(col("auth"), expr("'Unknown'"))) \
        .withColumn("level", coalesce(col("level"), expr("'Unknown'"))) \
        .withColumn("method", coalesce(col("method"), expr("'Unknown'"))) \
        .withColumn("page", coalesce(col("page"), expr("'Unknown'")))

    # String Cleaning
    page_view_events_df = page_view_events_df \
        .withColumn("userAgent", trim(lower(col("userAgent")))) \
        .withColumn("city", trim(regexp_replace(col("city"), "[^a-zA-Z0-9\\s+]", ""))) \
        .withColumn("state", trim(regexp_replace(col("state"), "[^a-zA-Z]", ""))) \
        .withColumn("lastName", trim(lower(col("lastName")))) \
        .withColumn("firstName", trim(lower(col("firstName")))) \
        .withColumn("gender", when(lower(col("gender")) == 'f', "female")
                            .when(lower(col("gender")) == 'm', "male")
                            .otherwise(None))  # Or a default like "Unknown"

    # Numeric Value Checks
    page_view_events_df = page_view_events_df.withColumn("lon",
        when(col("lon").isNull() | isnan(col("lon")) | (col("lon") < -180) | (col("lon") > 180), None).otherwise(col("lon"))
    ).withColumn("lat",
        when(col("lat").isNull() | isnan(col("lat")) | (col("lat") < -90) | (col("lat") > 90), None).otherwise(col("lat"))
    ).withColumn("duration",
        when(col("duration").isNull() | (col("duration") < 0), None).otherwise(col("duration"))
    ).withColumn("status",
        when(col("status").isNull() | (col("status") < 100) | (col("status") > 599), None).otherwise(col("status"))
    )

    # Data Type Consistency
    page_view_events_df = page_view_events_df \
        .withColumn("sessionId", col("sessionId").cast(LongType())) \
        .withColumn("userId", col("userId").cast(LongType())) \
        .withColumn("duration", col("duration").cast(DoubleType())) \
        .withColumn("status", col("status").cast(LongType()))

    # Critical Columns Filtering
    critical_columns = ["ts_normalized", "sessionId", "userId", "page", "method", "status"]
    page_view_events_df = page_view_events_df.na.drop(subset=critical_columns)

    # Write to HDFS
    # --- Error Handling (page_view_events) ---
    try:
        query = page_view_events_df \
            .writeStream \
            .outputMode("append") \
            .format("parquet") \
            .option("path", f"{HDFS_OUTPUT_PATH}/page_view_events") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/page_view_events") \
            .partitionBy("year", "month", "day") \
            .trigger(processingTime='1 minute') \
            .start()
        return query
    except Exception as e:
        logger.error(f"Error processing page_view_events: {e}")
        return None
    # --- End Error Handling ---

def process_status_change_events(df):
    """
    Process the 'status_change_events' topic.
    """
    # Define schema for status_change_events
    schema_status_change_events = StructType([
        StructField("ts", LongType(), True),
        StructField("sessionId", LongType(), True),
        StructField("auth", StringType(), True),
        StructField("level", StringType(), True),
        StructField("itemInSession", LongType(), True),
        StructField("city", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("state", StringType(), True),
        StructField("userAgent", StringType(), True),
        StructField("lon", DoubleType(), True),
        StructField("lat", DoubleType(), True),
        StructField("userId", LongType(), True),
        StructField("lastName", StringType(), True),
        StructField("firstName", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("registration", LongType(), True),
        StructField("_unparsed", StringType(), True)
    ])

    status_change_events_df = df.filter(col("topic") == "status_change_events") \
        .select(col("key"), from_json(col("value"), schema_status_change_events).alias("data")) \
        .select("key", "data.*")

    # --- Schema Robustness (status_change_events) ---
    expected_columns = [field.name for field in schema_status_change_events]
    extra_columns = [c for c in status_change_events_df.columns if c not in expected_columns and c != 'key']
    if extra_columns:
        status_change_events_df = status_change_events_df.withColumn("_unparsed", expr(f"concat_ws(',', {', '.join(extra_columns)})"))
        status_change_events_df = status_change_events_df.drop(*extra_columns)
    # --- End Schema Robustness ---

    # Normalize Timestamp
    status_change_events_df = status_change_events_df.withColumn("ts_normalized", to_timestamp(from_unixtime(col("ts") / 1000))) \
        .withColumn("year", year(col("ts_normalized"))) \
        .withColumn("month", month(col("ts_normalized"))) \
        .withColumn("day", dayofmonth(col("ts_normalized")))

    # Handle Null Values (Coalesce)
    status_change_events_df = status_change_events_df \
        .withColumn("city", coalesce(col("city"), expr("'Unknown'"))) \
        .withColumn("state", coalesce(col("state"), expr("'Unknown'"))) \
        .withColumn("auth", coalesce(col("auth"), expr("'Unknown'"))) \
        .withColumn("level", coalesce(col("level"), expr("'Unknown'")))

    # String Cleaning
    status_change_events_df = status_change_events_df \
        .withColumn("userAgent", trim(lower(col("userAgent")))) \
        .withColumn("city", trim(regexp_replace(col("city"), "[^a-zA-Z0-9\\s+]", ""))) \
        .withColumn("state", trim(regexp_replace(col("state"), "[^a-zA-Z]", ""))) \
        .withColumn("lastName", trim(lower(col("lastName")))) \
        .withColumn("firstName", trim(lower(col("firstName")))) \
        .withColumn("gender", when(lower(col("gender")) == 'f', "female")
                            .when(lower(col("gender")) == 'm', "male")
                            .otherwise(None))  # Or a default like "Unknown"

    # Numeric Value Checks
    status_change_events_df = status_change_events_df.withColumn("lon",
        when(col("lon").isNull() | isnan(col("lon")) | (col("lon") < -180) | (col("lon") > 180), None).otherwise(col("lon"))
    ).withColumn("lat",
        when(col("lat").isNull() | isnan(col("lat")) | (col("lat") < -90) | (col("lat") > 90), None).otherwise(col("lat"))
    )

    # Data Type Consistency
    status_change_events_df = status_change_events_df \
        .withColumn("sessionId", col("sessionId").cast(LongType())) \
        .withColumn("userId", col("userId").cast(LongType()))

    # Critical Columns Filtering
    critical_columns = ["ts_normalized", "sessionId", "userId", "auth", "level"]
    status_change_events_df = status_change_events_df.na.drop(subset=critical_columns)

    # Write to HDFS
    # --- Error Handling (status_change_events) ---
    try:
        query = status_change_events_df \
            .writeStream \
            .outputMode("append") \
            .format("parquet") \
            .option("path", f"{HDFS_OUTPUT_PATH}/status_change_events") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/status_change_events") \
            .partitionBy("year", "month", "day") \
            .trigger(processingTime='1 minute') \
            .start()
        return query
    except Exception as e:
        logger.error(f"Error processing status_change_events: {e}")
        return None
    # --- End Error Handling ---

queries = [
    process_auth_events(kafka_df),
    process_listen_events(kafka_df),
    process_page_view_events(kafka_df),
    process_status_change_events(kafka_df)
]

# Await Termination for All Queries
for query in queries:
    if query:
        query.awaitTermination()
