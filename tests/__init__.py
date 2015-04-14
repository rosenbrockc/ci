# Make the tests folder a package so we can test the unit test
# module from one level up more easily.
import tutility
import tconfig
import tserver
from unittest import TestSuite

test_cases = (tutility.TestUtilities, tconfig.TestServerConfigRead, tconfig.TestCronSettings,
              tconfig.TestRepoConfigRead, tserver.TestServerInit, tserver.TestServerProcess,
              tserver.TestPullRequest, tserver.TestCronManager, tserver.TestWiki)

def load_tests(loader, tests, pattern):
    suite = TestSuite()
    for test_class in test_cases:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite
