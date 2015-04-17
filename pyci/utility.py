"""Some helper functions used by multiple modules."""
from pyci.msg import err
def get_attrib(xml, name, tag=None, cast=str, default=None):
    """Returns the specified attribute from the XML element, raising a ValueError
    if it is not availaible.
    
    :arg xml: the XMLElement instance to get the attribute from.
    :arg name: the name of the attribute in xml.attrib dictionary.
    :arg tag: the name of the tag to display with the ValueError if the attribute is missing.
    """
    if name in xml.attrib:
        return cast(xml.attrib[name])
    elif default is not None:
        return default
    elif tag is not None:
        raise ValueError("'{}' is a required attribute of <{}> tag.".format(name, tag))

def get_repo_relpath(repo, relpath):
    """Returns the absolute path to the 'relpath' taken relative to the base
    directory of the repository.
    """
    from os import path
    if relpath[0:2] == "./":
        return path.join(repo, relpath[2::])
    else:
        from os import chdir, getcwd
        cd = getcwd()
        chdir(path.expanduser(repo))
        result = path.abspath(relpath)
        chdir(cd)
        return result

import dateutil.parser    
def load_with_datetime(pairs):
    """Deserialize JSON into python datetime objects."""
    d = {}
    for k, v in pairs:
        if isinstance(v, basestring):
            try:
                d[k] = dateutil.parser.parse(v)
            except ValueError:
                d[k] = v
        else:
            d[k] = v             
    return d

def get_json(jsonpath, default):
    """Returns the JSON serialized object at the specified path, or the default
    if it doesn't exist or can't be deserialized.
    """
    from os import path
    import json
    result = default
    
    if path.isfile(jsonpath):
        try:
            with open(jsonpath) as f:
                result = json.load(f, object_pairs_hook=load_with_datetime)
        except(IOError):
            err("Unable to deserialize JSON at {}".format(jsonpath))
            pass

    return result

from datetime import datetime
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial

def run_exec(repodir, command, output, index):
    """Runs the specified command in the repo directory.

    :arg repodir: the absolute path of the repo directory to run 'command' in.
    :arg command: what to run in the 'repodir'. Should be valid in the context
      of the $PATH variable.
    :arg output: the multiprocessing queue to push the results to.
    :arg index: the index of this test in the master list.
    """
    from os import path
    from subprocess import Popen, PIPE
    from datetime import datetime
    
    child = Popen("cd {}; {} > {}.cidat".format(repodir, command, index),
                  shell=True, executable="/bin/bash")
    # Need to do this so that we are sure the process is done before moving on
    child.wait()
    output.put({"index": index, "end": datetime.now(), "code": child.returncode,
                "output": path.join(repodir, "{}.cidat".format(index))})
