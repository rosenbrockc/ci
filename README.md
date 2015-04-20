# Py-CI

Generic continuous integration server for interfacing with github and publishing results to a Media Wiki. The basic idea is that continuous integration just requires three things:

- A repo to monitor for changes.
- Unit tests to run.
- A place to publish the results of the tests.

`Py-CI` interfaces with github using the [pygithub](https://github.com/PyGithub/PyGithub) API wrapper for interfacing with github's API. It monitors the pull requests for a set of repos. When a new or untested pull request is found:

- Create a local copy of the repo; merge the proposed changes from the pull request into a working branch.
- Run all the unit tests specified in the `repo.xml` configuration file.
- Post the results of running the unit tets to a media wiki.

## Quickstart

If you already have a [virtualenv](https://virtualenv.pypa.io/en/latest/) installed as well as [virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/), skip this next code block. However, be sure to add the `VENV` variable to the [global configuration file](https://github.com/rosenbrockc/ci/wiki).

```
pip install virtualenv
pip install virtualenvwrapper
mkvirtualenv ci
```

Next, copy the [`global.xml`](https://github.com/rosenbrockc/ci/wiki) file and put it somewhere on you local disk (say `~/.ci.global.xml`). Be sure to **edit the values**. Then:

```
export PYCI_XML="~/.ci.global.xml"
workon ci
pip install py-ci
sudo ci.py -setup
```

If you don't see any errors, your server is ready to have repositories installed. This configures the server cron to run _every minute_. Use `-cronfreq [int minutes]` to change that frequency (see [cron settings](https://github.com/rosenbrockc/ci/wiki/Cron-Implementation) for details). You don't need to use `sudo` for anything _except_ setting the server up initially (or uninstalling it later with the `-rollback` switch). Next, create a [`repo.xml`](https://github.com/rosenbrockc/ci/wiki/Repository-Level-Settings) file for repository you want to monitor. Suppose it exists at `~/repos/myrepo/ci.xml`, then:

```
ci.py -install ~/repos/myrepo/ci.xml
```

Your repository will now be monitored for new pull requests forever untill you either `-uninstall` the `repo.xml` file _or_ you `-disable` the CI server to temporarily suspend all requests. To understand the behavior of the CI server, read through the [repository level settings](https://github.com/rosenbrockc/ci/wiki/Repository-Level-Settings) page.

**IMPORTANT:** if your unit tests require environment variables to be set, they need to be added to a file called `~/.cron_profile` that will be loaded by the CI server whenever the cron is run. See [cron environment variables](https://github.com/rosenbrockc/ci/wiki/Environment-Variables-for-Unit-Tests) for more details.