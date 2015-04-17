"""This module handles writing to the terminal or a log file with support
for coloring for warnings, errors, etc."""
from termcolor import cprint

verbose = False
"""Specifies whether the messager is running in verbose mode across all modules.
"""

def example(script, explain, contents, requirements, output, outputfmt, details):
    """Prints the example help for the script."""
    blank()
    cprint(script.upper(), "yellow")
    cprint(''.join(["=" for i in range(70)]) + '\n', "yellow")

    cprint("DETAILS", "blue")
    std(explain + '\n')

    cprint(requirements, "red")
    cprint(output, "green")
    blank()

    if details != "":
        std(details)
        blank()

    if outputfmt != "":
        cprint("OUTPUT FORMAT", "blue")
        std(outputfmt)
        blank()

    cprint("EXAMPLES", "blue")
    for i in range(len(contents)):
        pre, code, post = contents[i]
        std("{}) {}".format(i + 1, pre))
        cprint("    " + code, "cyan")
        if post != "":
            std('\n' + post)
        blank()

def warn(msg):
    """Prints the specified message as a warning; prepends "WARNING" to
    the message, so that can be left off.
    """
    cprint("WARNING: " + msg, "yellow")

def err(msg):
    """Prints the specified message as an error; prepends "ERROR" to
    the message, so that can be left off.
    """
    cprint("ERROR: " + msg, "red")

def info(msg):
    """Prints the specified message as information."""
    cprint(msg, "cyan")

def okay(msg):
    """Prints the specified message as textual progress update."""
    cprint(msg, "green")

def std(msg):
    """Prints the message as generic output to terminal."""
    cprint(msg, "white")

def blank(n=1):
    """Prints a blank line to the terminal."""
    for i in range(n):
        print("")

def set_verbose(verbosity):
    """Sets the global verbosity for all modules."""
    global verbose
    verbose = verbosity
        
def vms(message, level=1):
    """Writes the specified message *only* if verbose output is enabled."""
    if verbose is not None and verbose != False:
        if isinstance(verbose, bool) or (isinstance(verbose, int) and level <= verbose):
            std(message)
