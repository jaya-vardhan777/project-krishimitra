"""
Spark Script for Sensor Data Aggregation

This script aggregates IoT sensor data using Apache Spark
for efficient large-scale data processing.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    window, avg, max, min, count, stddev,
    col, to_timestamp, date_format
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
import sys


def create_spark_session():
    """Create Spark session with optimized configuration"""
    return SparkSession.builder \
        .appName("SensorDataAggregation") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.shuffle.partitions", "200") \
        .getOrCreate()


def aggregate_sensor_data(spark, input_path, output_path, window_duration="1 hour"):
    """
    Aggregate sensor data by time windows
    
    Args:
        spark: Spark session
        input_path: S3 input path
        output_path: S3 output path
        window_duration: Aggregation window (e.g., "1 hour", "15 minutes")
    """
    # Define schema for sensor data
    schema = StructType([
        StructField("device_id", StringType(), False),
        StructField("sensor_type", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("value", DoubleType(), False),
        StructField("unit", StringType(), True),
        StructField("location_lat", DoubleType(), True),
        StructField("location_lon", DoubleType(), True)
    ])
    
    # Read sensor data
    df = spark.read \
        .schema(schema) \
        .parquet(input_path)
    
    # Aggregate by time window and sensor type
    aggregated = df.groupBy(
        window("timestamp", window_duration),
        "device_id",
        "sensor_type",
        "location_lat",
        "location_lon"
    ).agg(
        avg("value").alias("avg_value"),
        max("value").alias("max_value"),
        min("value").alias("min_value"),
        stddev("value").alias("stddev_value"),
        count("*").alias("reading_count")
    )
    
    # Add time partitioning columns
    result = aggregated \
        .withColumn("year", date_format(col("window.start"), "yyyy")) \
        .withColumn("month", date_format(col("window.start"), "MM")) \
        .withColumn("day", date_format(col("window.start"), "dd")) \
        .withColumn("hour", date_format(col("window.start"), "HH"))
    
    # Write partitioned output
    result.write \
        .mode("overwrite") \
        .partitionBy("sensor_type", "year", "month", "day") \
        .parquet(output_path)
    
    print(f"Aggregated {df.count()} records into {result.count()} aggregated records")


def main():
    """Main execution function"""
    if len(sys.argv) < 3:
        print("Usage: sensor_data_aggregation.py <input_path> <output_path> [window_duration]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    window_duration = sys.argv[3] if len(sys.argv) > 3 else "1 hour"
    
    spark = create_spark_session()
    
    try:
        aggregate_sensor_data(spark, input_path, output_path, window_duration)
        print("Sensor data aggregation completed successfully")
    except Exception as e:
        print(f"Error during aggregation: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
