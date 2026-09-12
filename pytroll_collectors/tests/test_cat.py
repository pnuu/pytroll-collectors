"""Tests for the cat script."""

import datetime as dt
import os

import pytest
from posttroll.message import Message
from trollsift.parser import compose

from pytroll_collectors.scripts.cat import process_message


def _create_collection_message(tmp_path, duration_minutes=10):
    """Create a collection message with a single file in it."""
    filename = tmp_path / "hrpt_noaa18_20230524_1017_10101.l1b"
    filename.write_text("data")
    start_time = dt.datetime(2023, 5, 24, 10, 17)
    data = {"platform_name": "NOAA-18",
            "start_time": start_time,
            "end_time": start_time + dt.timedelta(minutes=duration_minutes),
            "collection": [{"uri": str(filename), "uid": filename.name}]}
    return Message("/some/topic", "collection", data)


@pytest.fixture
def config(tmp_path):
    """Create a minimal cat configuration."""
    return {"output_file_pattern": str(tmp_path / "{platform_name}_{start_time:%Y%m%d_%H%M}.l1b"),
            "command": "true"}


def test_process_message_without_min_length(tmp_path, config):
    """Test that the optional min_length option can be left out."""
    msg = _create_collection_message(tmp_path)

    new_msg = process_message(msg, config)

    expected = compose(config["output_file_pattern"], msg.data)
    assert new_msg.type == "file"
    assert new_msg.data["uri"] == expected
    assert new_msg.data["filename"] == os.path.basename(expected)
    assert "collection" not in new_msg.data


def test_process_message_too_short_pass_is_skipped(tmp_path, config):
    """Test that a pass shorter than min_length is skipped."""
    config["min_length"] = 30
    msg = _create_collection_message(tmp_path, duration_minutes=10)

    assert process_message(msg, config) is None
