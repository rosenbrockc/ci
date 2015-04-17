# Contributing to Py-CI

If you would like to contribute a bug fix or add new features, please review these guidelines.

## Testing Strategy

Py-CI is essentially 100% unit tested. By essentially, we mean that all functions except those that rely on live requests are unit tested with at least one test. Since we use other open-source API implementations (`pygithub`, `mwclient`, etc.), we assume that they are unit tested and working and then only test our interaction with them. Any calls made to their routines are assumed to work fine (so long as we have formatted the data correctly).

The `tests/` folder is configured as a python package. This allows tests to be run using:

```
python -m unittest tests
python tests/scripts.py ci
```

from within the main repo directory. If you extend the code, please add a `unittest` module with the same name as the module you added, but with a prefix of `t`, as in `tmodule.py` for `module.py`. Then add the test cases to the test suites in `tests/__init__.py`.

## Continuous Integration

Once you have added your contribution, submit a pull request. It will get sucked up by an instance of this very project running on a server I have access to. Once the status updates as passing all the unit tests (including the ones you add!), then I will review the code and merge it into master.