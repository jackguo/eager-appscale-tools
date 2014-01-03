import json
import os
import yaml
from appscale_logger import AppScaleLogger
from eager_client import EagerClient
from local_state import LocalState

class EagerException(Exception):
  pass

class APISpec:
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
    self.dependencies = []

  def to_dict(self):
    result = {
      'name' : self.name,
      'version' : self.version,
      'specification' : self.specification,
      'dependencies' : self.dependencies
    }
    return result

class EagerHelper:

  @classmethod
  def perform_eager_validation(cls, api_info, keyname):
    eager = EagerClient(LocalState.get_login_host(keyname),
      LocalState.get_secret_key(keyname))
    error_occurred = False
    for api in api_info:
      AppScaleLogger.log('Found specification for API: {0}-v{1}'.format(api.name, api.version))
      validation_result = eager.validate_api_for_deployment(api.to_dict())
      if validation_result['success']:
        AppScaleLogger.log('API {0}-v{1} validated successfully.'.format(api.name, api.version))
      else:
        AppScaleLogger.log('API {0}-v{1} validation failed.'.format(api.name, api.version))
        if hasattr(validation_result, 'detail'):
          errors = str(validation_result.detail).split('|')
          if len(errors) == 1:
            AppScaleLogger.warn('{0}: {1}'.format(validation_result['reason'],
              str(validation_result.detail)))
          else:
            AppScaleLogger.warn('{0}: '.format(validation_result['reason']))
            for error in errors:
              AppScaleLogger.warn('  * {0}'.format(error))
        else:
          AppScaleLogger.warn(validation_result['reason'])
        error_occurred = True
    return not error_occurred

  @classmethod
  def get_api_info(cls, app_language, app_dir):
    if app_language != 'java':
      return None
    api_specs_dir = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'specs'
    dependencies_path = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'dependencies.yaml'

    dependencies = {}
    if os.path.exists(dependencies_path):
      dependencies_file = open(dependencies_path, 'r')
      dependencies = yaml.load(dependencies_file)
      dependencies_file.close()
      if dependencies is None:
        dependencies = {}
      else:
        EagerHelper.validate_dependencies(dependencies)

    if os.path.exists(api_specs_dir):
      api_info = []
      for f in os.listdir(api_specs_dir):
        if f.endswith('.json'):
          api_spec = APISpec(api_specs_dir + os.sep + f)
          api_dependencies = dependencies.get(api_spec.name + '_' + api_spec.version)
          if api_dependencies:
            api_spec.dependencies = api_dependencies
          api_info.append(api_spec)
      if api_info:
        return api_info
    return None

  @classmethod
  def validate_dependencies(cls, dependencies):
    for key,value in dependencies.items():
      if not isinstance(value, list):
        raise EagerException('Entry {0} of dependencies.yaml is invalid'.format(key))
      for item in value:
        if not isinstance(item, dict):
          raise EagerException('Entry {0} of dependencies.yaml is invalid'.format(key))
        if not item.get('name'):
          raise EagerException('Missing name attribute in the dependency for: {0}'.format(key))
        if not item.get('version'):
          raise EagerException('Missing version attribute in the dependency for: {0}'.format(key))

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