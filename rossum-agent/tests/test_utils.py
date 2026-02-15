"""Tests for rossum_agent.utils module."""

from __future__ import annotations

import shutil

from rossum_agent.utils import (
    BASE_OUTPUT_DIR,
    create_session_output_dir,
)


class TestCreateSessionOutputDir:
    """Test create_session_output_dir function."""

    def test_creates_new_directory(self):
        """Test that a new session directory is created."""
        session_dir = create_session_output_dir()

        assert session_dir.exists()
        assert session_dir.is_dir()

        shutil.rmtree(session_dir, ignore_errors=True)

    def test_creates_unique_directories(self):
        """Test that each call creates a unique directory."""
        dir1 = create_session_output_dir()
        dir2 = create_session_output_dir()

        assert dir1 != dir2
        assert dir1.exists()
        assert dir2.exists()

        shutil.rmtree(dir1, ignore_errors=True)
        shutil.rmtree(dir2, ignore_errors=True)

    def test_directory_is_under_base_output_dir(self):
        """Test that session directory is under the base output directory."""
        session_dir = create_session_output_dir()

        assert str(session_dir).startswith(str(BASE_OUTPUT_DIR))

        shutil.rmtree(session_dir, ignore_errors=True)
