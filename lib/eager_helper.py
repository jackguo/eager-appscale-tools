import json
import os
import yaml
from appengine_helper import AppEngineHelper
from appscale_logger import AppScaleLogger
from eager_client import EagerClient
from local_state import LocalState

class EagerException(Exception):
  pass

class Application:
  def __init__(self, name, version, owner):
    self.name = name
    self.version = version
    self.owner = owner
    self.dependencies = []
    self.api_list = []

class API:
  def __init__(self, api_spec_path):
    api_spec_file = open(api_spec_path, 'r')
    api_spec = json.load(api_spec_file)
    api_spec_file.close()
    swagger_version = api_spec.get('swaggerVersion')
    if swagger_version != '1.2':
      raise EagerException('Invalid swagger version: {0} in {1}'.format(swagger_version, api_spec_path))
    self.name = api_spec['apiName']
    self.version = api_spec['apiVersion']
    self.specification = api_spec

  def to_dict(self):
    result = {
      'name' : self.name,
      'version' : self.version,
      'specification' : self.specification
    }
    return result

class EagerHelper:

  @classmethod
  def perform_eager_validation(cls, app, keyname):
    eager = EagerClient(LocalState.get_login_host(keyname),
      LocalState.get_secret_key(keyname))
    AppScaleLogger.log('Running EAGER validations for application.')
    errors = eager.validate_application_for_deployment(app)
    if errors:
      AppScaleLogger.log('Validation errors encountered:')
      for e in errors:
        AppScaleLogger.log('  * {0}'.format(e))
    return not errors

  @classmethod
  def get_application_info(cls, owner, app_language, app_dir):
    name = AppEngineHelper.get_app_id_from_app_config(app_dir)
    version = AppEngineHelper.get_app_version_from_app_config(app_dir)
    app = Application(name, version, owner)

    dependencies_path = app_dir + os.sep + 'dependencies.yaml'
    if app_language == 'java':
      dependencies_path = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'dependencies.yaml'
      api_specs_dir = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'specs'
      if os.path.exists(api_specs_dir):
        for f in os.listdir(api_specs_dir):
          if f.endswith('.json'):
            api = API(api_specs_dir + os.sep + f)
            AppScaleLogger.log('Detected API: {0}-v{1}'.format(api.name, api.version))
            app.api_list.append(api)

    if os.path.exists(dependencies_path):
      dependencies_file = open(dependencies_path, 'r')
      dependencies = yaml.load(dependencies_file)
      dependencies_file.close()
      if dependencies:
        EagerHelper.validate_dependencies(dependencies)
        app.dependencies = dependencies['dependencies']

    return app

  @classmethod
  def validate_dependencies(cls, dependencies):
    value = dependencies.get('dependencies')
    if not value: return
    if not isinstance(value, list):
      raise EagerException('Malformed dependencies.yaml file: dependencies entry must be a list.')
    for item in value:
      if not isinstance(item, dict):
        raise EagerException('Malformed dependencies.yaml file: dependency entries must be dictionaries')
      if not item.get('name'):
        raise EagerException('Missing name attribute in the dependency')
      if not item.get('version'):
        raise EagerException('Missing version attribute in the dependency')

  @classmethod
  def publish_api(cls, api, url, keyname):
    eager = EagerClient(LocalState.get_login_host(keyname),
      LocalState.get_secret_key(keyname))
    result = eager.publish_api(api.to_dict(), url)
    if result['success']:
      AppScaleLogger.log('API {0}-v{1} published to API store.'.format(api.name, api.version))
    else:
      AppScaleLogger.log('Failed to publish API {0}-v{1}.'.format(api.name, api.version))
      AppScaleLogger.warn(result['reason'])
      if result.get('detail'):
        AppScaleLogger.warn(str(result['detail']))