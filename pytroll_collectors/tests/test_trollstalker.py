"""Tests for trollstalker."""
import os
import time
import pytest

from posttroll.message import Message
from pytroll_collectors.trollstalker import start_observer, stop_observer


LAG_SECONDS = 0.02
TIMEOUT_SECONDS = 10


def wait_for_messages(messages, count=1, timeout=TIMEOUT_SECONDS):
    """Wait until *count* messages have been published, or *timeout* expires."""
    deadline = time.time() + timeout
    while len(messages) < count and time.time() < deadline:
        time.sleep(LAG_SECONDS)
    return messages


@pytest.fixture
def dir_to_watch(tmp_path):
    """Define a dir to watch."""
    dir_to_watch = tmp_path / "to_watch"
    return dir_to_watch


@pytest.fixture
def config_file(tmp_path, dir_to_watch):
    """Create a config file for trollstalker."""
    config = """# This config is used in Trollstalker.

[noaa_hrpt]
topic=/HRPT/l1b/dev/mystation
directory=""" + os.fspath(dir_to_watch) + """
filepattern={path}hrpt_{platform_name}_{start_time:%Y%m%d_%H%M}_{orbit_number:05d}.l1b
instruments=avhrr/3,mhs,amsu-b,amsu-a,hirs/3,hirs/4
loglevel=WARNING
posttroll_port=12234
nameservers=false
alias_platform_name = noaa18:NOAA-18|noaa19:NOAA-19
history=10"""
    config_file = tmp_path / "config.ini"
    with open(config_file, "w") as fd:
        fd.write(config)
    return config_file


@pytest.fixture
def subdir_to_watch(dir_to_watch):
    """Create a subdirectory of the watched directory.

    The directory is created before the observer is started, so that the watch
    for it is guaranteed to be in place when the test writes a file in it.
    """
    subdir_to_watch = dir_to_watch / "new_dir"
    os.makedirs(subdir_to_watch)
    return subdir_to_watch


@pytest.fixture
def messages_from_observer(config_file):
    """Create an observer and yield the messages it published."""
    from posttroll.testing import patched_publisher
    with patched_publisher() as messages:
        obs = start_observer(["-c", os.fspath(config_file), "-C", "noaa_hrpt"])
        time.sleep(LAG_SECONDS)
        yield messages
        stop_observer(obs)


def test_trollstalker(subdir_to_watch, messages_from_observer):
    """Test trollstalker functionality."""
    trigger_file = subdir_to_watch / "hrpt_noaa18_20230524_1017_10101.l1b"
    with open(trigger_file, "w") as fd:
        fd.write("hej")
    wait_for_messages(messages_from_observer)

    message = messages_from_observer[0]
    assert message.startswith("pytroll://HRPT/l1b/dev/mystation file ")
    message = Message(rawstr=message)

    assert message.data['platform_name'] == "NOAA-18"
    assert message.data['uri'] == os.fspath(trigger_file)


def test_trollstalker_monitored_directory_is_created(messages_from_observer, dir_to_watch):
    """Test that monitored directories are created."""
    trigger_file = dir_to_watch / "hrpt_noaa18_20230524_1017_10101.l1b"
    with open(trigger_file, "w") as fd:
        fd.write("hej")
    wait_for_messages(messages_from_observer)
    assert os.path.exists(dir_to_watch)


def test_trollstalker_handles_moved_files(messages_from_observer, dir_to_watch, tmp_path):
    """Test that trollstalker detects moved files."""
    filename = "hrpt_noaa18_20230524_1017_10101.l1b"
    trigger_file = tmp_path / filename
    with open(trigger_file, "w") as fd:
        fd.write("hej")
    os.rename(trigger_file, dir_to_watch / filename)
    wait_for_messages(messages_from_observer)
    assert len(messages_from_observer) == 1
    assert messages_from_observer[0].startswith("pytroll://HRPT/l1b/dev/mystation file ")


def test_event_names_are_deprecated(config_file):
    """Test that trollstalker detects moved files."""
    with open(config_file, "a") as fd:
        fd.write("\nevent_names=IN_CLOSE_WRITE,IN_MOVED_TO,IN_CREATE\n")
    with pytest.deprecated_call():
        obs = start_observer(["-c", os.fspath(config_file), "-C", "noaa_hrpt"])
        stop_observer(obs)


def test_settings_can_be_given_without_a_config_file():
    """Test that trollstalker can be configured from the command line only."""
    from pytroll_collectors.trollstalker import get_settings

    monitored_dirs, settings = get_settings(["-d", "/tmp/some_dir", "-t", "/some/topic",
                                             "-i", "avhrr/3"])

    assert monitored_dirs == ["/tmp/some_dir"]
    assert settings["topic"] == "/some/topic"
    assert settings["aliases"] == {}
    assert settings["custom_vars"] == {}
    assert settings["tbus_orbit"] is False
    assert settings["granule_length"] == 0
    assert settings["history_length"] == 0


def test_logging_config_from_config_file_is_used(tmp_path, config_file):
    """Test that the logging config given in the config file is taken into use."""
    import logging

    from pytroll_collectors.trollstalker import get_settings

    log_file = tmp_path / "trollstalker.log"
    log_config_file = tmp_path / "log_config.yaml"
    log_config_file.write_text(f"""
version: 1
formatters:
  simple:
    format: '%(levelname)s %(name)s %(message)s'
handlers:
  file:
    class: logging.FileHandler
    filename: {log_file}
    formatter: simple
root:
  level: DEBUG
  handlers: [file]
""")
    with open(config_file, "a") as fd:
        fd.write(f"\nlog_config={log_config_file}\n")

    root = logging.getLogger("")
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        get_settings(["-c", os.fspath(config_file), "-C", "noaa_hrpt"])
        assert log_file.exists()
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        for handler in old_handlers:
            root.addHandler(handler)
        root.setLevel(old_level)
