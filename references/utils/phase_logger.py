#!/usr/bin/env python3
"""
Phase Logger - Core Infrastructure for QA Metrics

This module provides the foundation for logging decisions across all pipeline phases
with scores, metadata, and timestamps. Designed to be compatible with both script
and GUI execution modes.

Usage:
    from utils.phase_logger import PhaseLogger
    
    logger = PhaseLogger("A", "batch1")
    logger.log_decision("statute_123", "kept", 0.95, 0.87, {"name": "Anti-Terrorism Act"})
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pymongo import MongoClient
import threading
import queue
import time

# Configuration
MONGO_URI = "mongodb://localhost:27017"
QA_DB = "qa_metrics"
PHASE_LOGS_COLLECTION = "phase_logs"

class PhaseLogger:
    """
    Core logging infrastructure for pipeline phase decisions.
    
    Thread-safe logging with batch operations for performance.
    Compatible with both script and GUI execution modes.
    """
    
    def __init__(self, phase: str, batch_id: str, async_logging: bool = True):
        """
        Initialize phase logger.
        
        Args:
            phase: Pipeline phase (A, B, C, D, E)
            batch_id: Batch identifier (e.g., "batch1")
            async_logging: Enable asynchronous logging for performance
        """
        self.phase = phase
        self.batch_id = batch_id
        self.async_logging = async_logging
        
        # MongoDB connection
        self.client = MongoClient(MONGO_URI)
        self.collection = self.client[QA_DB][PHASE_LOGS_COLLECTION]
        
        # Ensure indexes for performance
        self._ensure_indexes()
        
        # Async logging setup
        if async_logging:
            self.log_queue = queue.Queue()
            self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
            self.log_thread.start()
    
    def _ensure_indexes(self):
        """Create database indexes for optimal query performance."""
        try:
            # Compound index for phase + batch queries
            self.collection.create_index([
                ("phase", 1),
                ("batch_id", 1),
                ("timestamp", -1)
            ])
            
            # Index for decision type queries
            self.collection.create_index([
                ("phase", 1),
                ("decision", 1),
                ("timestamp", -1)
            ])
            
            # Index for item_id lookups
            self.collection.create_index("item_id")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not create indexes: {e}")
    
    def log_decision(self, item_id: str, decision: str, 
                    score1: float, score2: float, 
                    metadata: Dict[str, Any],
                    timestamp: Optional[datetime] = None) -> bool:
        """
        Log a decision with scores and metadata.
        
        Args:
            item_id: Unique identifier for the item
            decision: Decision made (kept, dropped, grouped, deduplicated, versioned, merged)
            score1: Primary score (e.g., cosine similarity)
            score2: Secondary score (e.g., GPT confidence)
            metadata: Additional context information
            timestamp: Optional timestamp (defaults to current time)
        
        Returns:
            bool: True if logged successfully
        """
        log_entry = {
            "phase": self.phase,
            "batch_id": self.batch_id,
            "item_id": item_id,
            "decision": decision,
            "score1": float(score1),
            "score2": float(score2),
            "metadata": metadata,
            "timestamp": timestamp or datetime.now()
        }
        
        if self.async_logging:
            # Add to queue for async processing
            try:
                self.log_queue.put(log_entry, timeout=1)
                return True
            except queue.Full:
                print(f"⚠️  Warning: Log queue full for phase {self.phase}")
                return False
        else:
            # Synchronous logging
            return self._write_log_entry(log_entry)
    
    def _write_log_entry(self, log_entry: Dict[str, Any]) -> bool:
        """Write log entry to MongoDB."""
        try:
            self.collection.insert_one(log_entry)
            return True
        except Exception as e:
            print(f"❌ Error logging decision: {e}")
            return False
    
    def _log_worker(self):
        """Background worker for async logging."""
        batch_size = 10
        batch = []
        
        while True:
            try:
                # Get log entry with timeout
                log_entry = self.log_queue.get(timeout=5)
                batch.append(log_entry)
                
                # Flush batch when full or timeout
                if len(batch) >= batch_size:
                    self._write_log_batch(batch)
                    batch = []
                    
            except queue.Empty:
                # Flush remaining entries
                if batch:
                    self._write_log_batch(batch)
                    batch = []
            except Exception as e:
                print(f"❌ Error in log worker: {e}")
    
    def _write_log_batch(self, batch: list):
        """Write batch of log entries to MongoDB."""
        try:
            if batch:
                self.collection.insert_many(batch)
        except Exception as e:
            print(f"❌ Error writing log batch: {e}")
    
    def get_phase_stats(self) -> Dict[str, Any]:
        """Get statistics for the current phase and batch."""
        try:
            pipeline = [
                {"$match": {"phase": self.phase, "batch_id": self.batch_id}},
                {"$group": {
                    "_id": "$decision",
                    "count": {"$sum": 1},
                    "avg_score1": {"$avg": "$score1"},
                    "avg_score2": {"$avg": "$score2"}
                }}
            ]
            
            results = list(self.collection.aggregate(pipeline))
            
            stats = {
                "phase": self.phase,
                "batch_id": self.batch_id,
                "total_decisions": sum(r["count"] for r in results),
                "decision_breakdown": {r["_id"]: r["count"] for r in results},
                "avg_scores": {
                    r["_id"]: {"score1": r["avg_score1"], "score2": r["avg_score2"]}
                    for r in results
                }
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting phase stats: {e}")
            return {}
    
    def get_recent_decisions(self, limit: int = 100) -> list:
        """Get recent decisions for the current phase and batch."""
        try:
            cursor = self.collection.find(
                {"phase": self.phase, "batch_id": self.batch_id}
            ).sort("timestamp", -1).limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            print(f"❌ Error getting recent decisions: {e}")
            return []
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Remove old log entries to manage storage."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            result = self.collection.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            print(f"🧹 Cleaned up {result.deleted_count} old log entries")
            
        except Exception as e:
            print(f"❌ Error cleaning up old logs: {e}")
    
    def close(self):
        """Clean up resources."""
        if self.async_logging and hasattr(self, 'log_queue'):
            # Wait for queue to empty
            try:
                while not self.log_queue.empty():
                    time.sleep(0.1)
            except:
                pass
        
        if hasattr(self, 'client'):
            self.client.close()


class LoggingGUIMixin:
    """
    Mixin class for adding logging capabilities to existing GUIs.
    
    This mixin provides logging functionality that can be easily
    integrated into existing GUI classes without breaking changes.
    """
    
    def __init__(self):
        """Initialize logging mixin."""
        self.phase_logger = None
        self.current_phase = None
        self.current_batch = None
        self.logging_enabled = False
    
    def setup_logging(self, phase: str, batch_id: str, enable_logging: bool = True):
        """
        Setup logging for the current phase and batch.
        
        Args:
            phase: Pipeline phase (A, B, C, D, E)
            batch_id: Batch identifier
            enable_logging: Whether to enable logging
        """
        self.current_phase = phase
        self.current_batch = batch_id
        self.logging_enabled = enable_logging
        
        if enable_logging:
            self.phase_logger = PhaseLogger(phase, batch_id)
            print(f"✅ Logging enabled for phase {phase}, batch {batch_id}")
        else:
            self.phase_logger = None
            print(f"⚠️  Logging disabled for phase {phase}, batch {batch_id}")
    
    def log_gui_decision(self, item_id: str, decision: str, 
                        score1: float, score2: float, 
                        metadata: Dict[str, Any]) -> bool:
        """
        Log a decision from GUI operations.
        
        Args:
            item_id: Unique identifier for the item
            decision: Decision made
            score1: Primary score
            score2: Secondary score
            metadata: Additional context
        
        Returns:
            bool: True if logged successfully
        """
        if not self.logging_enabled or not self.phase_logger:
            return False
        
        try:
            return self.phase_logger.log_decision(
                item_id, decision, score1, score2, metadata
            )
        except Exception as e:
            print(f"❌ Error logging GUI decision: {e}")
            return False
    
    def get_gui_logging_stats(self) -> Dict[str, Any]:
        """Get logging statistics for GUI display."""
        if not self.phase_logger:
            return {}
        
        return self.phase_logger.get_phase_stats()
    
    def enable_logging(self):
        """Enable logging for the current phase."""
        if self.current_phase and self.current_batch:
            self.setup_logging(self.current_phase, self.current_batch, True)
    
    def disable_logging(self):
        """Disable logging for the current phase."""
        self.logging_enabled = False
        self.phase_logger = None


# Utility functions for common logging patterns
def log_filtering_decision(logger: PhaseLogger, statute: Dict, 
                          kept: bool, filter_score: float, 
                          gpt_confidence: float):
    """Log a filtering decision."""
    metadata = {
        "original_name": statute.get('Statute_Name', ''),
        "province": statute.get('Province', ''),
        "date": statute.get('Date', ''),
        "section_count": len(statute.get('Sections', []))
    }
    
    logger.log_decision(
        item_id=str(statute.get('_id', '')),
        decision="kept" if kept else "dropped",
        score1=filter_score,
        score2=gpt_confidence,
        metadata=metadata
    )


def log_grouping_decision(logger: PhaseLogger, group: Dict, 
                         similarity_score: float, gpt_confidence: float):
    """Log a grouping decision."""
    metadata = {
        "base_name": group.get('base_name', ''),
        "group_size": len(group.get('statutes', [])),
        "province": group.get('province', ''),
        "statute_type": group.get('statute_type', '')
    }
    
    logger.log_decision(
        item_id=group.get('group_id', ''),
        decision="grouped",
        score1=similarity_score,
        score2=gpt_confidence,
        metadata=metadata
    )


def log_deduplication_decision(logger: PhaseLogger, duplicate_group: Dict, 
                              similarity_score: float, gpt_confidence: float):
    """Log a deduplication decision."""
    metadata = {
        "duplicate_count": len(duplicate_group.get('statutes', [])),
        "kept_statute": duplicate_group.get('kept_statute', ''),
        "removed_statutes": duplicate_group.get('removed_statutes', [])
    }
    
    logger.log_decision(
        item_id=duplicate_group.get('group_id', ''),
        decision="deduplicated",
        score1=similarity_score,
        score2=gpt_confidence,
        metadata=metadata
    )


def log_versioning_decision(logger: PhaseLogger, version_group: Dict, 
                           version_score: float, gpt_confidence: float):
    """Log a versioning decision."""
    metadata = {
        "version_count": len(version_group.get('versions', [])),
        "base_name": version_group.get('base_name', ''),
        "version_labels": version_group.get('version_labels', [])
    }
    
    logger.log_decision(
        item_id=version_group.get('group_id', ''),
        decision="versioned",
        score1=version_score,
        score2=gpt_confidence,
        metadata=metadata
    )


if __name__ == "__main__":
    # Test the phase logger
    logger = PhaseLogger("A", "test_batch")
    
    # Test logging
    success = logger.log_decision(
        item_id="test_statute_123",
        decision="kept",
        score1=0.95,
        score2=0.87,
        metadata={"name": "Test Statute", "province": "Federal"}
    )
    
    print(f"Logging test: {'✅ Success' if success else '❌ Failed'}")
    
    # Test stats
    stats = logger.get_phase_stats()
    print(f"Phase stats: {stats}")
    
    logger.close() 