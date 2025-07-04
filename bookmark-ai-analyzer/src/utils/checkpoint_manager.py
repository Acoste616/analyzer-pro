"""Checkpoint management for resumable processing."""

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict

from ..config import get_settings
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    
    checkpoint_id: str
    created_at: datetime
    total_items: int
    processed_items: int
    failed_items: int
    last_processed_id: Optional[str]
    processing_time: float
    error_count: int
    status: str  # "in_progress", "completed", "failed"
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.status == "completed"


class CheckpointManager:
    """Manage checkpoints for resumable processing."""
    
    def __init__(self, checkpoint_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        settings = get_settings()
        self.checkpoint_dir = checkpoint_dir or settings.checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_checkpoint: Optional[CheckpointMetadata] = None
        self.checkpoint_data: Dict[str, Any] = {}
        
    def create_checkpoint(
        self,
        checkpoint_id: str,
        total_items: int,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> CheckpointMetadata:
        """
        Create a new checkpoint.
        
        Args:
            checkpoint_id: Unique identifier for the checkpoint
            total_items: Total number of items to process
            initial_data: Initial data to store in checkpoint
            
        Returns:
            Created checkpoint metadata
        """
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            created_at=datetime.now(),
            total_items=total_items,
            processed_items=0,
            failed_items=0,
            last_processed_id=None,
            processing_time=0.0,
            error_count=0,
            status="in_progress"
        )
        
        self.current_checkpoint = metadata
        self.checkpoint_data = initial_data or {}
        
        self._save_checkpoint()
        logger.info(f"Created checkpoint: {checkpoint_id}")
        
        return metadata
    
    def update_checkpoint(
        self,
        processed_items: Optional[int] = None,
        failed_items: Optional[int] = None,
        last_processed_id: Optional[str] = None,
        data_update: Optional[Dict[str, Any]] = None,
        increment_processed: bool = False,
        increment_failed: bool = False
    ) -> None:
        """
        Update checkpoint progress.
        
        Args:
            processed_items: Number of processed items (absolute)
            failed_items: Number of failed items (absolute)
            last_processed_id: ID of last processed item
            data_update: Data to update in checkpoint
            increment_processed: Increment processed count by 1
            increment_failed: Increment failed count by 1
        """
        if not self.current_checkpoint:
            raise ValueError("No active checkpoint")
        
        if processed_items is not None:
            self.current_checkpoint.processed_items = processed_items
        elif increment_processed:
            self.current_checkpoint.processed_items += 1
            
        if failed_items is not None:
            self.current_checkpoint.failed_items = failed_items
        elif increment_failed:
            self.current_checkpoint.failed_items += 1
            self.current_checkpoint.error_count += 1
            
        if last_processed_id is not None:
            self.current_checkpoint.last_processed_id = last_processed_id
            
        if data_update:
            self.checkpoint_data.update(data_update)
        
        # Update status if complete
        if self.current_checkpoint.processed_items >= self.current_checkpoint.total_items:
            self.current_checkpoint.status = "completed"
            
        self._save_checkpoint()
        
        if self.current_checkpoint.processed_items % 10 == 0:
            logger.debug(
                f"Checkpoint updated: {self.current_checkpoint.processed_items}/"
                f"{self.current_checkpoint.total_items} "
                f"({self.current_checkpoint.progress_percentage:.1f}%)"
            )
    
    def load_checkpoint(self, checkpoint_id: str) -> CheckpointMetadata:
        """
        Load a checkpoint from disk.
        
        Args:
            checkpoint_id: ID of checkpoint to load
            
        Returns:
            Loaded checkpoint metadata
        """
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.checkpoint"
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        
        with open(checkpoint_file, "rb") as f:
            data = pickle.load(f)
            
        metadata_dict = data["metadata"]
        metadata_dict["created_at"] = datetime.fromisoformat(metadata_dict["created_at"])
        
        self.current_checkpoint = CheckpointMetadata(**metadata_dict)
        self.checkpoint_data = data["data"]
        
        logger.info(
            f"Loaded checkpoint: {checkpoint_id} "
            f"({self.current_checkpoint.processed_items}/"
            f"{self.current_checkpoint.total_items} items)"
        )
        
        return self.current_checkpoint
    
    def get_latest_checkpoint(self) -> Optional[CheckpointMetadata]:
        """
        Get the most recent checkpoint.
        
        Returns:
            Latest checkpoint metadata or None
        """
        checkpoint_files = list(self.checkpoint_dir.glob("*.checkpoint"))
        if not checkpoint_files:
            return None
        
        # Sort by modification time
        latest_file = max(checkpoint_files, key=lambda p: p.stat().st_mtime)
        checkpoint_id = latest_file.stem
        
        return self.load_checkpoint(checkpoint_id)
    
    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """
        List all available checkpoints.
        
        Returns:
            List of checkpoint metadata
        """
        checkpoints = []
        
        for checkpoint_file in self.checkpoint_dir.glob("*.checkpoint"):
            try:
                with open(checkpoint_file, "rb") as f:
                    data = pickle.load(f)
                    
                metadata_dict = data["metadata"]
                metadata_dict["created_at"] = datetime.fromisoformat(
                    metadata_dict["created_at"]
                )
                
                checkpoints.append(CheckpointMetadata(**metadata_dict))
            except Exception as e:
                logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
                
        return sorted(checkpoints, key=lambda c: c.created_at, reverse=True)
    
    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: ID of checkpoint to delete
        """
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.checkpoint"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.info(f"Deleted checkpoint: {checkpoint_id}")
            
        if self.current_checkpoint and self.current_checkpoint.checkpoint_id == checkpoint_id:
            self.current_checkpoint = None
            self.checkpoint_data = {}
    
    def get_checkpoint_data(self, key: str, default: Any = None) -> Any:
        """
        Get data from current checkpoint.
        
        Args:
            key: Data key
            default: Default value if key not found
            
        Returns:
            Stored value or default
        """
        return self.checkpoint_data.get(key, default)
    
    def set_checkpoint_data(self, key: str, value: Any) -> None:
        """
        Set data in current checkpoint.
        
        Args:
            key: Data key
            value: Value to store
        """
        self.checkpoint_data[key] = value
        self._save_checkpoint()
    
    def _save_checkpoint(self) -> None:
        """Save current checkpoint to disk."""
        if not self.current_checkpoint:
            return
            
        checkpoint_file = self.checkpoint_dir / f"{self.current_checkpoint.checkpoint_id}.checkpoint"
        
        # Convert metadata to dict
        metadata_dict = asdict(self.current_checkpoint)
        metadata_dict["created_at"] = metadata_dict["created_at"].isoformat()
        
        data = {
            "metadata": metadata_dict,
            "data": self.checkpoint_data
        }
        
        # Save atomically
        temp_file = checkpoint_file.with_suffix(".tmp")
        with open(temp_file, "wb") as f:
            pickle.dump(data, f)
            
        temp_file.replace(checkpoint_file)
    
    def cleanup_old_checkpoints(self, keep_count: int = 10) -> None:
        """
        Clean up old checkpoints, keeping only the most recent ones.
        
        Args:
            keep_count: Number of checkpoints to keep
        """
        checkpoints = self.list_checkpoints()
        
        if len(checkpoints) <= keep_count:
            return
            
        # Keep only completed checkpoints and the most recent ones
        to_delete = []
        kept_count = 0
        
        for checkpoint in checkpoints:
            if kept_count < keep_count:
                kept_count += 1
            elif checkpoint.status != "in_progress":
                to_delete.append(checkpoint.checkpoint_id)
                
        for checkpoint_id in to_delete:
            self.delete_checkpoint(checkpoint_id)
            
        logger.info(f"Cleaned up {len(to_delete)} old checkpoints")
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save checkpoint on exit."""
        if self.current_checkpoint:
            if exc_type is not None:
                self.current_checkpoint.status = "failed"
                self.current_checkpoint.error_count += 1
            self._save_checkpoint()