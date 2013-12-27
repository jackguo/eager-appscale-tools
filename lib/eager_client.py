import socket
import ssl
import SOAPpy
import signal
import time
from custom_exceptions import TimeoutException

class EagerClient:

  # The port that the Eager service runs on by default.
  PORT = 18444

  # The number of times we should retry SOAP calls in case of failures.
  DEFAULT_NUM_RETRIES = 5

  def __init__(self, host, secret):
    """
    Creates a new EagerClient.

    Args:
      host: The location where an Eager service can be found.
      secret: A str containing the secret key, used to authenticate this client
        when talking to remote Eager endpoints.
    """
    self.host = host
    self.server = SOAPpy.SOAPProxy('https://%s:%s' % (host, self.PORT))
    self.secret = secret

  def run_with_timeout(self, timeout_time, num_retries, function, *args):
    """
    Runs the given function, aborting it if it runs for too long.

    Args:
      timeout_time: The number of seconds that we should allow function to
        execute for.
      num_retries: The number of times we should retry the SOAP call if we see
        an unexpected exception.
      function: The function that should be executed.
      *args: The arguments that will be passed to function.
    Returns:
      Whatever function(*args) returns if it runs within the timeout window
    """
    def timeout_handler(_, __):
      """
      Raises a TimeoutException if the function we want to execute takes
      too long to run.

      Raises:
        TimeoutException: If a SIGALRM is raised.
      """
      raise TimeoutException()

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_time)  # trigger alarm in timeout_time seconds
    try:
      ret_val = function(*args)
    except TimeoutException as exception:
      return self.handle_exception(exception, 'Client timed out')
    except ssl.SSLError:
      # these are intermittent, so don't decrement our retry count for this
      signal.alarm(0)  # turn off the alarm before we retry
      return self.run_with_timeout(timeout_time, num_retries, function, *args)
    except socket.error as exception:
      signal.alarm(0)  # turn off the alarm before we retry
      if num_retries > 0:
        time.sleep(1)
        return self.run_with_timeout(timeout_time, num_retries - 1, function, *args)
      else:
        return self.handle_exception(exception, 'Socket error')
    except Exception as exception:
      return self.handle_exception(exception, 'Unexpected client error')
    finally:
      signal.alarm(0)  # turn off the alarm

    return ret_val

  def handle_exception(self, ex, reason):
    ret_val = { 'success' : False, 'reason' : reason, 'detail' : ex }
    return ret_val

  def ping(self):
    return self.run_with_timeout(10, self.DEFAULT_NUM_RETRIES,
      self.server.ping, self.secret)

  def validate_api_for_deployment(self, api):
    return self.run_with_timeout(10, self.DEFAULT_NUM_RETRIES,
      self.server.validate_api_for_deployment, self.secret, api)

  def publish_api(self, api, url):
    return self.run_with_timeout(10, self.DEFAULT_NUM_RETRIES,
      self.server.publish_api, self.secret, api, url)