import json
import pickle
import gzip
import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from .logger import get_logger


@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    created_at: datetime
    description: str
    data_hash: str
    file_size: int
    compression: str
    version: str = "1.0"


@dataclass
class CheckpointInfo:
    metadata: CheckpointMetadata
    file_path: str
    exists: bool


class CheckpointManager:
    """
    Manages checkpoints for long-running processes with support for:
    - JSON and pickle serialization
    - Compression
    - Versioning
    - Automatic cleanup
    - Data integrity verification
    """
    
    def __init__(self, checkpoint_dir: str = "checkpoints", 
                 compression: bool = True,
                 max_checkpoints: int = 10,
                 retention_days: int = 30):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.compression = compression
        self.max_checkpoints = max_checkpoints
        self.retention_days = retention_days
        self.logger = get_logger(__name__)
        
        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata file
        self.metadata_file = self.checkpoint_dir / "checkpoints_metadata.json"
        
        # Load existing metadata
        self.metadata = self._load_metadata()
    
    def save_checkpoint(self, 
                       checkpoint_id: str, 
                       data: Any, 
                       description: str = "",
                       format: str = "json") -> str:
        """
        Save checkpoint data
        
        Args:
            checkpoint_id: Unique identifier for the checkpoint
            data: Data to save
            description: Human-readable description
            format: Serialization format ('json' or 'pickle')
            
        Returns:
            Path to saved checkpoint file
        """
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{checkpoint_id}_{timestamp}.{format}"
            
            if self.compression:
                filename += ".gz"
            
            file_path = self.checkpoint_dir / filename
            
            # Serialize and save data
            if format == "json":
                serialized_data = json.dumps(data, indent=2, default=str)
                data_bytes = serialized_data.encode('utf-8')
            elif format == "pickle":
                data_bytes = pickle.dumps(data)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # Calculate hash for integrity
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            # Save with optional compression
            if self.compression:
                with gzip.open(file_path, 'wb') as f:
                    f.write(data_bytes)
            else:
                with open(file_path, 'wb') as f:
                    f.write(data_bytes)
            
            # Create metadata
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                created_at=datetime.now(),
                description=description,
                data_hash=data_hash,
                file_size=file_path.stat().st_size,
                compression="gzip" if self.compression else "none"
            )
            
            # Update metadata registry
            self.metadata[checkpoint_id] = metadata
            self._save_metadata()
            
            # Cleanup old checkpoints
            self._cleanup_old_checkpoints(checkpoint_id)
            
            self.logger.info(f"Checkpoint saved: {checkpoint_id} -> {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint {checkpoint_id}: {str(e)}")
            raise
    
    def load_checkpoint(self, checkpoint_id: str, format: str = "json") -> Any:
        """
        Load checkpoint data
        
        Args:
            checkpoint_id: Checkpoint identifier
            format: Expected serialization format
            
        Returns:
            Loaded data or None if checkpoint doesn't exist
        """
        try:
            # Find latest checkpoint for this ID
            checkpoint_info = self.get_checkpoint_info(checkpoint_id)
            
            if not checkpoint_info or not checkpoint_info.exists:
                self.logger.warning(f"Checkpoint {checkpoint_id} not found")
                return None
            
            file_path = Path(checkpoint_info.file_path)
            metadata = checkpoint_info.metadata
            
            # Load and decompress data
            if metadata.compression == "gzip":
                with gzip.open(file_path, 'rb') as f:
                    data_bytes = f.read()
            else:
                with open(file_path, 'rb') as f:
                    data_bytes = f.read()
            
            # Verify data integrity
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            if data_hash != metadata.data_hash:
                raise ValueError(f"Checkpoint data integrity check failed for {checkpoint_id}")
            
            # Deserialize data
            if format == "json":
                data = json.loads(data_bytes.decode('utf-8'))
            elif format == "pickle":
                data = pickle.loads(data_bytes)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_id}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint {checkpoint_id}: {str(e)}")
            raise
    
    def checkpoint_exists(self, checkpoint_id: str) -> bool:
        """Check if checkpoint exists"""
        return checkpoint_id in self.metadata
    
    def get_checkpoint_info(self, checkpoint_id: str) -> Optional[CheckpointInfo]:
        """Get information about a checkpoint"""
        
        if checkpoint_id not in self.metadata:
            return None
        
        metadata = self.metadata[checkpoint_id]
        
        # Find the actual file
        pattern = f"{checkpoint_id}_*.json*"
        matching_files = list(self.checkpoint_dir.glob(pattern))
        
        if not matching_files:
            # Try pickle pattern
            pattern = f"{checkpoint_id}_*.pickle*"
            matching_files = list(self.checkpoint_dir.glob(pattern))
        
        if matching_files:
            # Get the latest file
            latest_file = max(matching_files, key=lambda p: p.stat().st_mtime)
            file_path = str(latest_file)
            exists = True
        else:
            file_path = ""
            exists = False
        
        return CheckpointInfo(
            metadata=metadata,
            file_path=file_path,
            exists=exists
        )
    
    def list_checkpoints(self) -> List[CheckpointInfo]:
        """List all available checkpoints"""
        
        checkpoints = []
        
        for checkpoint_id, metadata in self.metadata.items():
            checkpoint_info = self.get_checkpoint_info(checkpoint_id)
            if checkpoint_info:
                checkpoints.append(checkpoint_info)
        
        # Sort by creation time (newest first)
        checkpoints.sort(key=lambda x: x.metadata.created_at, reverse=True)
        
        return checkpoints
    
    def clear_checkpoint(self, checkpoint_id: str) -> bool:
        """Clear a specific checkpoint"""
        
        try:
            if checkpoint_id not in self.metadata:
                self.logger.warning(f"Checkpoint {checkpoint_id} not found in metadata")
                return False
            
            # Find and remove files
            patterns = [
                f"{checkpoint_id}_*.json*",
                f"{checkpoint_id}_*.pickle*"
            ]
            
            files_removed = 0
            for pattern in patterns:
                for file_path in self.checkpoint_dir.glob(pattern):
                    file_path.unlink()
                    files_removed += 1
                    self.logger.debug(f"Removed checkpoint file: {file_path}")
            
            # Remove from metadata
            del self.metadata[checkpoint_id]
            self._save_metadata()
            
            self.logger.info(f"Cleared checkpoint {checkpoint_id} ({files_removed} files)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear checkpoint {checkpoint_id}: {str(e)}")
            return False
    
    def clear_all_checkpoints(self) -> int:
        """Clear all checkpoints"""
        
        try:
            cleared_count = 0
            
            # Remove all checkpoint files
            for file_path in self.checkpoint_dir.glob("*"):
                if file_path.name != "checkpoints_metadata.json":
                    file_path.unlink()
                    cleared_count += 1
            
            # Clear metadata
            self.metadata.clear()
            self._save_metadata()
            
            self.logger.info(f"Cleared all checkpoints ({cleared_count} files)")
            return cleared_count
            
        except Exception as e:
            self.logger.error(f"Failed to clear all checkpoints: {str(e)}")
            return 0
    
    def _cleanup_old_checkpoints(self, checkpoint_id: str):
        """Cleanup old checkpoints for a specific ID"""
        
        try:
            # Find all files for this checkpoint ID
            patterns = [
                f"{checkpoint_id}_*.json*",
                f"{checkpoint_id}_*.pickle*"
            ]
            
            all_files = []
            for pattern in patterns:
                all_files.extend(self.checkpoint_dir.glob(pattern))
            
            # Sort by modification time (newest first)
            all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Keep only the latest N files
            files_to_remove = all_files[self.max_checkpoints:]
            
            for file_path in files_to_remove:
                file_path.unlink()
                self.logger.debug(f"Removed old checkpoint file: {file_path}")
            
            if files_to_remove:
                self.logger.info(f"Cleaned up {len(files_to_remove)} old checkpoint files for {checkpoint_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old checkpoints for {checkpoint_id}: {str(e)}")
    
    def cleanup_expired_checkpoints(self):
        """Clean up checkpoints older than retention period"""
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            expired_checkpoints = []
            
            for checkpoint_id, metadata in self.metadata.items():
                if metadata.created_at < cutoff_date:
                    expired_checkpoints.append(checkpoint_id)
            
            cleared_count = 0
            for checkpoint_id in expired_checkpoints:
                if self.clear_checkpoint(checkpoint_id):
                    cleared_count += 1
            
            if cleared_count > 0:
                self.logger.info(f"Cleaned up {cleared_count} expired checkpoints")
            
            return cleared_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired checkpoints: {str(e)}")
            return 0
    
    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """Get checkpoint statistics"""
        
        try:
            stats = {
                'total_checkpoints': len(self.metadata),
                'total_size_bytes': 0,
                'oldest_checkpoint': None,
                'newest_checkpoint': None,
                'by_format': {'json': 0, 'pickle': 0},
                'by_compression': {'gzip': 0, 'none': 0}
            }
            
            if not self.metadata:
                return stats
            
            # Calculate statistics
            creation_times = []
            for checkpoint_id, metadata in self.metadata.items():
                creation_times.append(metadata.created_at)
                stats['total_size_bytes'] += metadata.file_size
                
                # Count by compression
                stats['by_compression'][metadata.compression] += 1
                
                # Determine format from filename patterns
                checkpoint_info = self.get_checkpoint_info(checkpoint_id)
                if checkpoint_info and checkpoint_info.exists:
                    if '.json' in checkpoint_info.file_path:
                        stats['by_format']['json'] += 1
                    elif '.pickle' in checkpoint_info.file_path:
                        stats['by_format']['pickle'] += 1
            
            # Find oldest and newest
            if creation_times:
                stats['oldest_checkpoint'] = min(creation_times).isoformat()
                stats['newest_checkpoint'] = max(creation_times).isoformat()
            
            # Convert size to human readable
            stats['total_size_human'] = self._format_file_size(stats['total_size_bytes'])
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get checkpoint statistics: {str(e)}")
            return {}
    
    def _load_metadata(self) -> Dict[str, CheckpointMetadata]:
        """Load checkpoint metadata from file"""
        
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r') as f:
                metadata_dict = json.load(f)
            
            # Convert to CheckpointMetadata objects
            metadata = {}
            for checkpoint_id, data in metadata_dict.items():
                # Handle datetime parsing
                data['created_at'] = datetime.fromisoformat(data['created_at'])
                metadata[checkpoint_id] = CheckpointMetadata(**data)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint metadata: {str(e)}")
            return {}
    
    def _save_metadata(self):
        """Save checkpoint metadata to file"""
        
        try:
            # Convert to serializable format
            metadata_dict = {}
            for checkpoint_id, metadata in self.metadata.items():
                data = asdict(metadata)
                data['created_at'] = metadata.created_at.isoformat()
                metadata_dict[checkpoint_id] = data
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata_dict, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint metadata: {str(e)}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} TB"
    
    def export_checkpoint(self, checkpoint_id: str, export_path: str) -> bool:
        """Export checkpoint to external location"""
        
        try:
            checkpoint_info = self.get_checkpoint_info(checkpoint_id)
            
            if not checkpoint_info or not checkpoint_info.exists:
                self.logger.error(f"Checkpoint {checkpoint_id} not found")
                return False
            
            # Copy checkpoint file
            source_path = Path(checkpoint_info.file_path)
            destination_path = Path(export_path)
            
            # Create destination directory if needed
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_path, destination_path)
            
            # Export metadata as well
            metadata_path = destination_path.with_suffix('.metadata.json')
            metadata_dict = asdict(checkpoint_info.metadata)
            metadata_dict['created_at'] = checkpoint_info.metadata.created_at.isoformat()
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata_dict, f, indent=2)
            
            self.logger.info(f"Exported checkpoint {checkpoint_id} to {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export checkpoint {checkpoint_id}: {str(e)}")
            return False
    
    def import_checkpoint(self, checkpoint_path: str, checkpoint_id: str = None) -> bool:
        """Import checkpoint from external location"""
        
        try:
            source_path = Path(checkpoint_path)
            
            if not source_path.exists():
                self.logger.error(f"Checkpoint file not found: {checkpoint_path}")
                return False
            
            # Try to load metadata
            metadata_path = source_path.with_suffix('.metadata.json')
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata_dict = json.load(f)
                
                # Use original checkpoint ID if not specified
                if checkpoint_id is None:
                    checkpoint_id = metadata_dict['checkpoint_id']
                
                # Parse metadata
                metadata_dict['created_at'] = datetime.fromisoformat(metadata_dict['created_at'])
                metadata = CheckpointMetadata(**metadata_dict)
            else:
                # Create basic metadata
                if checkpoint_id is None:
                    checkpoint_id = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Calculate hash
                with open(source_path, 'rb') as f:
                    data_bytes = f.read()
                data_hash = hashlib.sha256(data_bytes).hexdigest()
                
                metadata = CheckpointMetadata(
                    checkpoint_id=checkpoint_id,
                    created_at=datetime.now(),
                    description="Imported checkpoint",
                    data_hash=data_hash,
                    file_size=source_path.stat().st_size,
                    compression="gzip" if source_path.suffix == '.gz' else "none"
                )
            
            # Copy to checkpoint directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            format_ext = ".json" if ".json" in source_path.name else ".pickle"
            compression_ext = ".gz" if source_path.suffix == '.gz' else ""
            
            filename = f"{checkpoint_id}_{timestamp}{format_ext}{compression_ext}"
            destination_path = self.checkpoint_dir / filename
            
            shutil.copy2(source_path, destination_path)
            
            # Update metadata
            self.metadata[checkpoint_id] = metadata
            self._save_metadata()
            
            self.logger.info(f"Imported checkpoint {checkpoint_id} from {checkpoint_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import checkpoint from {checkpoint_path}: {str(e)}")
            return False