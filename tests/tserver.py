"""Unit tests for the CI server module and classes."""
import unittest as ut
from pyci.server import *
from pyci.config import RepositorySettings

def get_testing_server(useconf=True, archpath=None):
    """Returns an instance of pyci.server.Server with hard-coded default
    values for the properties.
    """
    if useconf and archpath is None:
        #Since the config module is unit tested, we can rely on the config
        #files' values that are read in for those tests.
        return Server(testmode=True)
    elif archpath is not None:
        #This is a mixed mode; we still load the regular testing configuration,
        #but we override the location of the archive file so that the tests don't
        #change the contents of the model archive we usually compare to.
        return Server(archfile=archpath, testmode=True)
    else:
        #The tests are making sure that it fails gracefully with bogus
        #paths, just initialize an instance.
        return Server("~/nonexistent/path/data.json", "~/boguspath/archive.json", True)

class FakePull(object):
    """Class instance with a subset of the properties of 
    github.PullRequest.PullRequest so that we can test our formatting procedures
    with unit tests.
    """
    def __init__(self, number):
        from datetime import datetime
        self.number = number
        """The pull request number that shows up on github."""
        self.created_at = datetime(2005, 10, 14, 05, 23)
        """The date on which the pull request was created."""
        self.body = "Fake pull request body text."
        self.avatar_url = "http://some.url/avatar"
        self.html_url = "http://ci.github.com"
        self.snumber = str(number)

class FakeRepo(object):
    """Class instance with a subset of the properties of 
    github.Repository.Repository so that we can test our formatting procedures
    with unit tests.
    """
    def __init__(self, name):
        self.name = name
        """The short name of the github repo."""

class TestServerInit(ut.TestCase):
    """Tests the initialization of the Server class with various combinations
    of initializing values. Makes sure it handles bogus paths gracefully.
    """
    def test_standard(self):
        """Tests the standard load from XML; i.e. no parameters to initializer.
        """
        from os import path
        server = get_testing_server(archpath="~/codes/ci/tests/none.json")
        self.assertEqual([path.expanduser("~/codes/ci/tests/repo.xml")], server.installed)
        self.assertEqual(
            {},
            server.archive)
        self.assertEqual(
            {"arbitrary": RepositorySettings(server, path.expanduser("~/codes/ci/tests/repo.xml"))},
            server.repositories)

    def test_bogus(self):
        """Tests whether the initialization fails when no valid data is given.
        """
        server = get_testing_server(False)
        self.assertEqual([], server.installed)
        self.assertEqual({}, server.archive)
        self.assertEqual({}, server.repositories)

class TestServerProcess(ut.TestCase):
    """Tests the Server instance's ability to process PullRequests.
    """
    @classmethod
    def setUpClass(self):
        self.server = get_testing_server()
        #We need a pull request for each of the request statuses:
        #"new", "started, but incomplete", "failed", "old" We will choose
        #pull number for those types in increasing number order 1-4
        self.pulls = {i: FakePull(i) for i in range(4)}
        self.repodirs = ["~/codes/ci/tests/repo" for i in range(4)]
        #Now we hard-code the archive values we expect to be deserialized
        #and that specify the differences between the pull requests.
        from datetime import datetime
        #We don't have an entry in the archive for brand new pull requests.
        #All the pull requests have the same start time so that it is reproducible.
        self.archive = {"arbitrary":
                        {
                            #The one that started and is still running has a start time,
                            #but almost everything else has default value still.
                            1: {"success": False, "start": datetime(2015, 04, 23, 13, 05),
                                "number": 1, "stage": self.repodirs[1],
                                "completed": False, "finished": None},
                            #The one that failed has a start time and a completion date and
                            #the completion flag is set to True so that it won't be visited.
                            2: {"success": False, "start": datetime(2015, 04, 23, 13, 05),
                                "number": 2, "stage": self.repodirs[2],
                                "completed": True, "finished": datetime(2015, 04, 23, 13, 9)},
                            #The old class are those that finished without problems and just
                            #live in the history.
                            3: {"success": True, "start": datetime(2015, 04, 23, 13, 05),
                                "number": 3, "stage": self.repodirs[3],
                                "completed": True, "finished": datetime(2015, 04, 23, 15, 15)}}}

        self._create_archive()

    @classmethod
    def _create_archive(self):
        """Generates the initial archive file that sets the state of the server's previous
        pull request processing.
        """
        from os import path
        target = path.expanduser("~/codes/ci/tests/archive.json")
        if not path.isfile(target):
            import json
            from pyci.utility import json_serial
            with open(target, 'w') as f:
                json.dump(self.archive, f, default=json_serial)

    def test_find_pulls(self):
        """Tests whether the server differentiates between requests that are new,
        have started but not completed, and those that may have failed previously
        and handles each one correctly.
        """
        result = self.server.find_pulls(self.pulls.values())
        #The server should only find the pulls that still need something done to
        #them, those are "new", "started, but incomplete". The one that finished
        #successfully and the one that failed should be ignored.
        model = {
            "arbitrary": [PullRequest(self.server, self.server.repositories["arbitrary"],
                                      self.pulls[i], True) for i in range(2)]
        }
        self.maxDiff = None
        self.assertEqual(result, model)

    def test_install(self):
        """Tests whether the Server instance correctly initializes an XML repo
        settings file, save it to the archive and can also handle (i.e. ignore
        re-installations of the same file.
        """
        #First test a new XML installation. Give a different path than the
        #normal one to the server constructor.
        from os import path, remove
        instpath = path.expanduser("~/codes/ci/tests/new.install.json")
        archpath = path.expanduser("~/codes/ci/tests/new.archive.json")
        if path.isfile(instpath):
            remove(instpath)
        if path.isfile(archpath):
            remove(archpath)
        
        server = Server(instpath, archpath, True)
        server.install("~/codes/ci/tests/repo.xml")

        def assertions():
            self.assertEqual(server.archive, {"arbitrary": {}})
            self.assertEqual(server.repositories,
                             {"arbitrary": RepositorySettings(server, server.installed[0])})
            self.assertEqual(server.installed, [path.expanduser("~/codes/ci/tests/repo.xml")])

        assertions()
        #Now make sure that the values were also saved correctly in JSON.
        server.installed = server._get_installed()
        server.archive = server._get_archive()
        server.repositories = server._get_repos()
        assertions()

    #def test_get_fields(self):
    #Relies almost exclusively on the implementations of the field methods in the
    #class PullRequest. As such we skip it.

    def test_process_pulls(self):
        """Tests the interaction of Server with the list of PullRequest instances that
        it needs to process.
        """
        #We load the Server using a fixed archive each time. Then, before running
        #the processing, we *change* the filepath of the archive so that the updates
        #are saved to a different file.
        from os import path
        import datetime
        self.server.archpath = path.abspath(path.expanduser("~/codes/ci/tests/outputs/archive.json"))
        repodir = path.abspath(path.expanduser(self.server.repositories["arbitrary"].staging))
        expected = {}
        for i in range(4):
            expected[i] = get_expected_results(repodir, i)
        self.server.process_pulls(self.pulls, self.archive, expected)

        #The only variable whose value needs to be tested is the archive, which gets
        #updated with the status of the pull requests' evaluation.
        with open(path.expanduser("~/codes/ci/tests/outputs/process.out")) as f:
            model = eval(f.read())
        self.assertEqual(self.server.archive, model)        

def get_expected_results(repodir, process=None):
    """Returns a dict of the test results expected from running the commands
    for the unit tests (i.e. the tests run by the server).

    :arg process: when non-zero, return the results as 'new', 'started, but incomplete',
      'failed', 'old'.
    """
    from datetime import datetime
    from os import path
    if process is None:
        return {
            0: {"index": 0, "end": datetime(2015, 04, 23, 13, 05), "code": 0,
                "output": path.join(repodir, "{}.cidat".format(0))},
            1: {"index": 1, "end": datetime(2015, 04, 23, 14, 05), "code": 1,
                "output": path.join(repodir, "{}.cidat".format(1))},
            2: {"index": 2, "end": datetime(2015, 04, 23, 13, 55), "code": -1,
                "output": path.join(repodir, "{}.cidat".format(2))}
        }
    else:
        finished = {
            0: datetime(2015, 4, 23, 13, 9),
            1: datetime(2015, 4, 23, 13, 9),
            2: datetime(2015, 4, 23, 13, 9),
            3: datetime(2015, 4, 23, 15, 15)
        }
        result = {
            0: {"index": 0, "end": None, "code": 0,
                "output": path.join(repodir, "{}.cidat".format(0))},
            1: {"index": 1, "end": None, "code": 1,
                "output": path.join(repodir, "{}.cidat".format(1))},
            2: {"index": 2, "end": None, "code": 1,
                "output": path.join(repodir, "{}.cidat".format(2))},
            3: {"index": 2, "end": None, "code": 0,
                "output": path.join(repodir, "{}.cidat".format(2))}
        }
        #By default, all of them complete properly except for the one that
        #fails.
        for key in result:
            if process == 2:
                result[key]["code"] = (key%2)-1
            result[key]["end"] = finished[key]            

        return result

class TestPullRequest(ut.TestCase):
    """Tests the methods that initialize, test and analyze the unit testing for
    a single PullRequest instance.
    """
    @classmethod
    def setUpClass(self):
        from os import path
        self.server = get_testing_server()
        self.repo = RepositorySettings(filepath="tests/repo.xml")
        self.pull = PullRequest(self.server, self.repo, FakePull(11), True)
        self.pull.repodir = path.abspath(path.expanduser(self.repo.staging))
        self.expected = get_expected_results(self.pull.repodir)

    def test_init(self):
        """Tests the initialization of the git repo with a new branch for the
        pull request that is updated with the remote status.
        """
        from os import path
        #Since most of the operations in this function are live there isn't very
        #much that gets tested. First test is for a new pull request
        self.pull.init({})        
        self.assertEqual(self.pull.repodir, path.expanduser("~/codes/ci/tests/repo"))
        self.assertTrue(path.isdir(self.pull.repodir))

    def test_is_gitted(self):
        """Tests the function that determines if a repo has been initialized
        by git for the pull request CI automation.
        """
        from os import path
        self.pull.repodir = path.expanduser("~/codes/ci/tests/repo")
        self.assertTrue(self.pull._is_gitted())
        #Now make sure it returns false for a non-git repo.
        self.pull.repodir = path.expanduser("~/codes")
        self.assertFalse(self.pull._is_gitted())
        #Finally, check that it works for a git repo that is not made by the
        #CI server.
        self.pull.repodir = path.expanduser("~/codes/ci")
        self.assertFalse(self.pull._is_gitted())

    #def test_begin(self):
    #begin gets skipped because it only does two things: call the wiki create function
    #which is already unit tested, and then make a live status update to github.

    #def test_fail(self):
    #The method fail only performs a live request to the server to update the commit
    #status to failure.

    def test_test(self):
        """Tests the execution structure of the unit tests. Since the multiprocessing
        is unit tested by another testing module, this test is just for the backbone
        structure surrounding those executions.
        """
        self.pull.test(self.expected)

        #Running the tests updates the values of the dictionary entries for
        #each test in the repository settings object. We test those values
        #now to make sure that they match. Most of the values are copied
        #verbatim from the expected dictionary above, so we just check the
        #ones that ought to change.
        for i in range(3):
            self.assertEqual(self.repo.testing.tests[i]["success"], i%3 < 2)
        self.assertEqual(self.repo.testing.tests[1]["command"],
                         "/usr/local/bin/mytester tests/scripts.py")
        self.assertEqual(self.repo.testing.tests[2]["command"],
                         "cd /Users/dev/data/; path tests/builders.py")

    def test_finalize(self):
        """Tests the analysis of the testing results and the compilation of
        success percentages and total run times.
        """
        #We need to call the pull.test() function again to get the results
        #copied across correctly for analysis.
        self.pull.test(self.expected)
        self.pull.finalize()
        self.assertTrue(self.pull.percent - 2./3 < 1e-12)
        self.assertEqual(self.pull.message, "Results: 66.67% in 6780s.", self.pull.message)

    def test_fields(self):
        """Tests the creation of the fields dictionaries for the various events
        that are generated by the Server instance.
        """
        #We only have to test the 'start' and 'finish' events since the other
        #cases overlap with their dictionaries.
        start = self.pull.fields_general("start")
        self.pull.test(self.expected)
        self.pull.finalize()
        finish = self.pull.fields_general("finish")

        from os import path
        with open(path.expanduser("~/codes/ci/tests/outputs/start.fields")) as f:
            model = eval(f.read())
            self.assertEqual(model, start)
        with open(path.expanduser("~/codes/ci/tests/outputs/finish.fields")) as f:
            model = eval(f.read())
            self.assertEqual(model, finish)

class TestCronManager(ut.TestCase):
    """Tests the cron installation and emailing functionality of the CI server.
    """
    def setUp(self):
        self.server = get_testing_server()
        self.cron = CronManager(self.server)
        self.repo = RepositorySettings(self.server, filepath="tests/repo.xml")
        self.cron.settings = self.server.cron.settings
        
        from tconfig import get_test_results
        self.repo.testing.tests = get_test_results(self.repo.testing.tests)
        from os import path
        self.fields = {
            "__reponame__": "ciuser/arbitrary",
            "__repodesc__": "Unit testing description of arbitrary.",
            "__repourl__": "http://github.com/ciuser/arbitrary",
            "__repodir__": path.expanduser("~/codes/ci/tests/repo"),
            "__username__": "ciuser",
            "__userurl__": "http://usercontent.github.com/ciuser",
            "__useravatar__": "http://images.github.com/images/ciuser",
            "__useremail__": "ciuser@gmail.com",
            "__test_html": self.repo.testing.html(True),
            "__test_text": self.repo.testing.text(True)
        }

    def test_email(self):
        """This high-level function tests the templating functionality of the
        CronManager and the email instantiation of the email class. This method
        is treated as the unit test for the Email class (which has a single
        method only).
        """
        from os import path
        templates = ["start", "success", "failure", "timeout", "error"]
        
        for e in templates:
            email = self.cron.email(self.repo.name, e, self.fields, True)
            self.assertTrue(email.sent)
            self.assertEqual(email.to, ["a@gmail.com", "b@gmail.com"])
            self.assertEqual(email.sender, "no-reply@ci.domain.com")

            self.assertTrue(path.isfile(path.expanduser("~/codes/ci/tests/outputs/{}.txt".format(e))))
            self.assertTrue(path.isfile(path.expanduser("~/codes/ci/tests/outputs/{}.html".format(e))))

            with open(path.expanduser("~/codes/ci/tests/outputs/{}.txt".format(e))) as f:
                self.assertEqual(f.read().strip(), email.text.strip(), email.text)
            with open(path.expanduser("~/codes/ci/tests/outputs/{}.html".format(e))) as f:
                self.assertEqual(f.read().strip(), email.html.strip(), "\n{}\n\n".format(email.html))

class TestWiki(ut.TestCase):
    """Tests the creation and updating of wiki pages."""
    @classmethod
    def setUpClass(self):
        self.server = get_testing_server()
        self.pull = PullRequest(self.server, self.server.repositories["arbitrary"],
                                FakePull(11), True)
        self.repo = FakeRepo("diaconis")

        
    def test_get_site(self):
        """Makes sure that the site url is parsed correctly so that the mwclient
        doesn't choke on the settings.
        """
        url="wiki.domain.com"
        relpath="/wiki/core/"
        self.assertEqual(self.server.wiki.url, url)
        self.assertEqual(self.server.wiki.relpath, relpath)

    def _wiki_test(self, modelpath, function, *args):
        """Tests the text output of a wiki generating function against the model
        output specified in 'modelpath'.
        """
        from os import path
        with open(path.expanduser(modelpath)) as f:
            model = f.read().strip()

        return model, function(*args).strip()
        
    def test_create_new(self):
        """Tests the *text contents* that are auto-generated by the Wiki when
        the unit test details page is created.
        """
        model, code = self._wiki_test("~/codes/ci/tests/outputs/create_new.wiki",
                                      self.server.wiki._create_new, self.pull)
        self.assertEqual(model, code)

    def test_edit_main(self):
        """Tests the *text contents* that are auto-generated by the Wiki when
        the unit test details page is created.
        """
        model, code = self._wiki_test("~/codes/ci/tests/outputs/edit_main.wiki",
                                      self.server.wiki._edit_main, self.pull)
        self.assertEqual(model, code)
        self.assertEqual("arbitrary_Pull_Request_11", self.server.wiki.prefix)

    def test_update(self):
        """Tests the updating of the wiki page text for the unit test details.
        """
        model, code = self._wiki_test("~/codes/ci/tests/outputs/update.wiki",
                                      self.server.wiki.update, self.pull)
        self.assertEqual(model, code)
