import code
import functools
import getpass
import os
import sys

from google.appengine.api import appinfo
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.tools import dev_appserver, dev_appserver_main

from fabric.api import env, abort


# Assumes we're located at PROJECT_ROOT/ki/shared/fabric/utils.py
PROJECT_ROOT = os.path.realpath(
	os.path.join(os.path.dirname(__file__), '../../'))

def with_appcfg(func):
	"""Decorator that ensures that the current Fabric env has GAE info
	attached to it at `env.gae`.  Available attributes:

	 - env.gae.application:  The app's application id (e.g., key-auth)
	 - env.gae.version: The app's version
	"""
	@functools.wraps(func)
	def decorated_func(*args, **kwargs):
		if not hasattr(env, 'gae') or not env.gae:
			# We have to attach a dummy object to the environment, because we
			# need to attach more info to it than is supported by the AppInfo
			# object (e.g., a host attribute).
			appcfg = parse_appcfg()
			env.gae = type('GaeInfo', (), {})
			env.gae.application = appcfg.application
			env.gae.version = appcfg.version
		return func(*args, **kwargs)
	return decorated_func

@with_appcfg
def deployment_target(version=None):
	"""A base modifier for specifying the deployment target.  Knows how to
	adjust the app's version and the gae_host string if a particular version
	is requested."""
	if version:
		env.gae.version = version
		env.gae.host = '%s.latest.%s.appspot.com' % (
			env.gae.version, env.gae.application)
	else:
		env.gae.host = '%s.appspot.com' % env.gae.application

def target_required(func):
	"""Ensures that a deployment target is specified before the given task."""
	@functools.wraps(func)
	def decorated_func(*args, **kwargs):
		if not hasattr(env, 'gae') or not env.gae:
			abort('A deployment target must be specified.')
		return func(*args, **kwargs)
	return decorated_func

@with_appcfg
def prep_local_shell():
	"""Prepares a local shell by adjusting the datastore paths according to
	the settings and setting up the appropriate stubs."""
	import settings
	args = dev_appserver_main.DEFAULT_ARGS.copy()
	# If a custom datastore directory is requested, modify the args for each
	# of the datastore paths
	if hasattr(settings, 'DATASTORE_DIR'):
		ddir = settings.DATASTORE_DIR
		for key in ('datastore_path', 'history_path', 'blobstore_path'):
			args[key] = os.path.join(ddir, os.path.basename(args[key]))
	# Finally, set up the stubs
	dev_appserver.SetupStubs(env.gae.application, **args)

@with_appcfg
def prep_remote_shell(path='/remote_api'):
	"""Prepares a remote shell using remote_api located at the given path on
	the given host, if given.  By default, will use the default version of the
	current App Engine application."""
	auth_func = lambda: (raw_input('Email: '), getpass.getpass('Password: '))
	remote_api_stub.ConfigureRemoteApi(
		env.gae.application, path, auth_func, servername=env.gae.host)
	remote_api_stub.MaybeInvokeAuthentication()
	os.environ['SERVER_SOFTWARE'] = 'Development (remote_api_shell)/1.0'

def parse_appcfg():
	"""Parses the current project's app.yaml config into an AppInfo object."""
	yamlpath = os.path.join(PROJECT_ROOT, 'app.yaml')
	return appinfo.LoadSingleAppInfo(open(yamlpath))
