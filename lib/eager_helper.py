import os
from appscale_logger import AppScaleLogger
from eager_client import EagerClient
from local_state import LocalState

class EagerHelper:

  @classmethod
  def perform_eager_validation(cls, app_language, app_dir, keyname):
    if app_language == 'java':
      api_info = EagerHelper.get_api_info(app_dir)
      if api_info:
        eager = EagerClient(LocalState.get_login_host(keyname),
          LocalState.get_secret_key(keyname))
        for api in api_info.keys():
          AppScaleLogger.log('Found API: {0}'.format(api))
          AppScaleLogger.log(str(eager.ping()))
    return True

  @classmethod
  def get_api_info(cls, app_dir):
    api_specs_dir = app_dir + os.sep + 'war' + os.sep + 'WEB-INF' + os.sep + 'specs'
    if os.path.exists(api_specs_dir):
      api_info = { }
      for f in os.listdir(api_specs_dir):
        if f.endswith('.json'):
          api_info[f] = True
      if api_info:
        return api_info
    return None