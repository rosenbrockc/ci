"""This module has methods that are common to all the unit tests involving
scripts that take arguments. These must necessarily be tested separately
from the normal unittest framework.
"""
import os
os.environ["PYCI_XML"] = "~/codes/ci/tests/global.xml"

def context_exec(args, filepath=None, script=True, pypath=None):
    """Executes the specified file within the context of the currently executing
    python script.

    :arg args: the arguments to execute in the shell. Should be a list where the
      first element is the executable and subsequent items are the args to pass to
      that executable. The args list is joined with spaces, so no spaces should be
      included in the separate arguments.
    :arg filepath: if the execution is of a pure python module (and not a script)
      that will have its symbols loaded into the global table, specify the path to
      the *.py file here. In that case, you can leave 'args'=[]
    :arg script: when true, the execution is treated as a script by calling the
      args in the bash shell.
    :arg pypath: the path to an addtional folder to include in $PYTHONPATH when the
      execution is of a script in a new terminal process.
    """
    if script:
        from subprocess import Popen
        from os import waitpid
        if pypath is not None:
            args.insert(0, 'PYTHONPATH="{}"'.format(pypath))
        child=Popen(' '.join(args), shell=True, executable="/bin/bash")
        waitpid(child.pid, 0)
    elif filepath is not None:
        with open(filepath) as f:
            code = compile(f.read(), filepath, 'exec')
            exec(code)
