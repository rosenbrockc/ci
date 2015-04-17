#!/usr/bin/python
"""High-level interface to the classes and methods in the package.
"""
from pyci.msg import err, warn, okay, info, vms, set_verbose

settings = None
"""The GlobalSettings instance with interpreted contents of 'global.xml'.
"""
db = {}
"""The scripts database which includes cron status, enabled status and a
list of the installed repositories.
"""
datapath = None
"""The full path to the data file to which 'db' is serialized."""
args = None
"""The dictionary of arguments passed to the script."""

def examples():
    """Prints examples of using the script to the console using colored output.
    """
    script = "Continuous Integration Automation Server"
    explain = ("For complex codes with many collaborators, it is often difficult to maintian "
               "a pristine code that everyone can rely on. If every developer has power to "
               "commit to master, unintentional mistakes happen that can cripple those who "
               "rely on the code for day-to-day business. One way to overcome this is to isolate "
               "the master branch and require collaborators to work on separate forks/branches. "
               "When they are ready to commit their changes to master, they create a pull request "
               "that summarizes the changes and why they want to merge them into the master branch.\n\n"
               "A continuous integration server monitors repositories for new pull requests. When a new "
               "request is made, the proposed changes are downloaded to a local sandbox and tested "
               "against all the existing code. If the master branch has a rich suite of unit tests "
               "this will detect any bugs in the proposed merger. If all the tests pass, then the "
               "owner of the master branch can have confidence that the merger will be okay.")
    contents = [(("Configure this machine to be a CI server. Unfortunately, this step requires "
                  "sudo authority because the API accesses the crontab for arbitrary users."), 
                 "sudo ci.py -setup", 
                 ("Before this setup can proceed, you need to make sure the global configuration "
                  "XML file has been created and the environment variable to its path has been set:\n"
                  "\texport PYCI_XML='~/path/to/global.xml'.\nSee also: -rollback")),
                (("Remove the cron tab from the server, delete the list of installed repositories "
                  "and undo anything else that the script did when -setup was used."),
                 "sudo ci.py -rollback",
                 ("This action deletes the files specified in 'ARCHFILE' and 'DATAFILE' in 'global.xml'. "
                  "Also, the crontab is removed, which is why sudo privileges are needed. See also -setup.")),
                (("Install the repository described by myrepo.xml onto the CI server so that "
                  "it's pull requests are monitored and unit ,tested."),
                 "ci.py -install myrepo.xml",
                 ("After installation, you can query the repository immediately by running the "
                  "script with -cron. You can install a list of repositories with a single command."
                  "See also -uninstall.")),
                (("Run the routines that check for new pull requests, run the unit tests, and post "
                  "the results to the media wiki."),
                 "ci.py -cron", "")]
    required = ("REQUIRED:\n\t-'repo.xml' file for *each* repository that gets installed on the server.\n"
                "\t-'global.xml' file with configuration settings for *all* repositories.\n"
                "\t- git user and API key with push access for *each* repository installed.")
    output = ("RETURNS: prints status information to stdout.")
    details = ("This script installs a continous integration server on the local machine by "
               "configuring a cron to call this script every couple of minutes. The script interacts "
               "with github using an API to monitor the pull requests. When new ones are found, the "
               "list of tests specified in the 'repo.xml' file is executed and the results are posted "
               "to a media wiki page associated with the specific pull request. For more details, see "
               "the online repo at https://github.com/rosenbrockc/ci.")
    outputfmt = ("")

    from pyci.msg import example
    example(script, explain, contents, required, output, outputfmt, details)

def _parser_options():
    """Parses the options and arguments from the command line."""
    import argparse
    parser = argparse.ArgumentParser(description="UNCLE Cron Server")
    parser.add_argument("-examples", action="store_true",
                        help="Display examples of how to use this script.")
    parser.add_argument("-setup", action="store_true",
                        help=("Setup the cron tab and script database for this server so "
                              "that it is ready to have repositories installed."))
    parser.add_argument("-rollback", action="store_true",
                        help=("Remove this script's cron tab and reverse other things done "
                              "by this script. This does not delete this script."))
    parser.add_argument("-enable", action="store_true",
                        help="Re-enable the continuous integration server.")
    parser.add_argument("-disable", action="store_true",
                        help=("Disable the continuous integration server so that it no longer "
                              "monitors the installed repositories."))
    parser.add_argument("-cron", action="store_true",
                        help=("Run the continuous integration routines for all the repos installed "
                              "in this script's database."))
    parser.add_argument("-list", action="store_true",
                        help="List all the repositories in the CI server's database.")
    parser.add_argument("-install", nargs="+",
                        help=("Install the specified XML file(s) as repositories to be monitored "
                              "by the CI server."))
    parser.add_argument("-uninstall", nargs="+",
                        help=("Uninstall the specified XML file(s) as repositories from "
                              "the CI server."))
    parser.add_argument("--verbose", nargs="?", type=int, const=1,
                        help="Runs the CI server in verbose mode.")
    parser.add_argument("-cronfreq", type=int, default=1,
                        help="Specify the frequency at which the cron runs.")
    parser.add_argument("-nolive", action="store_true",
                        help=("For unit testing, when specified no live requests are made to "
                              "servers and all the class actions are performed in test mode. "
                              "This also prevents the cron tab from being installed."))

    global args
    args = vars(parser.parse_known_args()[0])

    if args["examples"]:
        examples()
        exit(0)

    return args

def _load_db():
    """Deserializes the script database from JSON."""
    from os import path
    from pyci.utility import get_json
    global datapath, db
    datapath = path.abspath(path.expanduser(settings.datafile))
    vms("Deserializing DB from {}".format(datapath))
    db = get_json(datapath, {"installed": [], "enabled": True, "cron": False})

def _save_db():
    """Serializes the contents of the script db to JSON."""
    from pyci.utility import json_serial
    import json
    vms("Serializing DB to JSON in {}".format(datapath))
    with open(datapath, 'w') as f:
        json.dump(db, f, default=json_serial)
        
def _get_real_user():
    """Returns the name of the actual user account, even if running in sudo."""
    import os
    return os.path.expanduser("~").split("/")[-1]

def _check_virtualenv():
    """Makes sure that the virtualenv specified in the global settings file
    actually exists.
    """
    from os import waitpid
    from subprocess import Popen, PIPE
    penvs = Popen("source /usr/local/bin/virtualenvwrapper.sh; workon",
                 shell=True, executable="/bin/bash", stdout=PIPE, stderr=PIPE)
    waitpid(penvs.pid, 0)
    envs = penvs.stdout.readlines()
    enverr = penvs.stderr.readlines()
    result = (settings.venv + '\n') in envs and len(enverr) == 0

    vms("Find virtualenv: {}".format(' '.join(envs).replace('\n', '')))
    vms("Find virtualenv | stderr: {}".format(' '.join(enverr)))
    
    if not result:
        info(envs)
        err("The virtualenv '{}' does not exist; can't use CI server.".format(settings.venv))
        if len(enverr) > 0:
            map(err, enverr)
    return result

def _check_global_settings():
    """Makes sure that the global settings environment variable and file
    exist for configuration.
    """
    global settings
    if settings is not None:
        #We must have already loaded this and everything was okay!
        return True
    
    from os import getenv
    result = False
    
    if getenv("PYCI_XML") is None:
        err("The environment variable PYCI_XML for the global configuration "
            "has not been set.")
    else:
        from os import path
        fullpath = path.abspath(path.expanduser(getenv("PYCI_XML")))
        if not path.isfile(fullpath):
            err("The file {} for global configuration does not exist.".format(fullpath))
        else:
            from pyci.config import GlobalSettings
            settings = GlobalSettings()
            result = True

    return result

def _setup_crontab():
    """Sets up the crontab if it hasn't already been setup."""
    from crontab import CronTab
    command = "workon {}; {}".format(settings.venv, os.path.realpath(__file__) + " -cron")
    user = _get_real_user()
    if args["nolive"]:
        vms("Skipping cron tab configuration because 'nolive' enabled.")
        return
    cron = CronTab(user=user)
    
    #We need to see if the cron has already been created for this command.
    existing = False
    possible = cron.find_command(command)
    if len(possible) > 0:
        if args["rollback"]:
            vms("Removing {} from cron tab.".format(command))
            cron.remove_all(command)
            db["cron"] = False
            _save_db()
        else:
            existing = True
    
    if not existing and not args["rollback"]:
        job = cron.new(command=command)
        #Run the cron every minute of every hour every day.
        if args["cronfreq"] == 1:
            vms("New cron tab configured *minutely* for {}".format(command))
            job.setall("* * * * *")
        else:
            vms("New cron tab configured every {} minutes for {}.".format(args["cronfreq"], command))
            job.setall("*/{} * * * *".format(args["cronfreq"]))
        cron.write()
        db["cron"] = True
        _save_db()

def _setup_server():
    """Checks whether the server needs to be setup if a repo is being installed.
    If it does, checks whether anything needs to be done.
    """
    if args["setup"] or args["install"]:
        #If the cron has been configured, it means that the server has been
        #setup. We also perform some checks of the configuration file and the
        #existence of the virtualenv.
        if not _check_global_settings() or not _check_virtualenv():
            return False

        if "cron" in db and not db["cron"]:
            _setup_crontab()

    if (args["rollback"] and "cron" in db and db["cron"]):
        _setup_crontab()

def _server_rollback():
    """Removes script database and archive files to rollback the CI server
    installation.
    """
    #Remove the data and archive files specified in settings. The cron
    #gets remove by the _setup_server() script if -rollback is specified.
    from os import path, remove
    archpath = path.abspath(path.expanduser(settings.archfile))
    if path.isfile(archpath) and not args["nolive"]:
        vms("Removing archive JSON file at {}.".format(archpath))
        remove(archpath)
    datapath = path.abspath(path.expanduser(settings.datafile))
    if path.isfile(datapath) and not args["nolive"]:
        vms("Removing script database JSON file at {}".format(datapath))
        remove(datapath)

def _server_enable():
    """Checks whether the server should be enabled/disabled and makes the
    change accordingly.
    """
    prev = None if "enabled" not in db else db["enabled"]
    if args["disable"]:
        db["enabled"] = False
        okay("Disabled the CI server. No pull requests will be processed.")

    if args["enable"]:
        db["enabled"] = True
        okay("Enabled the CI server. Pull request monitoring online.")

    #Only perform the save if something actually changed.
    if prev != db["enabled"]:
        _save_db()        

def _find_next(server):
    """Finds the name of the next repository to run based on the *current*
    state of the database.
    """
    from datetime import datetime
    #Re-load the database in case we have multiple instances of the script
    #running in memory.
    _load_db()
    result = None
    visited = []
    
    if "status" in db:
        for reponame, status in db["status"].items():
            vms("Checking cron status for {}: {}".format(reponame, status))
            start = None if "started" not in status else status["started"]
            end = None if "end" not in status else status["end"]
            running = start is not None and end is not None and start > end
            add = False
            
            if not running and end is not None:
                #Check the last time it was run and see if enough time has
                #elapsed.
                elapsed = (datetime.now() - end).seconds/60
                add = elapsed > server.cron.settings[reponame].frequency
                if not add:
                    vms("'{}' skipped because the interval hasn't ".format(reponame) +
                        "elapsed ({} vs. {})".format(elapsed, server.cron.settings[reponame].frequency))
            elif end is None:
                add = True

            if add:
                result = reponame
                break
            visited.append(reponame)
    else:
        db["status"] = {}        


    if result is None:
        #We still need to check the newly installed repos.            
        for reponame, repo in server.repositories.items():
            if reponame not in visited:
                #These are newly installed repos that have never run before.
                vms("Added '{}' as new repo for cron execution.".format(reponame))
                result = reponame
                break

    return result

def _do_cron():
    """Handles the cron request to github to check for new pull requests. If
    any are found, they are run *sequentially* until they are all completed.
    """
    if not args["cron"]:
        return
    
    if ("enabled" in db and not db["enabled"]) or "enabled" not in db:
        warn("The CI server is disabled. Exiting.")
        exit(0)
    #Our basic idea with the cron is as follows:
    # - the cron runs every minute of the day.
    # - each installed XML file has the last time it ran saved in the script's
    #   database. If the specified check frequency has elapsed since it last
    #   ran, then we run the repository server checks.
    # - NB: before running the time-intensive checks against remote servers
    #   or running the unit tests, first update the running status of the repo
    #   so that another call with -cron doesn't duplicate the work!

    #By having the cron run every minute, we maximize the probability that
    #repo checks with time intensive unit tests may run in parallel. Since
    #servers usually have many cores, this shouldn't impact the run times too
    #severely unless the tests are disk intensive.

    #We use the repo full names as keys in the db's status dictionary.
    from pyci.server import Server
    from datetime import datetime
    attempted = []
    server = Server(testmode=args["nolive"])
    nextrepo = _find_next(server)
    dbs = db["status"]
    
    while nextrepo is not None:
        vms("Working on '{}' in cron.".format(nextrepo))
        if nextrepo in attempted:
            #This makes sure we don't end up in an infinite loop.
            vms("'{}' has already been handled! Exiting infinite loop.".format(nextrepo))
            break
        
        if nextrepo not in dbs:
            vms("Created blank status dictionary for '{}' in db.".format(nextrepo))
            dbs[nextrepo] = {"start": None, "end": None}
        dbs[nextrepo]["start"] = datetime.now()
        _save_db()

        #Now that we have saved our intent to run these repo-checks, let's
        #actually run them.
        attempted.append(nextrepo)
        server.runnable = [nextrepo]
        if not args["nolive"]:
            vms("Starting pull request processing for '{}'.".format(nextrepo))
            server.process_pulls()
    
        dbs[nextrepo]["end"] = datetime.now()
        _save_db()
        nextrepo = _find_next(server)

def _fmt_time(time):
    """Returns the formatted time if it is not None."""
    if time is not None:
        return time.strftime("%m/%d/%Y %H:%M")
    else:
        return "-"
    
def _list_repos():
    """Lists all the installed repos as well as their last start and finish
    times from the cron's perspective.
    """
    if not args["list"]:
        return
    
    #Just loop over the list of repos we have in a server instance. See if
    #they also exist in the db's status; if they do, include the start/end
    #times we have saved.
    from pyci.server import Server
    server = Server(testmode=args["nolive"])
    output = ["Repository           |      Started     |      Finished    | XML File Path",
              "--------------------------------------------------------------------------"]

    dbs = {} if "status" not in db else db["status"]
    fullfmt = "{0:<20} | {1:^16} | {2:^16} | {3}"
    for reponame, repo in server.repositories.items():
        if reponame in dbs:
            start = _fmt_time(dbs[reponame]["start"])
            end = _fmt_time(dbs[reponame]["end"])
            output.append(fullfmt.format(reponame, start, end, repo.filepath))

    info('\n'.join(output))

def _handle_install():
    """Handles the (un)installation of repositories on this CI server.
    """
    from pyci.server import Server
    if args["install"]:
        server = Server(testmode=args["nolive"])
        for xpath in args["install"]:
            server.install(xpath)
            okay("Installed {} into the CI server.".format(xpath))
    if args["uninstall"]:
        server = Server(testmode=args["nolive"])
        for xpath in args["uninstall"]:
            server.uninstall(xpath)
            okay("Uninstalled {} from the CI server.".format(xpath))
    
def run():
    """Main script entry to handle the arguments given to the script."""
    _parser_options()
    set_verbose(args["verbose"])
    
    if _check_global_settings():
        _load_db()
    else:
        exit(-1)

    #Check the server configuration against the script arguments passed in.
    _setup_server()

    if args["rollback"]:
        _server_rollback()
        okay("The server rollback appears to have been successful.")
        exit(0)

    _server_enable()    
    _list_repos()
    _handle_install()
    
    #This is the workhorse once a successful installation has happened.
    _do_cron()
        
if __name__ == "__main__":
    run()
