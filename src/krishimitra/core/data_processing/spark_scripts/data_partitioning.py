"""
Spark Script for Data Partitioning

This script repartitions agricultural data for optimal
storage and query performance.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, date_format, year, month, dayofmonth
import sys


def create_spark_session():
    """Create Spark session with optimized configuration"""
    return SparkSession.builder \
        .appName("DataPartitioning") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.files.maxPartitionBytes", "134217728") \
        .getOrCreate()


def partition_data(spark, input_path, output_path, partition_columns):
    """
    Partition data by specified columns
    
    Args:
        spark: Spark session
        input_path: S3 input path
        output_path: S3 output path
        partition_columns: List of columns to partition by
    """
    # Read input data
    df = spark.read.parquet(input_path)
    
    # Add time-based partition columns if timestamp exists
    if "timestamp" in df.columns:
        df = df \
            .withColumn("year", year(col("timestamp"))) \
            .withColumn("month", month(col("timestamp"))) \
            .withColumn("day", dayofmonth(col("timestamp")))
    
    # Optimize partition size
    num_partitions = max(df.rdd.getNumPartitions() // 2, 1)
    df = df.repartition(num_partitions, *partition_columns)
    
    # Write partitioned data
    df.write \
        .mode("overwrite") \
        .partitionBy(*partition_columns) \
        .parquet(output_path)
    
    print(f"Partitioned {df.count()} records by {', '.join(partition_columns)}")


def main():
    """Main execution function"""
    if len(sys.argv) < 4:
        print("Usage: data_partitioning.py <input_path> <output_path> <partition_columns>")
        print("Example: data_partitioning.py s3://input/ s3://output/ year,month,sensor_type")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    partition_columns = sys.argv[3].split(',')
    
    spark = create_spark_session()
    
    try:
        partition_data(spark, input_path, output_path, partition_columns)
        print("Data partitioning completed successfully")
    except Exception as e:
        print(f"Error during partitioning: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
