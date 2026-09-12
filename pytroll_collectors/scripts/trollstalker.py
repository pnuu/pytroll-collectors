"""Trollstalker script.

./trollstalker.py -c /path/to/trollstalker_config.ini -C noaa_hrpt
"""

from pytroll_collectors.trollstalker import main

# Logging is set up by ``main()`` once the configuration file has been read.

if __name__ == "__main__":
    main()
