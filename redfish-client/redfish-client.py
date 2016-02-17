#!/usr/bin/python

# coding=utf-8

'''
redfish-client ::

 Usage:
   redfish-client.py [options] config add <manager_name> <manager_url> [<login>] [<password>]
   redfish-client.py [options] config del <manager_name>
   redfish-client.py [options] config modify <manager_name> (manager_name | url | login | password) <changed_value>
   redfish-client.py [options] config show
   redfish-client.py [options] config showall
   redfish-client.py [options] manager getinfo [<manager_name>]
   redfish-client.py (-h | --help)
   redfish-client.py --version
 
 
 Options:
   -h --help             Show this screen.
   --version             Show version.
   --conf_file FILE      Configuration file [default: ~/.redfish.conf]
   --insecure            Ignore SSL certificates
   --debug LEVEL         Run in debug mode, LEVEL from 1 to 3 increase verbosity
                         Security warning LEVEL > 1 could reveal password into the logs
   --debugfile FILE      Specify the client debugfile [default: redfish-client.log]
   --libdebugfile FILE   Specify python-redfish library log file [default: /var/log/python-redfish/python-redfish.log]
 
 config commands : manage the configuration file.
 manager commands : manage the manager (Ligh out management). If <manager_name>
                    is not provided use the 'default' entry
'''

import os
import sys
import json
import pprint
import docopt
import logging
import ConfigParser
import jinja2
import requests.packages.urllib3
import redfish

class ConfigFile(object):
    '''redfisht-client configuration file management'''
    def __init__(self, config_file):
        '''Initialize the configuration file

        Open and load configuration file data.
        If the file does not exist create an empty one ready to receive data

        :param config_file: File name of the configuration file
                            default: ~/.redfish.conf
        :type config-file: str
        :returns: Nothing

        '''
        self._config_file = config_file
        # read json file
        try:
            with open(self._config_file) as json_data:
                self.data = json.load(json_data)
                json_data.close()
        except (ValueError, IOError):
            self.data = {'Managers': {}}

    def save(self):
        '''Save the configuration file data'''
        try:
            with open(self._config_file, 'w') as json_data:
                json.dump(self.data, json_data)
                json_data.close()
        except IOError as e:
            print(e.msg)
            sys.exit(1)

    def manager_incorect(self, exception):
        ''' Log and exit if manager name is incorect'''
        logger.error('Incorect manager name : %s' % exception.args)
        sys.exit(1)

    def check_manager(self, manager_name):
        '''Check if the manager exists in configuration file

        :param manager_name: Name of the manager
        :type manager_name: str

        '''
        try:
            if manager_name not in self.get_managers():
                raise KeyError(manager_name)
        except KeyError as e:
            self.manager_incorect(e)

    def add_manager(self, manager_name, url, login, password):
        '''Add a manager to the configuration file

        :param manager_name: Name of the manager
        :type manager_name: str
        :param url: Url of the manager
        :type url: str
        :param login: Login of the manager
        :type login: str
        :param password: Password of the manager
        :type password: str

        '''

        self.data['Managers'][manager_name] = {}
        self.data['Managers'][manager_name]['url'] = url
        if login is None:
            login = ''
        if password is None:
            password = ''
        self.data['Managers'][manager_name]['login'] = login
        self.data['Managers'][manager_name]['password'] = password

    def modify_manager(self, manager_name, parameter, parameter_value):
        '''Modify the manager settings

        :param manager_name: Name of the manager
        :type manager_name: str
        :param parameter: url | login | password
        :type url: str
        :param parameter_value: Value of the parameter
        :type parameter_value: str
        :returns: Nothing

        '''

        if parameter == 'url':
            try:
                self.data['Managers'][manager_name]['url'] = parameter_value
            except KeyError as e:
                self.manager_incorect(e)
        elif parameter == 'login':
            try:
                self.data['Managers'][manager_name]['login'] = parameter_value
            except KeyError as e:
                self.manager_incorect(e)
        elif parameter == 'password':
            try:
                self.data['Managers'][manager_name]['password'] = parameter_value
            except KeyError as e:
                self.manager_incorect(e)
        elif parameter == 'manager_name':
            # Create a new entry with the new name
            self.add_manager(parameter_value,
                             self.data['Managers'][manager_name]['url'],
                             self.data['Managers'][manager_name]['login'],
                             self.data['Managers'][manager_name]['password'],
                             )
            # Remove the previous one
            self.delete_manager(manager_name)

    def delete_manager(self, manager_name):
        '''Delete manager

        :param manager_name: Name of the manager
        :type manager_name: str
        :returns: Nothing

        '''

        try:
            del self.data['Managers'][manager_name]
        except KeyError as e:
            self.manager_incorect(e)

    def get_managers(self):
        '''Get manager configured

        :returns: Managers
        :type returns: list

        '''
        managers = []
        for manager in self.data['Managers']:
            managers += [manager]
        return(managers)

    def get_manager_info(self, manager):
        '''Show manager info (url, login, password)

        :param manager: Name of the manager
        :type manager: str
        :returns: info containing url, login, password
        :type returns: dict

        '''
        info = {}
        url = self.data['Managers'][manager]['url']
        login = self.data['Managers'][manager]['login']
        password = self.data['Managers'][manager]['password']
        info = {'url': url, 'login': login, 'password': password}
        return(info)


class RedfishClientException(Exception):

    '''Base class for redfish client exceptions'''

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs
        self.message = message


if __name__ == '__main__':
    '''Main application redfish-client'''
    # Functions

    def show_manager(all=False):
        '''Display manager info

        :param all: Add login and password info
        :type all: bool
        :returns: Nothing

        '''
        print('Managers configured :')
        for manager in conf_file.get_managers():
            print(manager)
            if all is True:
                info = conf_file.get_manager_info(manager)
                print('\tUrl : {}'.format(info['url']))
                print('\tLogin : {}'.format(info['login']))
                print('\tPassword : {}'.format(info['password']))

    def get_manager_info(manager_name, check_SSL):
        connection_parameters = conf_file.get_manager_info(manager_name)
        if not connection_parameters['login']:
            simulator = True
            enforceSSL = False
        else:
            simulator = False
            enforceSSL = True
        try:
            print('Gathering data from manager, please wait...\n')
            # TODO : Add a rotating star showing program is running ?
            #        Could be a nice exercice for learning python. :)
            logger.info('Gathering data from manager')
            remote_mgmt = redfish.connect(connection_parameters['url'],
                                          connection_parameters['login'],
                                          connection_parameters['password'],
                                          verify_cert=check_SSL,
                                          simulator=simulator,
                                          enforceSSL=enforceSSL
                                          )
        except redfish.exception.RedfishException as e:
            sys.stderr.write(str(e.message))
            sys.stderr.write(str(e.advices))
            sys.exit(1)

        # Display manager information using jinja2 template      
        try:
            template = jinja2_env.get_template("manager_info.template")
        except jinja2.exceptions.TemplateNotFound as e:
            print('Template "{}" not found in {}.'.format(e.message, jinja2_env.loader.searchpath[0]))
            logger.debug('Template "%s" not found in %s.' % (e.message, jinja2_env.loader.searchpath[0]))
            sys.exit(1)
        
        print template.render(r=remote_mgmt)


    # Main program
    redfishclient_version = "redfish-client PBVER"

    # Parse and manage arguments
    arguments = docopt.docopt(__doc__, version=redfishclient_version)

    # Check debuging options
    # Debugging LEVEL :
    # 1- Only client
    # 2- Client and lib
    # 3- Client and lib + Tortilla

    loglevel = {"console_logger_level": "nolog",
                "file_logger_level": logging.INFO,
                "tortilla": False,
                "lib_console_logger_level": "nolog",
                "lib_file_logger_level": logging.INFO,
                "urllib3_disable_warning": True}

    if arguments['--debug'] == '1':
        loglevel['console_logger_level'] = logging.DEBUG
        loglevel['file_logger_level'] = logging.DEBUG
    elif arguments['--debug'] == '2':
        loglevel['console_logger_level'] = logging.DEBUG
        loglevel['file_logger_level'] = logging.DEBUG
        loglevel['lib_console_logger_level'] = logging.DEBUG
        loglevel['lib_file_logger_level'] = logging.DEBUG
        loglevel['urllib3_disable_warning'] = False
    elif arguments['--debug'] == '3':
        loglevel['console_logger_level'] = logging.DEBUG
        loglevel['file_logger_level'] = logging.DEBUG
        loglevel['lib_console_logger_level'] = logging.DEBUG
        loglevel['lib_file_logger_level'] = logging.DEBUG
        loglevel['urllib3_disable_warning'] = False
        loglevel['tortilla'] = True

    # Initialize logger according to command line parameters
    logger = redfish.config.initialize_logger(arguments['--debugfile'],
                                              loglevel['console_logger_level'],
                                              loglevel['file_logger_level'],
                                              __name__)
    redfish.config.REDFISH_LOGFILE = arguments['--libdebugfile']
    redfish.config.TORTILLADEBUG = loglevel['tortilla']
    redfish.config.CONSOLE_LOGGER_LEVEL = loglevel['lib_console_logger_level']
    redfish.config.FILE_LOGGER_LEVEL = loglevel['lib_file_logger_level']
    # Avoid warning messages from request / urllib3
    # SecurityWarning: Certificate has no `subjectAltName`, falling back
    # to check for a `commonName` for now. This feature is being removed
    # by major browsers and deprecated by RFC 2818.
    # (See https://github.com/shazow/urllib3/issues/497 for details.)
    if loglevel['urllib3_disable_warning'] is True:
        requests.packages.urllib3.disable_warnings()

    logger.info("*** Starting %s ***" % redfishclient_version)
    logger.info("Arguments parsed")
    logger.debug(arguments)

    # Get $HOME and $VIRTUAL_ENV environment variables.
    HOME = os.getenv('HOME')
    VIRTUAL_ENV = os.getenv('VIRTUAL_ENV')

    if not HOME:
        print('$HOME environment variable not set, please check your system')
        logger.error('$HOME environment variable not set')
        sys.exit(1)
    logger.debug("Home directory : %s" % HOME)
    
    if VIRTUAL_ENV:
        logger.debug("Virtual env : %s" % VIRTUAL_ENV)
        
    # Load master conf file
    config = ConfigParser.ConfigParser(allow_no_value=True)
    logger.debug("Read master configuration file")
    master_conf_file_path = "/etc/redfish-client.conf"
    
    if VIRTUAL_ENV:
        logger.debug("Read master configuration file from virtual environment")
        master_conf_file_path = VIRTUAL_ENV + master_conf_file_path
        
    if not os.path.isfile(master_conf_file_path):
        print('Master configuration file not found at {}.'.format(master_conf_file_path))
        logger.error('Master configuration file not found at %s.' % master_conf_file_path)
        sys.exit(1)
    
    config.read(master_conf_file_path)

    arguments['--conf_file'] = arguments['--conf_file'].replace('~', HOME)
    conf_file = ConfigFile(arguments['--conf_file'])
    
    # Initialize Template system (jinja2)
    # TODO : set the template file location into cmd line default to /usr/share/python-redfish/templates ?
    templates_path = config.get("redfish-client", "templates_path")
    logger.debug("Initialize template system")
    if VIRTUAL_ENV:
        logger.debug("Read templates file from virtual environment")
        templates_path = VIRTUAL_ENV + templates_path
    jinja2_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
    
    # Check cmd line parameters
    if arguments['config'] is True:
        logger.debug("Config commands")
        if arguments['show'] is True:
            logger.debug('show command')
            show_manager()
        elif arguments['showall'] is True:
            logger.debug('showall command')
            show_manager(True)
        elif arguments['add'] is True:
            logger.debug('add command')
            conf_file.add_manager(arguments['<manager_name>'],
                                  arguments['<manager_url>'],
                                  arguments['<login>'],
                                  arguments['<password>'])
            logger.debug(conf_file.data)
            conf_file.save()
        elif arguments['del'] is True:
            logger.debug('del command')
            conf_file.delete_manager(arguments['<manager_name>'])
            logger.debug(conf_file.data)
            conf_file.save()
        elif arguments['modify'] is True:
            logger.debug('modify command')
            if arguments['url'] is not False:
                conf_file.modify_manager(arguments['<manager_name>'],
                                         'url',
                                         arguments['<changed_value>'])
            elif arguments['login'] is not False:
                conf_file.modify_manager(arguments['<manager_name>'],
                                         'login',
                                         arguments['<changed_value>'])
            elif arguments['password'] is not False:
                conf_file.modify_manager(arguments['<manager_name>'],
                                         'password',
                                         arguments['<changed_value>'])
            elif arguments['manager_name'] is not False:
                conf_file.modify_manager(arguments['<manager_name>'],
                                         'manager_name',
                                         arguments['<changed_value>'])
            logger.debug(conf_file.data)
            conf_file.save()
    if arguments['manager'] is True:
        logger.debug("Manager commands")
        if arguments['getinfo'] is True:
            logger.debug('getinfo command')
            # If manager is not defined set it to 'default'
            if not arguments['<manager_name>']:
                manager_name = 'default'
            else:
                manager_name = arguments['<manager_name>']
            # Check if the default section is available in our conf file
            conf_file.check_manager(manager_name)
            if arguments['--insecure'] is True:
                get_manager_info(manager_name, False)
            else:
                get_manager_info(manager_name, True)

    logger.info("Client session teminated")
    sys.exit(0)
