from config import RepositorySettings, GlobalSettings
from pyci.msg import warn, err

class Server(object):
    """Represents the continuous integration server for automatically unit testing
    repositories and updating status information.
    """
    def __init__(self, datafile=None, archfile=None, testmode=False):
        """
        :arg datafile: the path to the JSON data file with a list of repo settings
          file paths defining the repos being monitored.
        :arg archfile: the path to the JSON archive file for the pull requests
          that have been processed already by the server.
        :arg testmode: when true, this class is instantiated in test mode so that
          the live requests are skipped.
        """
        self.settings = GlobalSettings()
        """Instance of GlobalSettings with CI server settings that affect *all*
        the repos being monitored.
        """
        self.testmode = testmode
        """when true, this class is instantiated in test mode so that
        the live requests are skipped."""

        from os import path
        self.instpath = path.abspath(path.expanduser(datafile if datafile is not None
                                                     else self.settings.datafile))
        """The absolute path to the data file listing the repo settings files that
        have been installed on this CI server.
        """
        self.archpath = path.abspath(path.expanduser(archfile if archfile is not None
                                                     else self.settings.archfile))
        """The absolute path to the data file with pull request processing information
        from previous runs of the CI server.
        """
        
        self.installed = self._get_installed()
        """A list of file paths to repo XML settings files for repos that need to
        be monitored.
        """
        self.cron = CronManager(self)
        """An instance of CronManager to handle the automation timing and events
        including the email notifications.
        """
        self.wiki = Wiki(self, testmode)
        """An instance of Wiki for creating and editing Media Wiki pages with the
        results of the unit tests.
        """
        self.repositories = self._get_repos()
        """Dictionary of repositories that are being monitored by this CI server.
        """
        self.archive = self._get_archive()
        """Dictionary indexed by repository full-name that has lists of SHA keys
        for pull-request commits that have already been processed by the server.
        """
        self.runnable = None
        """A list of repository names that have been authorized to run by the
        calling script. If None, the constraint is not applied.
        """

    @property
    def dirname(self):
        """Returns the full path to the directory that contains the 'server.py' file.
        """
        from os import path
        return path.abspath(path.dirname(__file__))

    def _get_fields(self, event, pull, message=None):
        """Constructs a dictionary of fields and replacement values based on the
        specified event and the status of the pull request.
        
        :arg event: one of ["start", "error", "finish"].
        :arg pull: an instance of PullRequest that has details about the current
          status of the pull request testing etc.
        :arg message: an additional contextual message to add in the __message__ field.
        """
        result = pull.fields_general(event)            
        if message is not None:
            result["__message__"] = message
            
        return result
    
    def process_pulls(self, testpulls=None, testarchive=None, expected=None):
        """Runs self.find_pulls() *and* processes the pull requests unit tests,
        status updates and wiki page creations.

        :arg expected: for unit testing the output results that would be returned
          from running the tests in real time.
        """
        from datetime import datetime
        pulls = self.find_pulls(testpulls.values())
        for reponame in pulls:
            for pull in pulls[reponame]:
                try:
                    archive = self.archive[pull.repokey]
                    if pull.snumber in archive:
                        #We pass the archive in so that an existing staging directory (if
                        #different from the configured one) can be cleaned up if the previous
                        #attempt failed and left the file system dirty.
                        pull.init(archive[pull.snumber])
                    else:
                        pull.init({})
                        
                    if self.testmode and testarchive is not None:
                        #Hard-coded start times so that the model output is reproducible
                        if pull.number in testarchive[pull.repokey]:
                            start = testarchive[pull.repokey][pull.number]["start"]
                        else:
                            start = datetime(2015, 4, 23, 13, 8)
                    else:
                        start = datetime.now()
                    archive[pull.snumber] = {"success": False, "start": start,
                                             "number": pull.number, "stage": pull.repodir,
                                             "completed": False, "finished": None}
                    #Once a local staging directory has been initialized, we add the sha
                    #signature of the pull request to our archive so we can track the rest
                    #of the testing process. If it fails when trying to merge the head of
                    #the pull request, the exception block should catch it and email the
                    #owner of the repo.
                    #We need to save the state of the archive now in case the testing causes
                    #an unhandled exception.
                    self._save_archive()

                    pull.begin()
                    self.cron.email(pull.repo.name, "start", self._get_fields("start", pull), self.testmode)
                    pull.test(expected[pull.number])
                    pull.finalize()

                    #Update the status of this pull request on the archive, save the archive
                    #file in case the next pull request throws an unhandled exception.
                    archive[pull.snumber]["completed"] = True
                    archive[pull.snumber]["success"] = abs(pull.percent - 1) < 1e-12

                    #This if block looks like a mess; it is necessary so that we can easily
                    #unit test this processing code by passing in the model outputs etc. that should
                    #have been returned from running live.
                    if (self.testmode and testarchive is not None and
                        pull.number in testarchive[pull.repokey] and
                        testarchive[pull.repokey][pull.number]["finished"] is not None):
                        archive[pull.snumber]["finished"] = testarchive[pull.repokey][pull.number]["finished"]
                    elif self.testmode:
                        archive[pull.snumber]["finished"] = datetime(2015, 4, 23, 13, 9)
                    else:
                        #This single line could replace the whole if block if we didn't have
                        #unit tests integrated with the main code.
                        archive[pull.snumber]["finished"] = datetime.now()
                    self._save_archive()

                    #We email after saving the archive in case the email server causes exceptions.
                    if archive[pull.snumber]["success"]:
                        key = "success"
                    else:
                        key = "failure"
                    self.cron.email(pull.repo.name, key, self._get_fields(key, pull), self.testmode)
                except:
                    import sys, traceback
                    e = sys.exc_info()
                    errmsg = '\n'.join(traceback.format_exception(e[0], e[1], e[2]))
                    err(errmsg)
                    self.cron.email(pull.repo.name, "error", self._get_fields("error", pull, errmsg),
                                    self.testmode)
                
    def find_pulls(self, testpulls=None):
        """Finds a list of new pull requests that need to be processed.

        :arg testpulls: a list of tserver.FakePull instances so we can test the code
          functionality without making live requests to github.
        """
        #We check all the repositories installed for new (open) pull requests.
        #If any exist, we check the pull request number against our archive to
        #see if we have to do anything for it.
        result = {}
        for lname, repo in self.repositories.items():
            if lname not in self.archive:
                raise ValueError("Trying to find pull requests for a repository "
                                 "that hasn't been installed. Use server.install().")
            if self.runnable is not None and lname not in self.runnable:
                #We just ignore this repository completely and don't even bother
                #performing a live check on github.
                continue
            
            pulls = testpulls if testpulls is not None else repo.repo.get_pulls("open")
            result[lname] = []
            for pull in pulls:
                newpull = True
                if pull.snumber in self.archive[lname]:
                    #Check the status of that pull request processing. If it was
                    #successful, we just ignore this open pull request; it is
                    #obviously waiting to be merged in.
                    if self.archive[lname][pull.snumber]["completed"] == True:
                        newpull = False

                if newpull:
                    #Add the pull request to the list that needs to be processed.
                    #We don't add the request to the archive yet because the
                    #processing step hasn't happened yet.
                    result[lname].append(PullRequest(self, repo, pull, testpulls is not None))

        return result
    
    def _get_archive(self):
        """Loads the archive of previously processed pull requests for all repos
        being monitored by this server.
        """
        from utility import get_json
        return get_json(self.archpath, {})

    def _save_archive(self):
        """Saves the JSON archive of processed pull requests.
        """
        import json
        from utility import json_serial
        with open(self.archpath, 'w') as f:
            json.dump(self.archive, f, default=json_serial)
    
    def _get_repos(self):
        """Gets a list of all the installed repositories in this server.
        """
        result = {}
        for xmlpath in self.installed:
            repo = RepositorySettings(self, xmlpath)
            result[repo.name.lower()] = repo

        return result
            
    def _get_installed(self):
        """Gets a list of the file paths to repo settings files that are
        being monitored by the CI server.
        """
        from utility import get_json
        #This is a little tricky because the data file doesn't just have a list
        #of installed servers. It also manages the script's database that tracks
        #the user's interactions with it.
        fulldata = get_json(self.instpath, {})
        if "installed" in fulldata:
            return fulldata["installed"]
        else:
            return []

    def uninstall(self, xmlpath):
        """Uninstalls the repository with the specified XML path from the server.
        """
        from os import path
        fullpath = path.abspath(path.expanduser(xmlpath))
        if fullpath in self.installed:
            repo = RepositorySettings(self, fullpath)
            if repo.name.lower() in self.repositories:
                del self.repositories[repo.name.lower()]
            if repo.name.lower() in self.archive:
                del self.archive[repo.name.lower()]
                self._save_archive()
            self.installed.remove(fullpath)
            self._save_installed()
        else:
            warn("The repository at {} was not installed to begin with.".format(fullpath))        
        
    def install(self, xmlpath):
        """Installs the repository at the specified XML path as an additional
        repo to monitor pull requests for.
        """
        #Before we can install it, we need to make sure that none of the existing
        #installed paths point to the same repo.
        from os import path
        fullpath = path.abspath(path.expanduser(xmlpath))
        if path.isfile(fullpath):
            repo = RepositorySettings(self, fullpath)
            if repo.name.lower() not in self.repositories:
                self.installed.append(fullpath)
                self._save_installed()
                self.archive[repo.name.lower()] = {}
                self._save_archive()
                
                self.repositories[repo.name.lower()] = repo
        else:
            warn("The file {} does not exist; install aborted.".format(fullpath))
    
    def _save_installed(self):
        """Saves the list of installed repo XML settings files."""
        import json
        from utility import json_serial, get_json
        #This is a little tricky because the data file doesn't just have a list
        #of installed servers. It also manages the script's database that tracks
        #the user's interactions with it.
        fulldata = get_json(self.instpath, {})
        fulldata["installed"] = self.installed
        with open(self.instpath, 'w') as f:
            json.dump(fulldata, f, default=json_serial)
    
class PullRequest(object):
    """Represents a single, open pull request on a repository that needs to be
    downloaded, unit tested and then have its stated updated.
    """
    def __init__(self, server, repo, pull, testmode=False):
        """
        :arg testmode: when true, this class is instantiated in test mode so that
          the live requests are skipped.
        """
        self.server = server
        """Server instance with cron, wiki and settings classes."""
        self.repo = repo
        """The RepositorySettings object to use for the processing."""
        self.pull = pull
        """github.PullRequest.PullRequest instance with information
        about the commits."""
        if testmode:
            self.commit = None
            """The last commit (by whatever ordering the API presents them in. Status
            information for the pull request is posted to this commit, making it the
            representative commit for the PR.
        """
        else:
            self.commit = pull.get_commits()[-1]
            
        self.url = None
        """The URL to the wiki page with details about the unit tests."""
        self.repodir = None
        """The full path to the staging directory for the repo."""
        self.testmode = testmode
        """when true, this class is instantiated in test mode so that
        the live requests are skipped."""

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    @property
    def repokey(self):
        """Returns the lowered full-name of the repository, which is used as a key
        in dictionaries of repos.
        """
        return self.repo.name.lower()

    @property
    def snumber(self):
        """Returns the pull request's number as a string. Necessary because the JSON
        serialization turns the numerical keys on dicts into strings; but they don't
        get deserialized correctly.
        """
        return str(self.number)
    
    @property
    def number(self):
        """Returns the number of the pull request on github.
        """
        return self.pull.number
    
    def init(self, archive):
        """Creates the repo folder locally, copies the static files and 
        folders available locally, initalizes the repo with git so it
        has the correct remote origin and is ready to sync.

        :arg staging: the full path to the directory to stage the unit tests in.
        """
        from os import makedirs, path, chdir, system, getcwd
        self.repodir = path.abspath(path.expanduser(self.repo.staging))

        if ("stage" in archive and path.isdir(archive["stage"]) and
            self.repodir != archive["stage"] and archive["stage"] is not None):
            #We have a previous attempt in a different staging directory to clean.
            from shutil import rmtree
            rmtree(archive["stage"])

        if not path.isdir(self.repodir):
            makedirs(self.repodir)
            
        #Copy across all the static files so that we don't have to download them
        #again and chew up the bandwidth. We don't have to copy files that already
        #exist in the local repo.
        self.repo.static.copy(self.repodir)
        cwd = getcwd()
        chdir(self.repodir)
        
        if not self._is_gitted():
            #Next we need to initialize the git repo, then add all the static files
            #and folders to be tracked so that when we pull from origin master they
            #can be merged into the repo without re-downloading them.
            system("git init")
            if not self.testmode:
                system("git remote add origin {}.git".format(self.repo.repo.html_url))

            for file in self.repo.static.files:
                #Here the 2:: removes the ./ specifying the path relative to the git
                #repository root. It is added by convention in the config files.
                system("git add {}".format(file["target"][2::]))
            for folder in self.repo.static.folders:
                system("git add {}".format(file["target"][2::]))

            #Now sync with the master branch so that we get everything else that isn't
            #static. Also, fetch the changes from the pull request head so that we
            #can merge them into a new branch for unit testing.
            if not self.testmode:
                system("git pull origin master")

        #Even though we have initialized the repo before, we still need to fetch the
        #pull request we are wanting to merge in.
        if not self.testmode:
            system("git fetch origin pull/{0}/head:testing_{0}".format(self.pull.number))
            system("git checkout testing_{}".format(pull.number))

        #The local repo now has the pull request's proposed changes and is ready
        #to be unit tested.
        chdir(cwd)

    def _is_gitted(self):
        """Returns true if the current repodir has been initialized in git *and*
        had a remote origin added *and* has a 'testing' branch.
        """
        from os import waitpid
        from subprocess import Popen, PIPE
    
        premote = Popen("cd {}; git remote -v".format(self.repodir),
                        shell=True, executable="/bin/bash", stdout=PIPE, stderr=PIPE)
        waitpid(premote.pid, 0)
        remote = premote.stdout.readlines()
        remerr = premote.stderr.readlines()

        pbranch = Popen("cd {}; git branch".format(self.repodir),
                        shell=True, executable="/bin/bash", stdout=PIPE, stderr=PIPE)
        waitpid(pbranch.pid, 0)
        branch = pbranch.stdout.readlines()
        braerr = pbranch.stderr.readlines()

        if len(remote) > 0 and len(remerr) > 0 and len(branch) > 0:
            return ((".git" in remote[0] and "fatal" not in remerr[0])
                    and any(["testing" in b for b in branch]))
        elif self.testmode and len(remote) == 0 and len(branch) == 0 and len(remerr) == 0:
            return True
        else:
            return False
        
    def begin(self):
        """Sets the status message on the *last* commit for this pull request
        to be 'pending' with a details link to a newly created Wiki page with
        the setup of the unit tests being run. Does *not* run the actual unit
        tests yet.
        """
        self.url = self.server.wiki.create(self)
        if not self.testmode:
            self.commit.create_status("pending", self.url, "Running unit tests...")

    def test(self, testresults=None):
        """Runs the unit test commands specified in the repo settings in parallel,
        keeping track of the results of each one.

        :arg testresults: a dictionary (indexed by integer index of the test
          command) to use as the expected output of executing the commands in parallel.
        """
        from multiprocessing import Process, Queue
        from utility import run_exec
        from datetime import datetime

        # Setup a list of processes that we want to run.
        output = Queue()
        processes = []
        for i, test in enumerate(self.repo.testing.tests):
            #Before the command is ready to run, we need to replace any custom variables.
            test["command"] = self.server.settings.var_replace(test["command"])
            processes.append(Process(target=run_exec, args=(self.repodir, test["command"], output, i)))
            if self.testmode:
                #We need to hardcode the date and time so that it always matches the model
                #output we expect.
                test["start"] = datetime(2015, 04, 23, 13, 04)
            else:
                test["start"] = datetime.now()
            if not self.testmode:
                processes[-1].start()
            
        #Wait for the unit tests to all finish. TODO: add a loop that waits for a few
        #seconds before checking each of them in turn. Don't block until they are just
        #finished. We need to cancel them all if the timeout value specified in the
        #TODO: enforce the setting for serial="true".
        #config file is reached.
        ordered = testresults
        if not self.testmode:
            for p in processes:
                p.join()
            results = [output.get() for p in processes]
            ordered = {o["index"]: o for o in results}
            
        for i, test in enumerate(self.repo.testing.tests):
            result = ordered[i]
            test["end"] = result["end"]
            test["success"] = result["code"] == 0 or result["code"] == 1
            test["code"] = result["code"]
            test["result"] = result["output"]      

    def finalize(self):
        """Finalizes the pull request processing by updating the wiki page with
        details, posting success/failure to the github pull request's commit.
        """
        #Determine the percentage success on the unit tests. Also see the total time for all
        #the unit tests.
        stotal = 0
        ttotal = 0
        for test in self.repo.testing.tests:
            stotal += (1 if test["success"]==True else 0)
            ttotal += (test["end"] - test["start"]).seconds

        self.percent = stotal/float(len(self.repo.testing.tests))
        self.message = "Results: {0:.2%} in {1:d}s.".format(self.percent, ttotal)
        if not self.testmode:
            if percent < 1:
                self.commit.create_status("failure", self.url, self.message)
            elif any([test["code"] == 1 for test in self.repo.testing.tests]):
                self.commit.create_status("pending", self.url, self.message + " Slowdown reported.")
            else:
                self.commit.create_status("success", self.url, self.message)
        self.server.wiki.update(self)

    def _fields_common(self):
        """Returns a dictionary of fields and values that are common to all events
        for which fields dictionaries are created.
        """
        result = {}
        if not self.testmode:
            result["__reponame__"] = self.repo.repo.full_name
            result["__repodesc__"] = self.repo.repo.description
            result["__repourl__"] = self.repo.repo.html_url
            result["__repodir__"] = self.repodir

            if self.organization is not None:
                owner = self.repo.organization
            else:
                owner = self.repo.user
                
            result["__username__"] = owner.name
            result["__userurl__"] = owner.html_url
            result["__useravatar__"] = owner.avatar_url
            result["__useremail__"] = owner.email

        return result

    def wiki(self):
        """Returns the wiki markup describing the details of the github pull request
        as well as a link to the details on github.
        """
        date = self.pull.created_at.strftime("%m/%d/%Y %H:%M")
        return "{} {} ({} [{} github])\n".format(self.pull.avatar_url, self.pull.body, date,
                                                 self.pull.html_url)

    def fields_general(self, event):
        """Appends any additional fields to the common ones and returns the fields
        dictionary.
        """
        result = self._fields_common()
        basic = {
            "__test_html__": self.repo.testing.html(False),
            "__test_text__": self.repo.testing.text(False)}
        full = {
            "__test_html__": self.repo.testing.html(),
            "__test_text__": self.repo.testing.text()}
        
        if event in ["finish", "success"]:
            full["__percent__"] = "{0:.2%}".format(self.percent)
            full["__status__"] = self.message
        
        extra = {
            "start": basic,
            "error": basic,
            "finish": full,
            "success": full,
            "timeout": basic
        }
        if event in extra:
            result.update(extra[event])
        return result
            
    def fail(self, message):
        """Marks the testing of this pull request as having failed due to an uncaught
        exception generated by the CI server python script.
        """
        self.commit.create_status("error", self.url,
                                  "Uncaught exception in CI server. File a bug:\n\n" + message)
        
class Wiki(object):
    """Object for interacting with a media wiki installation to create pages with
    details of the output from the unit tests.
    """
    def __init__(self, server, testmode=False):
        """
        :arg server: The Server instance with global settings for accessing the wiki.
        :arg testmode: when true, this class is instantiated in test mode so that
          the live requests are skipped.
        """
        self.server = server
        """The Server instance with global settings for accessing the wiki."""
        self.url = None
        """The base url of the media wiki that we are posting to."""
        self.relpath = None
        """The relative path to the api.php page that handles API requests on the wiki."""
        self.basepage = None
        """The base page for the repo whose unit tests are being run and whose results will
        be appended to this page.
        """
        self.site = None
        """The mwclient.Site instance for accessing the media wiki."""
        self._newpage_head = ["This page was automatically created by the CI bot for holding details "
                              "of the automated unit testing for continuous integration.\n"]
        """Returns the first few lines of the new page being created."""
        self.testmode = testmode
        """when true, this class is instantiated in test mode so that
        the live requests are skipped."""
        self.prefix = None
        """The text prefix used in front of the pages and links created for this request.
        """
        self._get_site()

    def _get_site(self):
        """Returns the mwclient.Site for accessing and editing the wiki pages.
        """
        import mwclient
        parts = self.server.settings.wiki.replace("http", "").replace("://", "").split("/")
        self.url = parts[0]
        if len(parts) > 1 and parts[1].strip() != "":
            self.relpath = '/' + '/'.join(parts[1:len(parts)])
            #The API expects us to have a trailing forward-slash.
            if self.relpath[-1] != "/":
                self.relpath += "/"
            if not self.testmode:
                self.site = mwclient.Site(self.url, path=self.relpath)
        else:
            if not self.testmode:
                self.site = mwclient.Site(self.url)

    def _site_login(self, repo):
        """Logs the user specified in the repo into the wiki.

        :arg repo: an instance of config.RepositorySettings with wiki credentials.
        """
        try:
            if not self.testmode:
                self.site.login(repo.wiki["user"], repo.wiki["password"])
        except LoginError as e:
            print(e[1]['result'])
        self.basepage = repo.wiki["basepage"]
            
    def create(self, request):
        """Creates a new wiki page for the specified PullRequest instance. The page
        gets initialized with basic information about the pull request, the tests
        that will be run, etc. Returns the URL on the wiki.

        :arg request: the PullRequest instance with testing information.
        """
        self._site_login(request.repo)
        self.prefix = "{}_Pull_Request_{}".format(request.repo.name, request.pull.number)
        
        #We add the link to the main repo page during this creation; we also create
        #the full unit test report page here.
        self._edit_main(request)
        return self._create_new(request)

    def update(self, request):
        """Updates the wiki page with the results of the unit tests run for the 
        pull request.

        :arg percent: the percent success rate of the unit tests.
        :arg ttotal: the total time elapsed in running *all* the unit tests.
        """
        from os import path
        self._site_login(request.repo)
        self.prefix = "{}_Pull_Request_{}".format(request.repo.name, request.pull.number)
                
        #Before we can update the results from stdout, we first need to upload them to the
        #server. The files can be quite big sometimes; if a file is larger than 1MB, we ...
        for i, test in enumerate(request.repo.testing.tests):
            test["remote_file"] = "{}_{}.txt".format(self.prefix, i)
            if test["result"] is not None and path.isfile(test["result"]):
                #Over here, we might consider doing something different if the wiki server
                #is the same physical machine as the CI server; we needn't use the network
                #protocols for the copy then. However, the machine knows already if an address
                #it is accessing is its own; the copy, at worst, would be through the named
                #pipes over TCP. It is wasteful compared to a HDD copy, but simplifies the
                #uploading (which must also make an entry in the wiki database).
                if not self.testmode:
                    self.site.upload(open(test["result"]), test["remote_file"],
                                     '`stdout` from `{}`'.format(test["command"]))

        #Now we can just overwrite the page with the additional test results, including the
        #links to the stdout files we uploaded.
        head = list(self._newpage_head)
        #Add a link to the details page that points back to the github pull request URL.
        head.append("==Github Pull Request Info==\n")
        head.append(request.wiki())
        head.append("==Commands Run for Unit Testing==\n")
        head.append(request.repo.testing.wiki())
        if not self.testmode:
            page = self.site.Pages[self.newpage]
            result = page.save('\n'.join(head), summary='Edited by CI bot with uploaded unit test details.',
                               minor=True, bot=True)
            return result[u'result'] == u'Success'
        else:
            return '\n'.join(head)
            
    def _create_new(self, request):
        """Creates the new wiki page that houses the details of the unit testing runs.
        """
        self.prefix = "{}_Pull_Request_{}".format(request.repo.name, request.pull.number)
        head = list(self._newpage_head)
        head.append(request.repo.testing.wiki(False))
        if not self.testmode:
            page = self.site.Pages[self.newpage]
            result = page.save('\n'.join(head), summary='Created by CI bot for unit test details.', bot=True)
            return result[u'result'] == u'Success'
        else:
            return '\n'.join(head)
        
    def _edit_main(self, request):
        """Adds the link to the new unit testing results on the repo's main wiki page.
        """
        self.prefix = "{}_Pull_Request_{}".format(request.repo.name, request.pull.number)
        if not self.testmode:
            page = site.pages[self.basepage]
            text = page.text()
        else:
            text = "This is a fake wiki page.\n\n<!--@CI:Placeholder-->"
            
        self.newpage = self.prefix
        link = "Pull Request #{}".format(request.pull.number)
        text = text.replace("<!--@CI:Placeholder-->",
                            "* [[{}|{}]]\n<!--@CI:Placeholder-->".format(self.newpage, link))
        if not self.testmode:
            result = page.save(text, summary="Added {} unit test link.".format(link), minor=True, bot=True)
            return result[u'result'] == u'Success'
        else:
            return text

class CronManager(object):
    """Object to manage a set of repositories whose pull requests need to be
    monitored via cron every few minutes.
    """
    def __init__(self, server):
        self.server = server
        """Instance of the Server object handling the overall CI workflow.
        """
        self.settings = {}
        """Dictionary of specific cron settings for each repo being monitored.
        """

    def _get_template(self, event, ctype, fields):
        """Gets the contents of the template for the specified event and type
        with all the fields replaced.
        
        :arg event: one of ['start', 'error', 'success', 'timeout', 'failure'].
        :arg ctype: one of ["txt", "html"] specifying which template to use.
        :arg fields: a dictionary of fields and their replacement values to
          insert.
        """
        from os import path
        template = path.join(self.server.dirname, "templates", "{}.{}".format(event, ctype))
        contents = None
        
        if path.isfile(template):
            with open(template) as f:
                #The templates are very small, so we don't need to worry about the file size.
                contents = f.read()
            for field, value in fields.items():
                contents = contents.replace(field, value)
        else:
            raise ValueError("The event '{}' is not supported or ".format(event) +
                             "the template file ({}) is missing.".format(template))
        return contents
        
    def email(self, repo, event, fields, dryrun=False):
        """Sends an email to the configured recipients for the specified event.

        :arg repo: the name of the repository to include in the email subject.
        :arg event: one of ["start", "success", "failure", "timeout", "error"].
        :arg fields: a dictionary of field values to replace into the email template
          contents to specialize them.
        :arg dryrun: when true, the email object and contents are initialized, but
          the request is never sent to the SMTP server.
        """
        tcontents = self._get_template(event, "txt", fields)
        hcontents = self._get_template(event, "html", fields)
        if tcontents is not None and hcontents is not None:
            return Email(self.server, repo, self.settings[repo], tcontents, hcontents, dryrun)
        
class Email(object):
    """Handles the sending of email to users with progress information on the automation job.
    """
    def __init__(self, server, repo, cron, texts, htmls, dryrun=False):
        """Sets up an email with these settings and then sends it.

        :arg server: the Server instance for the entire CI workflow.
        :arg dryrun: when true, the email object and contents are initialized, but
          the request is never sent to the SMTP server.
        """
        self.sent = False
        """Specifies whether this email instance has sent itself yet."""
        self.to = cron.emails
        """The list of email addresses to send the email to."""
        self.sender = server.settings.from_address
        """The email address to send the email from."""
        self.text = None
        """The text version of the email to send.
        """
        self.html = None
        """HTML code to send as the default content of the email.
        """
        self.subject = "Continous Integration Report for '{}'".format(repo)
        """The subject of the email, specialized for the repo being notified."""

        self._send(server, texts, htmls, dryrun)

    def _send(self, server, texts, htmls, dryrun):
        """Sends the email using the configured settings.

        :arg server: the Server instance for the entire CI workflow.
        """
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message container - the correct MIME type is multipart/alternative.
        emsg = MIMEMultipart('alternative')
        emsg['Subject'] = self.subject
        emsg['From'] = self.sender
        emsg['To'] = ', '.join(self.to)

        # Create the body of the message (a plain-text and an HTML version).
        self.text = '\n'.join(texts) if isinstance(texts, list) else texts
        self.html = """
        <html>
          <head></head>
          <body>
            {}  
          </body>
        </html>
        """.format('\n'.join(htmls) if isinstance(htmls, list) else htmls)

        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(self.text, 'plain')
        part2 = MIMEText(self.html, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        emsg.attach(part1)
        emsg.attach(part2)

        # Send the message via the configured SMTP server from ANCLE global configuration.
        if not dryrun:
            s = smtplib.SMTP(server.settings.gateway)
            s.sendmail(self.sender, self.to, emsg.as_string())
            s.quit()

        self.sent = True
