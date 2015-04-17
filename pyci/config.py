"""Extracts the continuous integration server's configuration information from
the JSON library file. Provides a class for interacting with a specific repo's 
XML configuration.
"""
from utility import get_attrib, get_repo_relpath
from msg import vms

class RepositorySettings(object):
    """Represents a single github repository that should be unit tested when
    new pull requests are made as part of the continuous integration.
    """
    def __init__(self, server=None, filepath=None):
        """Parses the repository settings at the specified file path."""
        from os import path
        self.server = server
        """An instance of Server to act as parent of this repository."""
        self.filepath = (path.abspath(path.expanduser(filepath))
                         if filepath is not None else filepath)
        """The full path to the XML file settings for this repo."""
        self.name = None
        """The name of the github repository to monitor and integrate. Should exist
        with the list of repos that self.user has access to."""
        self.username = None
        """The name of the user account that has read/write access on the repo
        and that will be used to clone, test and update status on the pull requests.
        """
        self.apikey = None
        """The API key of the user account on github."""
        self.organization = None
        """The login name of the organization that owns the repo.
        """
        self.testing = None
        """Settings for performing the unit tests on the merged repos."""
        self.static = None
        """Settings for specifying locally available files and folders that should
        be copied locally before updating them from the repo. These should be files
        and folders that probably never change (like the unit testing input/output).
        """        
        self.wiki = {"user": None, "password": None, "basepage": None}
        """Settings for logging into and editing the base wiki page for the repo.
        """
        
        self._repo = None
        """Lazy initialization for the self.repo property."""
        self._user = None
        """Lazy initialization for the self.user property."""
        self._org = None
        """Lazy initialization for the self.org property."""

        if self.filepath is not None:
            self._parse_xml()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
    
    @property
    def org(self):
        """Instance of the github.Organization.Organization specified as owning the
        repository being monitored.
        """
        if self._org is None:
            self._get_github()

        return self._org
        
    @property
    def user(self):
        """Instance of the github.NamedUser.NamedUser corresponding to the username
        and API key settings.
        """
        if self._user is None:
            self._get_github()

        return self._user

    @property
    def repo(self):
        """Instance of the github.Repository.Repository class that these settings
        represent, obtained by querying the remote server using the API.
        """
        if self._repo is None:
            self._get_github()
            
        return self._repo

    def _get_github(self):
        """Creates an instance of github.Github to interact with the repos via the 
        API interface in pygithub.
        """
        from pygithub import Github
        vms("Querying github with user '{}'.".format(self.user))
        g = Github(self.user, self.apikey)
        self._user = g.get_user()
        #The github user authenticating always has to be specified; however the user
        #may not be able to see the repo, even if it has access to it. We may need
        #to check the organization repos.
        if self.organization is not None:
            self._org = g.get_organization(self.organization)
            vms("Found github organization '{}'.".format(self._org.name), 2)

            #Next we need to find this repository in the lists available to both
            #the user *and* the organization. If they specified an organization, then we
            #should check that first/exclusively.
            for repo in self._org.get_repos():
                if repo.full_name.lower() == self.name.lower():
                    self._repo = repo
                    vms("Found organization repository '{}'.".format(self._repo.full_name), 2)
                    break
        else:
            for repo in self._user.get_repos():
                if repo.full_name.lower() == self.name.lower():
                    self._repo = repo
                    vms("Found user repository '{}'.".format(self._repo.full_name), 2)
                    break        
                
    def _parse_repo(self, xml):
        """Parses a <repo> tag to update settings on this Repository instance.
        
        :arg xml: the <repo> tag XMLElement.
        """
        self.name = get_attrib(xml, "name", "repo")
        self.username = get_attrib(xml, "user", "repo")
        self.apikey = get_attrib(xml, "apikey", "repo")
        self.organization = get_attrib(xml, "organization")
        self.staging = get_attrib(xml, "staging", "repo")
        
    def _parse_xml(self):
        """Extracts the XML settings into class instances that can operate on
        the settings to perform the testing functions.
        """
        import xml.etree.ElementTree as ET
        from os import path
        #This dict has the keys of XML tags that are required in order for the
        #CI server to run the repo. When each one is parsed, we change its value
        #to True and then check that they are all true at the end.
        required = {"testing": False, "wiki": False}
        #Make sure the file exists and then import it as XML and read the values out.
        if path.isfile(self.filepath):
            tree = ET.parse(self.filepath)
            vms("Parsing XML tree from {}.".format(self.filepath), 2)
            root = tree.getroot()
            if root.tag != "cirepo":
                raise ValueError("The root tag in a continuous integration settings XML "
                                 "file should be a <cirepo> tag.")

            self._parse_repo(root)
            for child in root:
                if child.tag == "cron":
                    if self.server is not None:
                        self.server.cron.settings[self.name] = CronSettings(child)
                if child.tag == "testing":
                    self.testing = TestingSettings(child)
                if child.tag == "static":
                    self.static = StaticSettings(child)
                if child.tag == "wiki":
                    self.wiki["user"] = get_attrib(child, "user", "wiki")
                    self.wiki["password"] = get_attrib(child, "password", "wiki")
                    self.wiki["basepage"] = get_attrib(child, "basepage", "wiki")
                if child.tag in required:
                    required[child.tag] = True

            if not all(required.values()):
                tags = ', '.join(["<{}>".format(t) for t in required])
                raise ValueError("{} are required tags in the repo's XML settings file.".format(tags))

class CronSettings(object):
    """Represents the cron request settings for a single repository."""
    def __init__(self, xml=None):
        """
        :arg xml: the XMLElement instance of the <cron> tag that holds the
          request settings for the repo.
        """
        self.frequency = None
        """Specifies the frequency (in minutes) at which to test for new pull
        requests on the repo."""
        self.emails = None
        """A list of email addresses to notify when the cron performs any of
        the automated tasks.
        """
        self.notify = None
        """A list of events to notify the email addresses of during the
        automation. Possible values: ['start', 'error', 'success', 'timeout', 'failure'].
        """

        if xml is not None:
            self._parse_xml(xml)
        else:
            self.frequency = 5
            self.emails = []
            self.notify = []
            
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

    def _parse_xml(self, xml):
        """Extracts the attributes from the XMLElement instance."""
        from re import split
        vms("Parsing <cron> XML child tag.", 2)
        self.frequency = get_attrib(xml, "frequency", default=5, cast=int)
        self.emails = split(",\s*", get_attrib(xml, "emails", default=""))
        self.notify = split(",\s*", get_attrib(xml, "notify", default=""))
            
class StaticSettings(object):
    """Settings describing files *local* to the server that should be copied into
    the repositories locally before trying to syncronize with the remote, merged
    pull request. For unit tests requiring large amounts of data, this greatly
    reduces the bandwidth usage and run time of the continuous integration testing.
    """
    def __init__(self, xml=None):
        self.files = []
        """A list of locally available files to copy before syncing with the remote
        pull request.
        """
        self.folders = []
        """A list of locally available folders to copy before syncing with the remote
        pull request.
        """

        if xml is not None:
            self._parse_xml(xml)
            
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return str(self.__dict__)
    
    def _parse_xml(self, xml):
        """Extracts objects representing and interacting with the settings in the
        xml tag.
        """
        vms("Parsing <static> XML child tag.", 2)
        for child in xml:
            if "path" in child.attrib and "target" in child.attrib:
                if child.tag == "file":
                    self.files.append({"source": child.attrib["path"],
                                       "target": child.attrib["target"]})
                elif child.tag == "folder":
                    self.folders.append({"source": child.attrib["path"],
                                         "target": child.attrib["target"]})

    def copy(self, repodir):
        """Copies the static files and folders specified in these settings into the
        locally-cloned repository directory.

        :arg repodir: the full path to the directory with the locally-cloned version
          of the pull request being unit tested.
        """
        #Instead of using the built-in shell copy, we make shell calls to rsync.
        #This allows us to copy only changes across between runs of pull-requests.
        from os import system, path
        vms("Running static file copy locally.", 2)
        for file in self.files:
            fullpath = path.expanduser(file["source"])
            if path.isfile(fullpath):
                vms("Running 'rsync' for {}.".format(fullpath), 3)
                system("rsync -t -u {} {}".format(fullpath, get_repo_relpath(repodir, file["target"])))

        for folder in self.folders:
            fullpath = path.expanduser(folder["source"])
            if path.isdir(fullpath):
                vms("Running 'rsync' for {}.".format(fullpath), 3)
                system("rsync -t -u -r {} {}".format(path.join(fullpath, ""),
                                                     path.join(get_repo_relpath(repodir, folder["target"]), "")))
                    
class TestingSettings(object):
    """Settings describing the series of unit tests to perform on the repository
    as extracted from the repo's XML settings file.
    """
    def __init__(self, xml=None):
        """
        :arg xml: the <testing> XMLElement to extract attributes and children from.
        """
        self.timeout = None
        """The maximum number of minutes that *all* tests are allowed to take to run.
        If None, the allowed time is infinite.
        """
        self.tests = []
        """A list of the unit tests to run on the merged pull request repository.
        """

        if xml is not None:
            self._parse_xml(xml)
            
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return str(self.__dict__)
    
    def _parse_xml(self, xml):
        """Extracts objects representing and interacting with the settings in the
        xml tag.
        """
        vms("Parsing <testing> XML child tag.", 2)
        self.timeout = get_attrib(xml, "timeout", cast=int)
        for child in xml:
            if child.tag == "command":
                self.tests.append({"command": child.text, "end": None,
                                   "success": False, "code": None,
                                   "start": None, "result": None})

    def format_time(self, time, function, yes, no):
        """Formats the specified time using function. If time is not None,
        the value 'yes' is used, otherwise 'no'.
        """
        if time is not None:
            return function(time.strftime(yes))
        else:
            return function(no)
                
    def html(self, full=True):
        """Returns an HTML table of the test results."""
        import dominate
        from dominate.tags import table, tbody, tr, th, td
        result = table()
        with result.add(tbody()):
            header = tr()
            header += th("Command")
            if full:
                header += th("Start")
                header += th("End")
                header += th("Code")
            
            for test in self.tests:
                l = tr()
                l += td(test["command"])
                if full:
                    l += self.format_time(test["start"], td, "%m/%d/%Y %H:%M", "None")
                    l += self.format_time(test["end"], td, "%m/%d/%Y %H:%M", "None")
                    l += td(str(test["code"]))

        sresult = str(result)
        vms("HTML test table generated: {}.".format(sresult), 3)
        return sresult
                    
    def text(self, full=True):
        """Returns a text representation of the test results."""
        #Because we don't know the length of the commands in advance and we don't get to
        #use HTML, we make nested lists of items for each command.
        result = []
        for test in self.tests:
            result.append("Command: {}".format(test["command"]))
            if full:
                result.append(" - Start: {}".format(
                    self.format_time(test["start"], str, "%m/%d/%Y %H:%M", "None")))
                result.append(" - End:   {}".format(
                    self.format_time(test["end"], str, "%m/%d/%Y %H:%M", "None")))
                result.append(" - Code:  {}\n".format(test["code"]))

        sresult = '\n'.join(result)
        vms("Text test table generated: {}.".format(sresult), 3)        
        return sresult

    def wiki(self, full=True):
        """Returns the markup for writing the testing details to a media wiki.
        """
        result = []
        for test in self.tests:
            result.append("# {}".format(test["command"]))
            if full:
                result.append("* Start:  {}".format(
                    self.format_time(test["start"], str, "%m/%d/%Y %H:%M", "None")))
                result.append("* End:    {}".format(
                    self.format_time(test["end"], str, "%m/%d/%Y %H:%M", "None")))
                result.append("* Code:   {}".format(test["code"]))
                result.append("* Stdout: [[File:{}]]\n".format(test["remote_file"]))

        sresult = '\n'.join(result)
        vms("Wiki test table generated: {}.".format(sresult), 3)
        return sresult
    
class GlobalSettings(object):
    def __init__(self, noload=False):
        """A configuration class to store global variables under a configuration
        module name. Exposes values as properties to allow arbitrary variable
        storage via XML as well as static oft-used variables.

        :arg noload: when True, the constructor does *not* attempt to load the
          global settings from the file specified in 'PYCI_XML' environment var.
        """
        self._vardict = {}
        self._initialized = False

        if noload:
            return
        self.getenvar("PYCI_XML")

        if self.implicit_XML is not None:
            #print "Loading CI server config variables from " + self.implicit_XML
            self.load_xml(self.implicit_XML)
            self._initialized = True

    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return str(self._vardict)
    
    @property
    def implicit_XML(self):
        """Returns the full path to an XML file that contains path information for 
        the CI server."""
        return self.property_get("PYCI_XML")

    @property
    def gateway(self):
        """Returns the SMTP gateway for sending email reports."""
        return self.property_get("GATEWAY")

    @property
    def from_address(self):
        """Returns the email address to send notifications from."""
        return self.property_get("FROM")

    @property
    def wiki(self):
        """Returns the configured address and root of the media wiki."""
        return self.property_get("WIKI")        

    @property
    def venv(self):
        """Returns the name of the virtualenv to use for the CI server."""
        return self.property_get("VENV")

    @property
    def serial(self):
        """Returns true if the CI server should run in serial mode.
        """
        serial = self.property_get("SERIAL", False)
        if isinstance(serial, str):
            return serial.lower() == "true"
        else:
            return serial
        
    @property
    def datafile(self):
        """Returns the full path to the data file listing installed repos."""
        return self.property_get("DATAFILE")

    @property
    def archfile(self):
        """Returns the full path to the arch file listing installed repos."""
        return self.property_get("ARCHFILE")
    
    def property_get(self, key, default=None):
        if key in self._vardict:
            return self._vardict[key]
        else:
            return default

    def var_replace(self, text):
        """Replaces all instances of @VAR with their values in the specified text.
        """
        result = text
        for var in self._vardict:
            result = result.replace("@{}".format(var), self._vardict[var])
        return result
        
    def getenvar(self, envar):
        """Retrieves the value of an environment variable if it exists."""
        from os import getenv
        if getenv(envar) is not None:
            self._vardict[envar] = getenv(envar)

    def load_xml(self, filepath):
        """Loads the values of the configuration variables from an XML path."""
        from os import path
        import xml.etree.ElementTree as ET
        #Make sure the file exists and then import it as XML and read the values out.
        uxpath = path.expanduser(filepath)
        if path.isfile(uxpath):
            tree = ET.parse(uxpath)
            vms("Parsing global settings from {}.".format(uxpath))
            root = tree.getroot()

            for child in root:
                if child.tag == "var":
                    self._vardict[child.attrib["name"]] = child.attrib["value"]
      
