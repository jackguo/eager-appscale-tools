import json
import os
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

  def to_dict(self):
    result = {
      'name' : self.name,
      'version' : self.version
    }
    return result

class EagerHelper:

  @classmethod
  def perform_eager_validation(cls, app_language, app_dir, keyname):
    if app_language == 'java':
      api_info = EagerHelper.get_api_info(app_dir)
      if api_info:
        eager = EagerClient(LocalState.get_login_host(keyname),
          LocalState.get_secret_key(keyname))
        error_occurred = False
        for api in api_info:
          AppScaleLogger.log('Found specification for API: {0}-v{1}'.format(api.name, api.version))
          validation_result = eager.validate_api_for_deployment(api.to_dict())
          if validation_result['success']:
            AppScaleLogger.log('API {0}-v{1} validated successfully'.format(api.name, api.version))
          else:
            AppScaleLogger.log('API {0}-v{1} validation failed'.format(api.name, api.version))
            error_occurred = True
        if error_occurred:
          return False
    return True

  @classmethod
  def get_api_info(cls, app_dir):
    api_specs_dir = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'specs'
    if os.path.exists(api_specs_dir):
      api_info = []
      for f in os.listdir(api_specs_dir):
        if f.endswith('.json'):
          api_spec = APISpec(api_specs_dir + os.sep + f)
          api_info.append(api_spec)
      if api_info:
        return api_info
    return None