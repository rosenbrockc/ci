"""Unit testing for the pyci.config module and its containing classes.
"""
import unittest as ut
from pyci.config import *
from pyci.server import *

class TestServerConfigRead(ut.TestCase):
    """Tests the importing of the server settings (global) XML file."""
    def setUp(self):
        self.settings = GlobalSettings(True)
        self.settings._vardict["PYCI_XML"] = "~/codes/ci/tests/global.xml"
        self.settings._vardict["GATEWAY"] = "gateway.domain.com"
        self.settings._vardict["FROM"] = "no-reply@ci.domain.com"
        self.settings._vardict["CUSTBIN"] = "/usr/local/bin/mytester"
        self.settings._vardict["CUSTPATH"] = "/Users/dev/data/"
        self.settings._vardict["WIKI"] = "wiki.domain.com/wiki/core"
        self.settings._vardict["DATAFILE"] = "~/codes/ci/tests/data.json"
        self.settings._vardict["ARCHFILE"] = "~/codes/ci/tests/archive.json"
        self.settings._vardict["VENV"] = "ci"
        self.settings._initialized = True

    def _dict_compare(self, a, b):
        result = [""]
        for key in a:
            result.append("{}: {} || {}".format(key, a[key], b[key]))

        return '\n'.join(result)
        
    def test_xml_read(self):
        """Makes sure the XML loader produces the same values for the settings
        and server that were hard-coded under human-interpretation.
        """
        result = GlobalSettings()
        self.assertEqual(self.settings, result,
                         self._dict_compare(self.settings._vardict, result._vardict))

    def test_var_replace(self):
        """Tests that the GlobalSettings instance can successfully replace a test
        string's fields with the relevant values from its _vardict.
        """
        src = "@CUSTBIN @CUSTPATHscripts.py"
        res = "/usr/local/bin/mytester /Users/dev/data/scripts.py"
        self.assertEqual(res, self.settings.var_replace(src))

class TestCronSettings(ut.TestCase):
    """Tests the reading in of <cron> tags' settings.
    """
    def setUp(self):
        import xml.etree.ElementTree as ET
        self.xml = ET.Element("cron")
        self.xml.set("frequency", "15")
        self.xml.set("emails", "a@b.com, e@f.org")
        self.xml.set("notify", "start, failure, error")

        self.model = CronSettings()
        self.model.frequency = 15
        self.model.emails = ["a@b.com", "e@f.org"]
        self.model.notify = ["start", "failure", "error"]

    def test_xml_read(self):
        read = CronSettings(self.xml)
        self.assertEqual(read, self.model)
        
class TestRepoConfigRead(ut.TestCase):
    """Tests the importing of the repo settings XML file."""
    def setUp(self):
        self.target = RepositorySettings()
        """A hard-coded instance of RepositorySettings with the XML file's values
        set manually to what they should initialize to.
        """
        from os import path
        self.target.filepath = path.abspath(path.expanduser("~/codes/ci/tests/repo.xml"))
        self.target.name = "arbitrary"
        self.target.username = "agituser"
        self.target.apikey = "[key]"
        self.target.organization = "custom-org"
        self.target.staging = "~/codes/ci/tests/repo"

        self.target.testing = TestingSettings()
        self.target.testing.timeout = 120
        self.commands = ["first tests/a.py", "@CUSTBIN tests/scripts.py",
                         "cd @CUSTPATH; path tests/builders.py"]

        for c in self.commands:
            self.target.testing.tests.append(
                {"command": c, "end": None,
                 "success": False, "code": None,
                 "start": None, "result": None})

        self.target.static = StaticSettings()
        self.target.static.files.append(
            {"source": "~/codes/ci/tests/static/file.txt", "target": "./file.txt"})
        self.target.static.folders.append(
            {"source": "~/codes/ci/tests/static/folder", "target": "./folder"})

        self.target.wiki["user"] = "wikibot"
        self.target.wiki["password"] = "botpassword"
        self.target.wiki["basepage"] = "Base_Page"

    def test_init(self):
        """Tests the XML read-in of the repo.xml file.
        """
        coded = RepositorySettings(filepath="tests/repo.xml")
        self.assertEqual(self.target, coded)
        #"\n{}\n\n{}\n".format(coded.__dict__, self.target.__dict__))
        
    def test_static_copy(self):
        """Tests the copying of the static files and folders using rsync.
        """
        from os import path
        repodir = path.expanduser("~/codes/ci/tests/repo")
        self.target.static.copy(repodir)

        #We use rsync to determine if the directories are the same.
        from os import waitpid
        from subprocess import Popen, PIPE
        command = "cd ~/codes/ci/tests; rsync -avun static/ repo/"
        child = Popen(command, shell=True, executable="/bin/bash", stdout=PIPE)
        waitpid(child.pid, 0)
        output = child.stdout.readlines()
        self.assertEqual(len(output), 5, "OUT: {}".format(output))
        self.assertTrue("sent" in output[3])
        
    def test_testing_summaries(self):
        """Tests the HTML, text and wiki representation generation for the
        TestingSettings instance.
        """
        self.target.testing.tests = []
        get_test_results(self.target.testing.tests, self.commands)

        from os import path
        files = ["html", "text", "wiki"]
        for ftype in files:
            func = getattr(self.target.testing, ftype)
            with open(path.abspath("./tests/outputs/testing.{}".format(ftype))) as f:
                model = f.read()
            self.assertEqual(func().strip(), model.strip())

def get_test_results(tests, commands=None):
    """Appends a series of hard-coded test results to the specified
    list to be used in verifying the procedures with unit tests.
    """
    def get_result(i, c):
        from datetime import datetime
        return {"command": c, "end": datetime(2005, 7, 14, 12, 31),
                "success": i%3==0, "code": i%3,
                "start": datetime(2005, 7, 14, 12, 30),
                "result": "~/ci/staging/result.{}.dat".format(i),
                "remote_file": "result.{}.dat".format(i)}

    if commands is not None:
        for i, c in enumerate(commands):
            tests.append(get_result(i, c))
    else:
        ntests = []
        for i, test in enumerate(tests):
            ntests.append(get_result(i, test["command"]))
        return ntests
