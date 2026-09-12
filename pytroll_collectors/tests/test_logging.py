#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2026 Pytroll developers

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit testing the logging functionality.

This is inspired by how it is done in pytroll-watchers and assisted by ChatGPT.
"""


import pytest
import logging
import logging.config

import yaml
from unittest.mock import patch
from pytroll_collectors.logging import _setup_logging_from_config


@pytest.fixture
def isolated_logging():
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    yield

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    for handler in old_handlers:
        root.addHandler(handler)

    root.setLevel(old_level)


def test_setup_logging_from_yaml_config(tmp_path):
    config_file = tmp_path / "logging.yaml"
    config_file.write_text(
        """
version: 1
handlers:
  console:
    class: logging.StreamHandler
loggers:
  "":
    handlers: [console]
    level: INFO
""",
        encoding="utf-8",
    )

    with patch("pytroll_collectors.logging.logging.config.dictConfig") as dict_config:
        logger = _setup_logging_from_config(config_file, "mylogger")

    dict_config.assert_called_once()
    assert logger.name == "mylogger"


def test_setup_logging_from_missing_config_raises(tmp_path, isolated_logging):
    """Test that a missing logging config file raises FileNotFoundError."""
    log_config_file = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError, match="Logging config file not found"):
        _setup_logging_from_config(log_config_file, "pytroll_collectors.test")


def test_setup_logging_from_invalid_yaml_raises(tmp_path, isolated_logging):
    """Test that a YAML file not containing a dict raises ValueError."""
    log_config_file = tmp_path / "log_config.yaml"
    log_config_file.write_text("- not\n- a\n- dict\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid YAML logging config"):
        _setup_logging_from_config(log_config_file, "pytroll_collectors.test")


def test_setup_logging_logs_to_file_given_with_log_option(tmp_path, isolated_logging):
    """Test that the file given with the -l/--log option is logged to."""
    from argparse import Namespace

    from pytroll_collectors.logging import setup_logging

    log_file = tmp_path / "collector.log"
    opts = Namespace(log=str(log_file), log_config=None, verbose=False)

    logger = setup_logging(opts, "pytroll_collectors.test")
    logger.info("a message in the log file")

    for handler in logging.getLogger("").handlers:
        handler.flush()

    assert log_file.exists()
    assert "a message in the log file" in log_file.read_text()


def test_setup_logging_without_log_option_only_logs_to_stdout(tmp_path, isolated_logging):
    """Test that no file handler is created when no log file is given."""
    from argparse import Namespace

    from pytroll_collectors.logging import setup_logging

    setup_logging(Namespace(log=None, log_config=None, verbose=False), "pytroll_collectors.test")

    handlers = logging.getLogger("").handlers
    assert handlers
    assert not any(isinstance(handler, logging.FileHandler) for handler in handlers)
