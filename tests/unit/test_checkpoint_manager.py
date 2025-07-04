import pytest
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.checkpoint_manager import CheckpointManager, CheckpointMetadata, CheckpointInfo


class TestCheckpointManager:
    """Test checkpoint management functionality."""
    
    def setup_method(self, temp_dir):
        self.checkpoint_dir = temp_dir / "checkpoints"
        self.manager = CheckpointManager(
            checkpoint_dir=str(self.checkpoint_dir),
            compression=False,  # Disable compression for easier testing
            max_checkpoints=3,
            retention_days=30
        )
    
    @pytest.mark.unit
    def test_checkpoint_manager_initialization(self, temp_dir):
        """Test checkpoint manager initialization."""
        manager = CheckpointManager(checkpoint_dir=str(temp_dir / "test_checkpoints"))
        
        assert manager.checkpoint_dir.exists()
        assert manager.compression is True  # Default
        assert manager.max_checkpoints == 10  # Default
        assert manager.retention_days == 30  # Default
    
    @pytest.mark.unit
    def test_save_checkpoint_json(self):
        """Test saving checkpoint in JSON format."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        file_path = self.manager.save_checkpoint(
            checkpoint_id="test_json",
            data=test_data,
            description="Test JSON checkpoint",
            format="json"
        )
        
        assert Path(file_path).exists()
        assert "test_json" in self.manager.metadata
        
        # Verify metadata
        metadata = self.manager.metadata["test_json"]
        assert metadata.checkpoint_id == "test_json"
        assert metadata.description == "Test JSON checkpoint"
        assert metadata.compression == "none"
    
    @pytest.mark.unit
    def test_save_checkpoint_pickle(self):
        """Test saving checkpoint in pickle format."""
        test_data = {"key": "value", "datetime": datetime.now()}
        
        file_path = self.manager.save_checkpoint(
            checkpoint_id="test_pickle",
            data=test_data,
            description="Test pickle checkpoint",
            format="pickle"
        )
        
        assert Path(file_path).exists()
        assert "test_pickle" in self.manager.metadata
    
    @pytest.mark.unit
    def test_load_checkpoint_json(self):
        """Test loading checkpoint in JSON format."""
        test_data = {"key": "value", "number": 42}
        
        self.manager.save_checkpoint(
            checkpoint_id="test_load_json",
            data=test_data,
            format="json"
        )
        
        loaded_data = self.manager.load_checkpoint("test_load_json", format="json")
        
        assert loaded_data == test_data
    
    @pytest.mark.unit
    def test_load_checkpoint_pickle(self):
        """Test loading checkpoint in pickle format."""
        test_data = {"key": "value", "datetime": datetime.now()}
        
        self.manager.save_checkpoint(
            checkpoint_id="test_load_pickle",
            data=test_data,
            format="pickle"
        )
        
        loaded_data = self.manager.load_checkpoint("test_load_pickle", format="pickle")
        
        assert loaded_data["key"] == test_data["key"]
        assert isinstance(loaded_data["datetime"], datetime)
    
    @pytest.mark.unit
    def test_load_nonexistent_checkpoint(self):
        """Test loading non-existent checkpoint."""
        result = self.manager.load_checkpoint("nonexistent")
        assert result is None
    
    @pytest.mark.unit
    def test_checkpoint_exists(self):
        """Test checking if checkpoint exists."""
        test_data = {"test": "data"}
        
        assert not self.manager.checkpoint_exists("test_exists")
        
        self.manager.save_checkpoint("test_exists", test_data)
        
        assert self.manager.checkpoint_exists("test_exists")
    
    @pytest.mark.unit
    def test_get_checkpoint_info(self):
        """Test getting checkpoint information."""
        test_data = {"test": "data"}
        
        self.manager.save_checkpoint(
            checkpoint_id="test_info",
            data=test_data,
            description="Test info checkpoint"
        )
        
        info = self.manager.get_checkpoint_info("test_info")
        
        assert info is not None
        assert info.exists is True
        assert info.metadata.checkpoint_id == "test_info"
        assert info.metadata.description == "Test info checkpoint"
        assert Path(info.file_path).exists()
    
    @pytest.mark.unit
    def test_list_checkpoints(self):
        """Test listing all checkpoints."""
        # Create multiple checkpoints
        for i in range(3):
            self.manager.save_checkpoint(
                checkpoint_id=f"test_list_{i}",
                data={"index": i},
                description=f"Test checkpoint {i}"
            )
        
        checkpoints = self.manager.list_checkpoints()
        
        assert len(checkpoints) == 3
        
        # Should be sorted by creation time (newest first)
        assert all(isinstance(cp, CheckpointInfo) for cp in checkpoints)
        assert all(cp.exists for cp in checkpoints)
    
    @pytest.mark.unit
    def test_clear_checkpoint(self):
        """Test clearing a specific checkpoint."""
        test_data = {"test": "data"}
        
        self.manager.save_checkpoint("test_clear", test_data)
        assert self.manager.checkpoint_exists("test_clear")
        
        result = self.manager.clear_checkpoint("test_clear")
        
        assert result is True
        assert not self.manager.checkpoint_exists("test_clear")
    
    @pytest.mark.unit
    def test_clear_nonexistent_checkpoint(self):
        """Test clearing non-existent checkpoint."""
        result = self.manager.clear_checkpoint("nonexistent")
        assert result is False
    
    @pytest.mark.unit
    def test_clear_all_checkpoints(self):
        """Test clearing all checkpoints."""
        # Create multiple checkpoints
        for i in range(3):
            self.manager.save_checkpoint(f"test_clear_all_{i}", {"index": i})
        
        assert len(self.manager.metadata) == 3
        
        cleared_count = self.manager.clear_all_checkpoints()
        
        assert cleared_count == 3
        assert len(self.manager.metadata) == 0
    
    @pytest.mark.unit
    def test_cleanup_old_checkpoints(self):
        """Test cleanup of old checkpoints."""
        # Create more checkpoints than the limit
        for i in range(5):
            self.manager.save_checkpoint(f"test_cleanup_{i}", {"index": i})
        
        # Only the latest 3 should remain (max_checkpoints = 3)
        remaining_files = list(self.checkpoint_dir.glob("test_cleanup_*"))
        assert len(remaining_files) <= self.manager.max_checkpoints
    
    @pytest.mark.unit
    def test_get_checkpoint_statistics(self):
        """Test getting checkpoint statistics."""
        # Create some checkpoints
        for i in range(3):
            self.manager.save_checkpoint(
                f"test_stats_{i}",
                {"index": i, "data": "x" * 100},
                description=f"Stats test {i}"
            )
        
        stats = self.manager.get_checkpoint_statistics()
        
        assert stats['total_checkpoints'] == 3
        assert stats['total_size_bytes'] > 0
        assert 'oldest_checkpoint' in stats
        assert 'newest_checkpoint' in stats
        assert 'total_size_human' in stats
    
    @pytest.mark.unit
    def test_export_checkpoint(self, temp_dir):
        """Test exporting checkpoint."""
        test_data = {"export": "test"}
        
        self.manager.save_checkpoint("test_export", test_data, description="Export test")
        
        export_path = temp_dir / "exported_checkpoint.json"
        result = self.manager.export_checkpoint("test_export", str(export_path))
        
        assert result is True
        assert export_path.exists()
        
        # Check if metadata file was also created
        metadata_path = export_path.with_suffix('.metadata.json')
        assert metadata_path.exists()
    
    @pytest.mark.unit
    def test_export_nonexistent_checkpoint(self, temp_dir):
        """Test exporting non-existent checkpoint."""
        export_path = temp_dir / "nonexistent.json"
        result = self.manager.export_checkpoint("nonexistent", str(export_path))
        
        assert result is False
        assert not export_path.exists()
    
    @pytest.mark.unit
    def test_import_checkpoint(self, temp_dir):
        """Test importing checkpoint."""
        # Create a test file to import
        test_data = {"imported": "data"}
        test_file = temp_dir / "import_test.json"
        
        with open(test_file, 'w') as f:
            json.dump(test_data, f)
        
        # Create metadata file
        metadata = {
            "checkpoint_id": "imported_test",
            "created_at": datetime.now().isoformat(),
            "description": "Imported checkpoint",
            "data_hash": "test_hash",
            "file_size": test_file.stat().st_size,
            "compression": "none"
        }
        
        metadata_file = test_file.with_suffix('.metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        result = self.manager.import_checkpoint(str(test_file))
        
        assert result is True
        assert self.manager.checkpoint_exists("imported_test")
    
    @pytest.mark.unit
    def test_import_nonexistent_file(self):
        """Test importing non-existent file."""
        result = self.manager.import_checkpoint("nonexistent.json")
        assert result is False


class TestCheckpointMetadata:
    """Test CheckpointMetadata dataclass."""
    
    @pytest.mark.unit
    def test_checkpoint_metadata_creation(self):
        """Test creating CheckpointMetadata."""
        now = datetime.now()
        metadata = CheckpointMetadata(
            checkpoint_id="test",
            created_at=now,
            description="Test checkpoint",
            data_hash="abc123",
            file_size=1024,
            compression="gzip"
        )
        
        assert metadata.checkpoint_id == "test"
        assert metadata.created_at == now
        assert metadata.description == "Test checkpoint"
        assert metadata.data_hash == "abc123"
        assert metadata.file_size == 1024
        assert metadata.compression == "gzip"
        assert metadata.version == "1.0"  # Default


class TestCheckpointInfo:
    """Test CheckpointInfo dataclass."""
    
    @pytest.mark.unit
    def test_checkpoint_info_creation(self):
        """Test creating CheckpointInfo."""
        metadata = CheckpointMetadata(
            checkpoint_id="test",
            created_at=datetime.now(),
            description="Test",
            data_hash="abc123",
            file_size=1024,
            compression="none"
        )
        
        info = CheckpointInfo(
            metadata=metadata,
            file_path="/path/to/checkpoint",
            exists=True
        )
        
        assert info.metadata == metadata
        assert info.file_path == "/path/to/checkpoint"
        assert info.exists is True


class TestCheckpointWithCompression:
    """Test checkpoint functionality with compression enabled."""
    
    def setup_method(self, temp_dir):
        self.checkpoint_dir = temp_dir / "checkpoints_compressed"
        self.manager = CheckpointManager(
            checkpoint_dir=str(self.checkpoint_dir),
            compression=True,  # Enable compression
            max_checkpoints=3
        )
    
    @pytest.mark.unit
    def test_save_and_load_compressed_checkpoint(self):
        """Test saving and loading compressed checkpoint."""
        test_data = {"key": "value", "large_data": "x" * 1000}
        
        # Save with compression
        self.manager.save_checkpoint("test_compressed", test_data)
        
        # Load and verify
        loaded_data = self.manager.load_checkpoint("test_compressed")
        
        assert loaded_data == test_data
        
        # Verify compression was used
        metadata = self.manager.metadata["test_compressed"]
        assert metadata.compression == "gzip"
    
    @pytest.mark.unit
    def test_compressed_file_smaller(self):
        """Test that compressed files are smaller."""
        large_data = {"data": "x" * 10000}  # Large repetitive data
        
        # Create manager without compression
        uncompressed_manager = CheckpointManager(
            checkpoint_dir=str(self.checkpoint_dir / "uncompressed"),
            compression=False
        )
        
        # Save same data with and without compression
        self.manager.save_checkpoint("compressed", large_data)
        uncompressed_manager.save_checkpoint("uncompressed", large_data)
        
        # Get file sizes
        compressed_metadata = self.manager.metadata["compressed"]
        uncompressed_metadata = uncompressed_manager.metadata["uncompressed"]
        
        # Compressed should be smaller
        assert compressed_metadata.file_size < uncompressed_metadata.file_size