#! /usr/bin/env python

import click
import datetime
import json
import logging
import os
from tkinter import *
from tkinter.ttk import Combobox

"""
    A simple interface to track where time is spent during work
"""

DEFAULT_CONFIG_SETTINGS = {
    'log_dir': '~/.tt/logs',
    'log_filename': 'timesheet',
    'categories':
     {
         'Coding': 'Coding, testing and debugging activities.',
         'Email': 'Reading and responding to email.',
         'Learning': 'Learning activities like on-line courses, wiki pages, etc.',
         'LinkedIn': 'Browsing or using LinkedIn.',
         'Meetings': 'Attending a meeting in person or via video.',
         'Off': 'Out of the office.',
         'Other': 'Non-work related activities like lunch, Facebook, etc.',
         'Reviews': 'Code or design review activities.',
         'Slack': 'Using slack.',
         'Support': 'Working on tickets or directly with users.',
     },
     'default_category': 'Off'
}
DEFAULT_SETTINGS = {
    'config_dir': '~/.tt',
    'config_file': 'config',
}
LOG_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'


def handle_home_expansion():
    """Expand any ~ default directories to appropriate path value"""
    if DEFAULT_CONFIG_SETTINGS['log_dir'].startswith('~'):
        DEFAULT_CONFIG_SETTINGS['log_dir'] = os.path.expanduser(DEFAULT_CONFIG_SETTINGS['log_dir'])
    if DEFAULT_SETTINGS['config_dir'].startswith('~'):
        DEFAULT_SETTINGS['config_dir'] = os.path.expanduser(DEFAULT_SETTINGS['config_dir'])


def create_default_config_file(config_file):
    """Create a default configuration file in the specified location"""
    try:
        with open(config_file, 'w') as cfg_f:
            json.dump(DEFAULT_CONFIG_SETTINGS, cfg_f)
    except Exception as e:
        raise ProgramExit('Unable to create config file: %s', e)


def _chk_create_dir(dir):
    """Checks if the path exists as a directory or creates it"""
    if not os.path.exists(dir):
        try:
            os.makedirs(dir)
        except Exception as e:
            raise ProgramExit('Unable to create %s directory: %s', dir, e)
    elif not os.path.isdir(dir):
        raise ProgramExit('%s is not a directory.', dir)


def setup_log_directory(log_dir=None):
    """Set up the logging directory where time is logged"""
    if not log_dir:
        log_dir = os.path.join(DEFAULT_CONFIG_SETTINGS['log_dir'])
    _chk_create_dir(log_dir)


def setup_initial_configuration(config_dir=None):
    """Set up the initial configuration. Assumes it does not currently exist"""
    if not config_dir:
        config_dir = DEFAULT_SETTINGS['config_dir']
    _chk_create_dir(config_dir)
    config_file = os.path.join(config_dir, DEFAULT_SETTINGS['config_file'])
    if os.path.exists(config_file):
        log.warning('Config file alread exists, will use this file: %s', config_file)
    else:
        create_default_config_file(config_file)
    setup_log_directory(DEFAULT_CONFIG_SETTINGS['log_dir'])


def read_configs(config_file):
    """Read in the configuration from the config file"""
    with open(config_file) as config_f:
        configs = json.load(config_f)
    return configs


def log_entry(entry, configs):
    """Makes a UTC time stamped entry into the log file.

       Handles the creation of a new log file if required.
    """
    timestamp = datetime.datetime.utcnow()
    timestmap_file_base = configs['log_filename']
    timestamp_file = '{0}-{1}.log'.format(timestmap_file_base, timestamp.strftime('%d-%m-%Y'))
    log_file = os.path.join(configs['log_dir'], timestamp_file)
    with open(log_file, 'a') as log_f:
        log_f.write('{0} {1}\n'.format(timestamp.strftime(LOG_TIMESTAMP_FORMAT), entry))

class TimeSheet(object):

    def __init__(self, configs, master):
        self.configs = configs

        # Set up app window.
        self.master = master
        self.frame = Frame(master)
        self.frame.grid()

        # Set app title.
        self.Title = Label(self.frame, text='Now working on:')
        self.Title.grid(row=0, column=0)

        # Set up the selection list with all the activity categories.
        self.activity_categories = sorted(configs['categories'].keys())
        default_activity_index = self.activity_categories.index(configs['default_category'])
        if configs['long-definitions']:
           activity_categories_display = ['{0}: {1}'.format(category, configs['categories'][category]) for category in self.activity_categories]
        else:
           activity_categories_display = self.activity_categories
        text_length = max([len(i) for i in activity_categories_display])
        self.activityBox = Combobox(self.frame, width=text_length)
        self.activityBox['values'] = activity_categories_display
        self.activityBox.current(default_activity_index)
        self.activityBox.bind('<<ComboboxSelected>>', self.log_activity)
        self.activityBox.grid(row=1, column=0)

        # Set up app quit button.
        self.quit = Button(self.frame, text='Quit', command=self.end)
        self.quit.grid(row=2, column=0)

        # Log the default entry which is set up upon startup.
        log_entry(self.configs['default_category'], configs)

    def log_activity(self, evt):
        """New activity selected, log it"""
        activity = self.activityBox.get()
        # If we are using long activities, need to get the short name
        if self.configs['long-definitions']:
            for short_name in self.activity_categories:
                if activity.startswith(short_name):
                    activity = short_name
                    break
        log_entry(activity, self.configs)

    def end(self):
        """Log default activity prior to quiting."""
        log_entry(self.configs['default_category'], self.configs)
        self.frame.quit()


@click.command()
@click.option('-c', '--config-file', default=None, help='Configuration file location for timesheet application.')
@click.option('--use-long-defs', is_flag=True, help='Use the long definition of each activity')
def main(use_long_defs, config_file):

    # Set up logger
    log = logging.getLogger(__name__)
    logging.StreamHandler().setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)

    # Handle ~ expansion if it exists
    handle_home_expansion()

    # Find and read in configs. Create defaults if not already in place
    default_config_file = os.path.join(DEFAULT_SETTINGS['config_dir'], DEFAULT_SETTINGS['config_file'])
    if config_file:
        if not os.path.exists(config_file) or not os.path.isfile(config_file):
            log.warning('Cannot locate config file %s. Using default config file location %s.', config_file, default_config_file)
            if not os.path.exists(default_config_file) or not os.path.isfile(default_config_file):
                log.warning('Cannot locate default config file %s. Creating one and using default configs.')
                setup_initial_configuration()
                configs = DEFAULT_CONFIG_SETTINGS
            else:
                configs = read_configs(default_config_file)
        else:
            configs = read_configs(config_file)
    else:
        if not os.path.exists(default_config_file) or not os.path.isfile(default_config_file):
            log.warning('Cannot locate default config file %s. Creating one and using default configs.')
            setup_initial_configuration()
            configs = DEFAULT_CONFIG_SETTINGS
        else:
            configs = read_configs(default_config_file)
    configs['long-definitions'] = use_long_defs

    # Main application loop
    root = Tk()
    app = TimeSheet(configs, root)
    root.mainloop()


if __name__ == '__main__':
    main()
