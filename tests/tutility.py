"""Unit tests for the utility module in pyci."""
from pyci.utility import *
import unittest as ut

class TestUtilities(ut.TestCase):
    """Tests the utility module functions on hard-coded values.
    """
    def setUp(self):
        import xml.etree.ElementTree as ET
        self.xml = ET.Element("unittest")
        self.xml.set("exists", "true")
        self.xml.set("integer", "23")
        self.xml.set("float", "1.354")

    def test_get_attrib(self):
        """Tests utility.get_attrib including its ability to raise ValueError
        and cast the values as different types.
        """
        self.assertEqual("true", get_attrib(self.xml, "exists"))
        self.assertEqual(0, get_attrib(self.xml, "default", default=0))
        self.assertEqual(23, get_attrib(self.xml, "integer", cast=int))
        self.assertEqual(1.354, get_attrib(self.xml, "float", cast=float))
        self.assertRaises(ValueError, get_attrib, *(self.xml, "noexist", "unittest"))

    def test_repo_relpath(self):
        """Tests the utility function that returns a full path relative to a
        specified folder.
        """
        from os import path
        repodir = "~/codes/ci/tests"
        relpath = "../pyci/config.py"
        result = path.expanduser("~/codes/ci/pyci/config.py")
        self.assertEqual(result, get_repo_relpath(repodir, relpath))

    #def test_get_json(self): is simple enough; if the python library is unit
    #tested, we don't need to also test it.

    def test_run_exec(self):
        """Tests the running of a command in a subprocess, particularly within
        the context of the multiprocessing module.
        """
        from multiprocessing import Process, Queue
        output = Queue()
        repodir = "~/codes/ci/tests/repo"
        processes = []
        for i in range(3):
            processes.append(Process(target=run_exec, args=(repodir, "ls -la", output, i)))
            processes[-1].start()
            
        #Wait for the unit tests to all finish.
        for p in processes:
            p.join()
        results = [output.get() for p in processes]
        ordered = {o["index"]: o for o in results}

        #We consider the test successful if the output files were created and the end time
        #is not None. That means that the process ran correctly and python didn't lose
        #control of the subprocess.
        from os import path
        fullrepo = path.expanduser(repodir)
        for i in range(3):
            self.assertTrue(path.isfile(path.join(fullrepo, "{}.cidat".format(i))))
            self.assertIsNotNone(ordered[i]["end"])
            self.assertEqual(ordered[i]["code"], 0)
