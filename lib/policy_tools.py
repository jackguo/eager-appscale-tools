# Policy Management Tool client libs
# Programmer: junsheng(junsheng.guo90@gmail.com)


# General-purpose Python library imports
import os
import sys
import argparse
import subprocess
import yaml
import re

# Make sure we're on Python 2.6 or greater before importing any code
# that's incompatible with older versions.
import version_helper
version_helper.ensure_valid_python_is_used()


from eager_client  import EagerClient
from remote_helper import RemoteHelper
from local_state import LocalState
from appscale import AppScale

class PolicyTools():

  USAGE = """eager-policy command [options] [args]: 

Available commands:
  add		add a new policy via file or reading content from std, options:

  remove	remove an existing policy by name
  list		list current policies in system, options:
  			-active: 	list all active policies;
			-inactive: 	list all inactive policies;
			-all:		list all policies

  info		display the content of a certain policy
  enable	enable an inactive policy by name
  disable	disable an active policy by name
  help		display help message of a certain command or this message if no cmd specified.
"""

  POLICY_DIR = "/root/appscale/Eager/policystore"
  SUPPORT_CMDS = {
      'add'    :  """eager-policy add policy_name [file] [-inactive]

    file is used to read the policy content from, if no file is provided, read from stdin

    By default, system makes the newly added policy active. If the policy is desired to be inactive, use the "-inactive" switch""",
      'remove' : """eager-policy remove policy_name
    
    Only one argument is needed, the policy name, but make sure the policy exists in the current system""",
      'list'   : """eager-policy list [-active|-inactive|-all]
    
    List policies by status. If no status is provided, all policies will be listed, same as "-all" switch""",
      'info'   : """eager-policy info policy_name
          display the content of a named policy""",
      'enable' : """eager-policy enable policy_name
          
          Only one argument is needed, the policy name, but make sure the policy exists in the current system and is inactive""",
      'disable': """eager-policy disable policy_name
          
          Only one argument is needed, the policy name, but make sure the policy exists in the current system and is active""",
      'help'   : ""}

  def __init__(self):
    self.key_name = self.get_key_name()
    self.service_host = LocalState.get_login_host(self.key_name)
    self.service_port = EagerClient.PORT

    # Detect if the EAGER service is running or not
    marker = re.compile("^" + str(self.service_port) + "/tcp")
    out = subprocess.Popen("nmap -p " + str(self.service_port) + " " + self.service_host, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in out.stdout.readlines():
      if marker.match(line):
        if(line.split()[1] == 'open'):
	  self.eager = EagerClient(self.service_host, LocalState.get_secret_key(self.key_name))
	else:
          self.eager = None
        break

  def get_key_name(self):
    """
    read key name from AppScalefile, which is by default believed in the current working directory.
    """
    appscale = AppScale()
    contents = appscale.read_appscalefile()
    contents_as_yaml = yaml.safe_load(contents)

    if "keyname" in contents_as_yaml:
	    return contents_as_yaml["keyname"]
    else:
	    print "No keyname found in AppScalefile...Abort\n"

  def add(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['add'])
    parser.add_argument("policy_name")
    parser.add_argument("policy_file", nargs="?", type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument("-inactive", action='store_true')
    options = parser.parse_args(argv)
    content = options.policy_file.read()
    if not options.policy_file == sys.stdin:
	    options.policy_file.close()

    if self.eager:
	    res = self.eager.add_policy(options.policy_name, content, not options.inactive)
	    if res[0] == 0:
		    print res[1]
    else: 
      if self.remote_exist(options.policy_name, 'all'):
        print "Error: Policy {0} already exists!".format(options.policy_name)
        return
      if options.inactive:
        s = '.i.py'
      else:
        s = '.a.py'
      s = options.policy_name + s
      tmp = open(s, "w")
      tmp.write(content)
      tmp.close()
      RemoteHelper.scp(self.service_host, self.key_name, s, self.POLICY_DIR, False)

  def remove(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['remove'])
    parser.add_argument("policy_name")
    options = parser.parse_args(argv)
    if self.eager:
	    res = self.eager.remove_policy(options.policy_name)
	    if res[0] == 0:
		    print res[1]
    else:
      if self.remote_exist(options.policy_name, "all"):
        self.ssh("rm " + self.POLICY_DIR + "/" + options.policy_name + ".[ai].py")
        return
      print "Policy {0} is not found!".format(options.policy_name)

  def list(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['list'])
    parser.add_argument("-active", action='store_true')
    parser.add_argument("-inactive", action='store_true')
    parser.add_argument("-all", action='store_true')

    options = parser.parse_args(argv)
    if options.active and options.inactive:
      print "Error using list cmd: only one option can be used"
      return

    if (not (options.active or options.inactive or options.all)) or options.all:
      status = 'all'
      print "All the policies:"
    elif options.active:
      status = 'active'
      print "All active policies:"
    else:
      status = 'inactive'
      print "All inactive policies:"

    res = self.remote_list(status)
    for item in res:
      print item[0]

  def info(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['info'])
    parser.add_argument("policy_name")
    options = parser.parse_args(argv)

    if self.remote_exist(options.policy_name, "all"):
      print self.get_remote_content(options.policy_name + ".[ai].py")
      return
    print "Error:  Policy {0} doesn't exist!".format(options.policy_name)

  def enable(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['enable']) 
    parser.add_argument("policy_name")
    options = parser.parse_args(argv)
    if self.eager:
      res = self.eager.enable_policy(options.policy_name)
      if res[0] == 0:
        print res[1]
    else:
      if self.remote_exist(options.policy_name, "inactive"):
        old_path = self.POLICY_DIR + "/" + options.policy_name + ".i.py"
        new_path = self.POLICY_DIR + "/" + options.policy_name + ".a.py"
        self.ssh("mv " + old_path + " " + new_path)
        return
      print "Error: No such inactvie policy: {0}".format(options.policy_name)

  def disable(self, argv):
    parser = argparse.ArgumentParser(usage=self.SUPPORT_CMDS['disable'])
    parser.add_argument("policy_name")
    options = parser.parse_args(argv)
    if self.eager:
      res = self.eager.disable_policy(options.policy_name)
      if res[0] == 0:
        print res[1]
    else:
      if self.remote_exist(options.policy_name, "active"):
        old_path = self.POLICY_DIR + "/" + options.policy_name + ".a.py"
        new_path = self.POLICY_DIR + "/" + options.policy_name + ".i.py"
        self.ssh("mv " + old_path + " " + new_path)
        return
      print "Error: No such actvie policy: {0}".format(options.policy_name)
    
  def help(self, argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd_name", nargs='?')
    options = parser.parse_args(argv)
    if options.cmd_name not in self.SUPPORT_CMDS.keys():
      print "unknown command: {0}".format(options.cmd_name)
      print self.USAGE
      return
    print "usage: " + self.SUPPORT_CMDS[options.cmd_name]

  def remote_list(self, status):
    out = self.ssh("ls " + self.POLICY_DIR)
    policies = out.split()
    reg = re.compile("(^[0-9a-zA-Z_]+)\\.([ai])\\.py$")
    match_res = [reg.match(item) for item in policies]

    if status == 'active':
      w_list = ['a']
    elif status == 'inactive':
      w_list = ['i']
    else:
      w_list = ['a', 'i']

    return [(item.groups()[0], item.groups()[1]) for item in match_res if item and item.groups()[1] in w_list]
  
  def remote_exist(self, name, status):
    for item in self.remote_list(status):
      if item[0] == name:
        return True
    return False

  def get_remote_content(self, filename):
    return self.ssh("cat " + self.POLICY_DIR + "/" + filename)

  def ssh(self, command):
    key_path = LocalState.get_key_path_from_name(self.key_name)
    ssh_command = "ssh -i {0} {1}@{2}  ".format(key_path, "root", self.service_host)
    p = subprocess.Popen(ssh_command + command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.read()
