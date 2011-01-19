"""
These fabric commands are designed to be useful across all of our KI projects.
They aim make the fabfile for a project as simple as

    from ki.shared.fabric import *

in the simplest case.  Per-project commands can of course be added to each
project's fabfile.


Deployment Targets
------------------

There are two deployment target modifiers, production and staging, which
adjust the deployments to which the other commands apply. Each takes an
optional version modifier, if it should target a non-default version.

For example, to run the shell command on the default production deployment:

    fab production shell

To run the shell command on a specific version of the staging deployment:

    fab staging:1-908ca6a shell

And to get a local shell, you just leave off the deployment target:

    fab shell
"""

from __future__ import with_statement

import datetime
import logging
import os
import sys
import code

from fabric.api import *

# Our own utils for use in this fabfile
import utils

# Where is the remote_api endpoint? The default is the path when the builtin
# config is used in app.yaml.
REMOTE_API_PATH = '/_ah/remote_api'


##############################################################################
# Deployment targets -- These can be used to specify which deployment the
# following commands should apply to.
##############################################################################

@utils.with_appcfg
def staging(version=None):
	"""Sets the deployment target to staging, with an optional non-default
	version."""
	env.gae.application = '%s-staging' % env.gae.application
	return utils.deployment_target(version=version)

@utils.with_appcfg
def production(version=None):
	"""Sets the deployment target to production, with an optional non-default
	version."""
	return utils.deployment_target(version=version)


##############################################################################
# Fabric commands
##############################################################################

@utils.target_required
def deploy(git=None, inplace=None):
	"""Clones the current project's git HEAD to a temporary directory,
updates its submodules, and deploys from the clone.

Optional arguments:

    :git -- Deploy the project with the current git revision appended to its
    version string (like the old --gitversion switch).

    :inplace -- Deploy the project from its working directory, instead of
    making a clean checkout.

Usage:

    # Deploy whatever version is in app.yaml to staging
    fab staging deploy

    # Deploy a version tagged with the current git revision to production
    fab production deploy:git

    # Deploy straight from the working directory
    fab staging deploy:inplace=1

	# Deploy from the working directory, tagged with git revision
	fab production deploy:git,inplace
	"""
	# Are we deploying a version tagged with the git revision? If so, update
	# the app's version string accordingly.
	if git:
		gitversion = local('git rev-parse --short HEAD').strip()
		env.gae.version = '%s-%s' % (env.gae.version, gitversion)

	# Are we making a clean checkout from which to deploy?
	if not inplace:
		# Where are we checking out a clean copy?
		clone_src = os.getcwd()
		deploy_src = local('mktemp -d -t %s' % env.gae.application).strip()

		# Make the clone, check out and update its submodules, and clean up
		# all the resulting git information (trying to make a clean copy of
		# the source).
		local('git clone %s %s' % (clone_src, deploy_src))
		with cd(deploy_src):
			# First we want to replace the remote KI submodule URL with our
			# local one. This makes cloning faster and makes it possible to
			# deploy from a clean clone whose KI submodule is ahead of the
			# remote KI submodule.
			remote_ki = 'git@keyingredient.unfuddle.com:keyingredient\/ki.git'
			local_ki = os.path.join(clone_src, 'ki').replace('/', '\/')
			sed_pattern = 's/%s/%s/g' % (remote_ki, local_ki)
			local("sed -i '' -e '%s' .gitmodules" % sed_pattern)

			# Now we can update the submodules and clean up any git info
			local('git submodule init && git submodule update', capture=False)
			local('find . -name ".git*" | xargs rm -rf')

	# Otherwise, we're just deploying from the current directory, as is, but
	# with the app ID and version controlled by the remote target.
	else:
		deploy_src = '.'

	# Deploy the application using appcfg.py
	cmd = 'appcfg.py -A %s -V %s update %s' % (
		env.gae.application, env.gae.version, deploy_src)
	local(cmd, capture=False)

	# Clean up after ourselves if we made a clone of the source code
	if not inplace:
		assert deploy_src not in ('.', env.cwd)
		local('rm -r %s' % deploy_src)


@utils.target_required
def livedeploy(inplace=None):
	"""Deploy the project twice: once tagged with the git version, once on
version 1.  This supports our policy of keeping the live sites on version 1
while still having a record of the most recent git version that is deployed.

Optional arguments:

    :inplace -- Deploy the project from its working directory, instead of
    making a clean checkout.
	"""
	deploy(git=True, inplace=inplace)
	# Reset the gae env to the "real" version as specified in app.yaml. This
	# will usually have the effect of deploying to version '1'
	env.gae.version = utils.parse_appcfg().version
	deploy(git=False, inplace=inplace)


def shell(cmd=None, path=REMOTE_API_PATH):
	"""Launches an interactive shell for this app. If preceded by a deployment
target (e.g. production or staging), a remote_api shell on the given target is
started. Otherwise, a local shell is started.  Uses enhanced ipython or
bpython shells, if available, falling back on the normal Python shell.

Optional arguments:

    :cmd -- A string of valid Python code to be executed on the shell. The
    shell will exit after the code is executed.

	:path -- The path to the remote_api handler on the deployment
	target. Defaults to '/remote_api'.

Usage:

    # A local shell
    fab shell

    # A remote_api shell on production
    fab production shell

    # Run a command directly on production
    fab production shell:cmd="memcache.flush_all()"
"""

	# Import the modules we want to make available by default
	from google.appengine.api import urlfetch
	from google.appengine.api import memcache
	from google.appengine.ext import deferred
	from google.appengine.ext import db

	# Build a dict usable as locals() from the modules we want to use
	modname = lambda m: m.__name__.rpartition('.')[-1]
	mods = [db, deferred, memcache, sys, urlfetch]
	mods = dict((modname(m), m) for m in mods)

	# The banner for either kind of shell
	banner = 'Python %s\n\nImported modules: %s\n' % (
		sys.version, ', '.join(sorted(mods)))

	# Are we running a remote shell?
	if hasattr(env, 'gae'):
		# Add more info to the banner
		loc = '%s%s' % (env.gae.host, path)
		banner = '\nApp Engine remote_api shell\n%s\n\n%s' % (loc, banner)
		# Actually prepare the remote shell
		utils.prep_remote_shell(path=path)

	# Otherwise, we're starting a local shell
	else:
		utils.prep_local_shell()

	# Define the kinds of shells we're going to try to run
	def ipython_shell():
		import IPython
		shell = IPython.Shell.IPShell(argv=[], user_ns=mods)
		shell.mainloop(banner=banner)

	def bpython_shell():
		from bpython import cli
		cli.main(args=[], banner=banner, locals_=mods)

	def plain_shell():
		sys.ps1 = '>>> '
		sys.ps2 = '... '
		code.interact(banner=banner, local=mods)

	# If we have a command to run, run it.
	if cmd:
		print 'Running remote command: %s' % cmd
		exec cmd in mods

	# Otherwise, start an interactive shell
	else:
		try:
			ipython_shell()
		except ImportError:
			try:
				bpython_shell()
			except ImportError:
				plain_shell()


def loaddata(path):
	"""Load the specified JSON fixtures.  If preceded by a deployment target,
the fixture data will be loaded onto that target.  Otherwise they will be
loaded into the local datastore.

Arguments:

    :path -- The path to the fixture data to load

Usage:

    # Load data locally
    fab loaddata:groups/fixtures/test_groups.json

    # Load data onto staging
    fab staging loaddata:groups/fixtures/test_groups.json
"""
	from ki.webapp.gaetest import fixtures

	# Are we loading the fixtures remotely or locally?
	if hasattr(env, 'gae'):
		utils.prep_remote_shell()
	else:
		utils.prep_local_shell()

	# Actually load the fixtures (tweak the logging so their info shows up)
	logging.getLogger().setLevel(logging.INFO)
	fixtures.load_fixtures(path)


def dumpdata(kind=None, batch=None, resume=None):
	"""Dump data from a remote deployment using the bulkloader.py tool.

Optional arguments:

    :kind -- Limit the dump to entities of this kind.

	:batch -- Dump the data in batches of this size.

	:resume -- The path to a "*-pgrogress-*.sql3" from which to resume.

Usage:

    # Dump all data from staging
    fab staging dumpdata

    # Dump all profiles from production
   	fab production dumpdata:Profile
	fab production dumpdata:kind=Profile

	# Dump all recipes in batches of 10
	fab staging dumpdata:Recipe,10
	fab stating dumpdata:kind=Recipe,batch=10

	# Dump everything in batches of 100
	fab staging dumpdata:batch=100

	# Resume a dump from a progress file
	fab staging dumpdata:Recipe,resume=bulkloader-progress-XXX.sql3
"""
	# Eample command:
	#
	# bulkloader.py --dump --application="key-usergen"
	# --url="http://key-usergen.appspot.com/remote_api"
	# --db_filename=bulkloader-progress-20100819.084903.sql3
	# --filename="recipes.sql" --kind="Recipe" --batch_size="25"

	if not hasattr(env, 'gae'):
		abort('dumpdata command requires a remote deployment.')

	url = 'https://%s%s' % (env.gae.host, REMOTE_API_PATH)
	basename = kind if kind is not None else 'all-kinds'
	datestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
	filename = '%s-%s.sql3' % (basename, datestamp)

	args = [
		'--dump',
		'--url="%s"' % url,
		'--application="%s"' % env.gae.application,
		'--filename="%s"' % filename,
		]

	if kind:
		args.append('--kind="%s"' % kind)
	if batch:
		args.append('--batch_size="%s"' % batch)
	if resume:
		if not os.path.exists(resume):
			abort('Resume file not found: %s' % resume)
		args.append('--db_filename="%s"' % resume)

	cmd = 'bulkloader.py %s' % ' '.join(args)
	local(cmd, capture=False)


@utils.target_required
def memcache(cmd='stats'):
	"""Operate on a remote deployment's memcache by getting its stats or
clearing its data.

Optional arguments:

    :cmd -- The action to take. Defaults to 'stats'. Must be one of 'stats' or
    'flush'.

Usage:

    # Get production memcache's stats
    fab production memcache:stats

    # Same thing (gets stats by defualt)
    fab production memcache

    # Clear staging memcache
    fab staging memcache:flush
"""
	# What kind of commands do we know how to run?
	cmds = {
		'stats': 'print memcache.get_stats()',
		'flush': 'memcache.flush_all()',
		}
	# Aliases
	cmds['clear'] = cmds['flush']

	# Make sure we know what to do with the command
	if not cmd in cmds:
		valid_cmds = ', '.join(cmds)
		abort('Invalid memcache command. Valid commands: %s' % valid_cmds)

	# Run the actual Python code via the shell command
	return shell(cmd=cmds[cmd])

def poextract(conf='babel.conf'):
	"""Extract all of the translatable strings from the templates
	and update the PO files that exist in locales.  You need pybabel in
	your path and babel and jinja2 installed into the python that pybabel
	uses.  A working method is to install babel and jinja2 with python 2.6
	and run GAE in 2.5.  The output POT file is ki.pot.

Optional arguments:

    :conf -- The configuration file to use, defaults to 'babel.conf'
	"""
	local('pybabel extract -F %s . > ki.pot' % conf, capture=False)
	poupdate()

def poinit(locale):
	"""Initialize message catalogs. You need pybabel in
	your path and babel and jinja2 installed into the python that pybabel
	uses.  A working method is to install babel and jinja2 with python 2.6
	and run GAE in 2.5.

Arguments:

    :locale -- Locale for the new localized catalog
	"""
	import os
	try:
		os.mkdir('locales')
	except: pass

	local('pybabel init -i ki.pot -d locales -l %s' % (locale))

def poupdate():
	"""Update all locales. Run after an extract.
	"""

	import os
	for folder in sorted(os.listdir('locales')):
		local('pybabel update -i ki.pot -d locales/ -l %s' % folder)

def pocompile():
	""" Compile all recipe catalogs. """
	local('pybabel compile --use-fuzzy --statistics -d locales/ ')

if __name__ == '__main__':
	shell()
