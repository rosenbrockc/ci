# PyCI Revision History

For all revisions after the initial repository setup.

## Revision 0.0.4

- Debugging the actual implementation on the server to work well with crontab etc.
- Added `pygithub` dependency to `setup.py`.

## Revision 0.0.3

- Added support for `.cron_profile` environment variables; needed for PyCI to load correctly and probably for user's unit tests to run correctly. If the file doesn't exist, it is automatically created with the bare-minimum defaults.
- Added to the Python Package Index.

## Revision 0.0.2

- Updated README.md
- Added verbosity option to the config and CI script modules.

## Revision 0.0.1

- Completed the driver script `ci.py` and implemented full unit tests for it and all of its script arguments.