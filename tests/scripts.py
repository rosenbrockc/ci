#This script tests the scripts in the ./scripts folder on some pre-defined
#files that are known to work.
import sys
from common import context_exec
from os import path as ppath

def examples():
    """Prints examples of using the script to the console using colored output.
    """
    script = "Continuous Integration Scripts Unit Testing"
    explain = ("Since scripts behave differently based on the arguments and combinations "
               "of arguments you pass them, they can't be tested nicely without "
               "duplicating code. This script provides a framework for testing the scripts "
               "that ship with the CI server and the various combinations of arguments "
               "that can be passed to them.")
    contents = [(("Run all the tests for script arguments and combinations of script arguments "
                  "for the ci server."), "scripts.py ci",
                 ("You can also show the examples and help information for the ci.py script "
                  "by passing the '-texamples' and '-thelp' arguments."))]
    required = ("REQUIRED: a working installation of the code.")
    output = ("RETURNS: prints status information to stdout.")
    details = ""
    outputfmt = ""
    from pyci.msg import example
    example(script, explain, contents, required, output, outputfmt, details)

def _parser_options():
    """Parses the options and arguments from the command line."""
    from os import getcwd
    sys.path.insert(0, getcwd())
    
    import argparse
    bparser = argparse.ArgumentParser(add_help=False)
    bparser.add_argument("-examples", action="store_true",
                        help="See detailed help and examples for this script.")
    args = vars(bparser.parse_known_args()[0])
    if args["examples"]:
        examples()
        exit(0)

    parser = argparse.ArgumentParser(parents=[bparser],
                                     description="CI Server Script Testing Utility")
    parser.add_argument("scripts", nargs="+",
                        choices=["ci"],
                        help="Specify a list of scripts that you want to unit test.")
    parser.add_argument("-pypath",
                        help="Specify an additional path to add to sys.path.")
    parser.add_argument("-texamples", action="store_true",
                        help="Execute the scripts being unit tested with -examples")
    parser.add_argument("-thelp", action="store_true",
                        help="Show help/usage information for scripts being tested.")
    parser.add_argument("-all", action="store_true",
                        help="Run all the unit tests for CI server scripts.")
    parser.add_argument("-tverbose", action="store_true",
                        help="Run the unit tested scripts in verbose mode.")

    args.update(vars(parser.parse_known_args()[0]))

    #We use the pypath argument so that we can test the package without needing to
    #keep re-installing it after each change.
    if args["pypath"]:
        abspath = ppath.abspath(ppath.expanduser(args["pypath"]))
        sys.path.insert(0, abspath)
    else:
        args["pypath"] = getcwd()

    return args

def _test_generic(args, script, sargs=[]):
    """Executes the specified scripts and argument for a unit test.

    :arg script: the full path to the script to execute.
    :arg args: a list of arguments to pass to the script when it execs.
    :arg examples: when true, the script is run with only the '-examples'
      argument and 'args' is ignored.
    """
    gargs = ["python", script]
    if not args["texamples"]:
        gargs.extend(sargs)
    else:
        gargs.append("-examples")

    if args["tverbose"]:
        gargs.append("--verbose")
    if args["thelp"]:
        gargs.append("-h")

    context_exec(gargs, pypath=args["pypath"])

def _test_ci(args):
    """Tests the interaction of the ci.py script with the main library.
    """
    from pyci.msg import info
    spath = ppath.expanduser("~/codes/ci/pyci/scripts/ci.py")
    #This dictionary has a list of the script arguments that can test the various
    #functionality in the ci.py script.
    sargs = {
        "install": ["-install", "~/codes/ci/tests/repo.xml", "-nolive"],
        "uninstall": ["-uninstall", "~/codes/ci/tests/repo.xml", "-nolive"],
        "disable": ["-disable"],
        "enable": ["-enable"],
        "setup": ["-setup", "-nolive", "-cronfreq", "5"],
        "rollback": ["-rollback", "-nolive"],
        "cron": ["-cron", "-nolive"],
        "list": ["-list", "-nolive"]
    }
    order = ["enable", "install", "list", "uninstall", "disable", "cron", 
             "enable", "install", "cron", "setup", "rollback"]
    for key in order:
        _test_generic(args, spath, sargs[key])

if __name__ == '__main__':
    args = _parser_options()
    testdict = {
        "ci": _test_ci
    }

    if args["all"]:
        for testkey in testdict:
            if testdict[testkey] is not None:
                testdict[testkey](args)
    else:
        #Check whether we have a function defined for the unit test to perform and
        #then run it.
        for script in args["scripts"]:
            if script in testdict and testdict[script] is not None:
                testdict[script](args)
