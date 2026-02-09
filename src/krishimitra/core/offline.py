"""
Offline mode and data synchronization for KrishiMitra platform.

This module provides offline data storage, retrieval, and automatic synchronization
when connectivity is restored.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict

from .utils.caching import SQLiteCache
from .utils.compression import DataCompressor, CompressionAlgorithm


class SyncStatus(Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class DataType(Enum):
    """Types of data that can be stored offline."""
    RECOMMENDATION = "recommendation"
    WEATHER_DATA = "weather_data"
    SOIL_DATA = "soil_data"
    MARKET_PRICE = "market_price"
    FARMER_PROFILE = "farmer_profile"
    CONVERSATION = "conversation"
    FEEDBACK = "feedback"


@dataclass
class OfflineRecord:
    """Represents an offline data record."""
    id: str
    data_type: DataType
    data: Dict[str, Any]
    created_at: datetime
    modified_at: datetime
    sync_status: SyncStatus
    sync_attempts: int = 0
    last_sync_attempt: Optional[datetime] = None
    error_message: Optional[str] = None


class OfflineStorage:
    """
    Offline data storage using SQLite.
    
    Provides persistent local storage for critical agricultural data
    when internet connectivity is unavailable.
    """
    
    def __init__(self, db_path: Union[str, Path] = "offline_data.db"):
        """
        Initialize offline storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.compressor = DataCompressor(algorithm=CompressionAlgorithm.GZIP)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Main offline data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_data (
                id TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                data BLOB NOT NULL,
                created_at REAL NOT NULL,
                modified_at REAL NOT NULL,
                sync_status TEXT NOT NULL,
                sync_attempts INTEGER DEFAULT 0,
                last_sync_attempt REAL,
                error_message TEXT
            )
        """)
        
        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_type 
            ON offline_data(data_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_status 
            ON offline_data(sync_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_modified_at 
            ON offline_data(modified_at)
        """)
        
        # Sync queue table for pending operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                FOREIGN KEY (record_id) REFERENCES offline_data(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority 
            ON sync_queue(priority DESC, created_at ASC)
        """)
        
        conn.commit()
        conn.close()
    
    def store(
        self,
        record_id: str,
        data_type: DataType,
        data: Dict[str, Any]
    ) -> bool:
        """
        Store data offline.
        
        Args:
            record_id: Unique record identifier
            data_type: Type of data
            data: Data to store
            
        Returns:
            True if successful
        """
        try:
            # Compress data
            json_str = json.dumps(data, separators=(',', ':'))
            compressed_data = self.compressor.compress_bytes(json_str.encode('utf-8'))
            
            now = datetime.utcnow().timestamp()
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO offline_data
                (id, data_type, data, created_at, modified_at, sync_status, sync_attempts)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                record_id,
                data_type.value,
                compressed_data,
                now,
                now,
                SyncStatus.PENDING.value
            ))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception:
            return False
    
    def retrieve(
        self,
        record_id: str
    ) -> Optional[OfflineRecord]:
        """
        Retrieve data from offline storage.
        
        Args:
            record_id: Record identifier
            
        Returns:
            OfflineRecord or None if not found
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, data_type, data, created_at, modified_at, 
                   sync_status, sync_attempts, last_sync_attempt, error_message
            FROM offline_data
            WHERE id = ?
        """, (record_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        # Decompress data
        compressed_data = row[2]
        decompressed_data = self.compressor.decompress_bytes(compressed_data)
        data = json.loads(decompressed_data.decode('utf-8'))
        
        return OfflineRecord(
            id=row[0],
            data_type=DataType(row[1]),
            data=data,
            created_at=datetime.fromtimestamp(row[3]),
            modified_at=datetime.fromtimestamp(row[4]),
            sync_status=SyncStatus(row[5]),
            sync_attempts=row[6],
            last_sync_attempt=datetime.fromtimestamp(row[7]) if row[7] else None,
            error_message=row[8]
        )
    
    def list_by_type(
        self,
        data_type: DataType,
        limit: Optional[int] = None
    ) -> List[OfflineRecord]:
        """
        List all records of a specific type.
        
        Args:
            data_type: Type of data to list
            limit: Maximum number of records to return
            
        Returns:
            List of offline records
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = """
            SELECT id, data_type, data, created_at, modified_at,
                   sync_status, sync_attempts, last_sync_attempt, error_message
            FROM offline_data
            WHERE data_type = ?
            ORDER BY modified_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (data_type.value,))
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            # Decompress data
            compressed_data = row[2]
            decompressed_data = self.compressor.decompress_bytes(compressed_data)
            data = json.loads(decompressed_data.decode('utf-8'))
            
            records.append(OfflineRecord(
                id=row[0],
                data_type=DataType(row[1]),
                data=data,
                created_at=datetime.fromtimestamp(row[3]),
                modified_at=datetime.fromtimestamp(row[4]),
                sync_status=SyncStatus(row[5]),
                sync_attempts=row[6],
                last_sync_attempt=datetime.fromtimestamp(row[7]) if row[7] else None,
                error_message=row[8]
            ))
        
        return records
    
    def delete(self, record_id: str) -> bool:
        """
        Delete a record from offline storage.
        
        Args:
            record_id: Record identifier
            
        Returns:
            True if deleted
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM offline_data WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            return deleted
        except Exception:
            return False
    
    def get_pending_sync_records(
        self,
        limit: Optional[int] = None
    ) -> List[OfflineRecord]:
        """
        Get records pending synchronization.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of pending records
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = """
            SELECT id, data_type, data, created_at, modified_at,
                   sync_status, sync_attempts, last_sync_attempt, error_message
            FROM offline_data
            WHERE sync_status = ?
            ORDER BY modified_at ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (SyncStatus.PENDING.value,))
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            # Decompress data
            compressed_data = row[2]
            decompressed_data = self.compressor.decompress_bytes(compressed_data)
            data = json.loads(decompressed_data.decode('utf-8'))
            
            records.append(OfflineRecord(
                id=row[0],
                data_type=DataType(row[1]),
                data=data,
                created_at=datetime.fromtimestamp(row[3]),
                modified_at=datetime.fromtimestamp(row[4]),
                sync_status=SyncStatus(row[5]),
                sync_attempts=row[6],
                last_sync_attempt=datetime.fromtimestamp(row[7]) if row[7] else None,
                error_message=row[8]
            ))
        
        return records
    
    def update_sync_status(
        self,
        record_id: str,
        status: SyncStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update synchronization status of a record.
        
        Args:
            record_id: Record identifier
            status: New sync status
            error_message: Error message if sync failed
            
        Returns:
            True if updated
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            now = datetime.utcnow().timestamp()
            
            cursor.execute("""
                UPDATE offline_data
                SET sync_status = ?,
                    last_sync_attempt = ?,
                    sync_attempts = sync_attempts + 1,
                    error_message = ?
                WHERE id = ?
            """, (status.value, now, error_message, record_id))
            
            updated = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            return updated
        except Exception:
            return False


class DataSynchronizer:
    """
    Automatic data synchronization when connectivity is restored.
    
    Handles conflict resolution and retry logic for failed synchronizations.
    """
    
    def __init__(
        self,
        offline_storage: OfflineStorage,
        max_retries: int = 3,
        retry_delay_seconds: int = 60
    ):
        """
        Initialize data synchronizer.
        
        Args:
            offline_storage: Offline storage instance
            max_retries: Maximum number of sync retry attempts
            retry_delay_seconds: Delay between retry attempts
        """
        self.offline_storage = offline_storage
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
    
    async def sync_pending_records(
        self,
        sync_callback: callable
    ) -> Dict[str, Any]:
        """
        Synchronize all pending records.
        
        Args:
            sync_callback: Async function to sync a single record
                          Should accept (record_id, data_type, data) and return bool
            
        Returns:
            Sync results summary
        """
        pending_records = self.offline_storage.get_pending_sync_records()
        
        results = {
            'total': len(pending_records),
            'successful': 0,
            'failed': 0,
            'conflicts': 0,
            'errors': []
        }
        
        for record in pending_records:
            # Skip if max retries exceeded
            if record.sync_attempts >= self.max_retries:
                results['failed'] += 1
                continue
            
            # Check if enough time has passed since last attempt
            if record.last_sync_attempt:
                time_since_last = datetime.utcnow() - record.last_sync_attempt
                if time_since_last.total_seconds() < self.retry_delay_seconds:
                    continue
            
            # Update status to in progress
            self.offline_storage.update_sync_status(
                record.id,
                SyncStatus.IN_PROGRESS
            )
            
            try:
                # Attempt synchronization
                success = await sync_callback(
                    record.id,
                    record.data_type,
                    record.data
                )
                
                if success:
                    self.offline_storage.update_sync_status(
                        record.id,
                        SyncStatus.COMPLETED
                    )
                    results['successful'] += 1
                else:
                    self.offline_storage.update_sync_status(
                        record.id,
                        SyncStatus.FAILED,
                        "Sync callback returned False"
                    )
                    results['failed'] += 1
            
            except Exception as e:
                error_msg = str(e)
                self.offline_storage.update_sync_status(
                    record.id,
                    SyncStatus.FAILED,
                    error_msg
                )
                results['failed'] += 1
                results['errors'].append({
                    'record_id': record.id,
                    'error': error_msg
                })
        
        return results
    
    def resolve_conflict(
        self,
        local_data: Dict[str, Any],
        remote_data: Dict[str, Any],
        strategy: str = "remote_wins"
    ) -> Dict[str, Any]:
        """
        Resolve data conflicts between local and remote versions.
        
        Args:
            local_data: Local version of data
            remote_data: Remote version of data
            strategy: Conflict resolution strategy
                     ('local_wins', 'remote_wins', 'merge')
            
        Returns:
            Resolved data
        """
        if strategy == "local_wins":
            return local_data
        elif strategy == "remote_wins":
            return remote_data
        elif strategy == "merge":
            # Simple merge: remote wins for conflicts, keep unique fields
            merged = remote_data.copy()
            for key, value in local_data.items():
                if key not in merged:
                    merged[key] = value
            return merged
        else:
            raise ValueError(f"Unknown conflict resolution strategy: {strategy}")
    
    def cleanup_synced_records(self, older_than_days: int = 7) -> int:
        """
        Clean up successfully synced records older than specified days.
        
        Args:
            older_than_days: Remove records older than this many days
            
        Returns:
            Number of records removed
        """
        cutoff_time = datetime.utcnow() - timedelta(days=older_than_days)
        
        conn = sqlite3.connect(str(self.offline_storage.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM offline_data
            WHERE sync_status = ? AND modified_at < ?
        """, (SyncStatus.COMPLETED.value, cutoff_time.timestamp()))
        
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted


class OfflineRecommendationEngine:
    """
    Offline-capable recommendation engine with cached models.
    
    Provides basic recommendations when internet connectivity is unavailable.
    """
    
    def __init__(self, offline_storage: OfflineStorage):
        """
        Initialize offline recommendation engine.
        
        Args:
            offline_storage: Offline storage instance
        """
        self.offline_storage = offline_storage
        self.cached_recommendations: Dict[str, List[Dict[str, Any]]] = {}
    
    def cache_recommendations(
        self,
        farmer_id: str,
        recommendations: List[Dict[str, Any]]
    ):
        """
        Cache recommendations for offline access.
        
        Args:
            farmer_id: Farmer identifier
            recommendations: List of recommendations
        """
        self.cached_recommendations[farmer_id] = recommendations
        
        # Also store in offline storage
        for rec in recommendations:
            self.offline_storage.store(
                record_id=rec.get('id', f"{farmer_id}_{rec.get('title', 'rec')}"),
                data_type=DataType.RECOMMENDATION,
                data=rec
            )
    
    def get_offline_recommendations(
        self,
        farmer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get cached recommendations for offline use.
        
        Args:
            farmer_id: Farmer identifier
            limit: Maximum number of recommendations
            
        Returns:
            List of cached recommendations
        """
        # Try memory cache first
        if farmer_id in self.cached_recommendations:
            return self.cached_recommendations[farmer_id][:limit]
        
        # Fall back to offline storage
        records = self.offline_storage.list_by_type(
            DataType.RECOMMENDATION,
            limit=limit
        )
        
        return [record.data for record in records]
    
    def generate_basic_recommendation(
        self,
        crop_type: str,
        season: str
    ) -> Dict[str, Any]:
        """
        Generate basic recommendation using cached knowledge.
        
        Args:
            crop_type: Type of crop
            season: Current season
            
        Returns:
            Basic recommendation
        """
        # Simple rule-based recommendations for common scenarios
        basic_recommendations = {
            ('rice', 'monsoon'): {
                'title': 'Rice Cultivation - Monsoon Season',
                'description': 'Basic guidance for rice cultivation during monsoon',
                'actionItems': [
                    'Ensure proper drainage in fields',
                    'Monitor water levels regularly',
                    'Apply organic fertilizer before planting'
                ],
                'confidence': 0.7
            },
            ('wheat', 'winter'): {
                'title': 'Wheat Cultivation - Winter Season',
                'description': 'Basic guidance for wheat cultivation in winter',
                'actionItems': [
                    'Prepare soil with adequate moisture',
                    'Use quality seeds',
                    'Apply nitrogen fertilizer in stages'
                ],
                'confidence': 0.7
            }
        }
        
        key = (crop_type.lower(), season.lower())
        return basic_recommendations.get(
            key,
            {
                'title': f'{crop_type.title()} Cultivation',
                'description': 'General agricultural guidance',
                'actionItems': [
                    'Monitor crop health regularly',
                    'Maintain proper irrigation',
                    'Consult local agricultural experts'
                ],
                'confidence': 0.5
            }
        )
