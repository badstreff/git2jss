#!/usr/bin/env python
import getpass
import requests
from xml.etree import ElementTree as ET
from xml.dom import minidom
import os
import argparse
import urllib3
import configparser

# Suppress the warning in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mypath = os.path.dirname(os.path.realpath(__file__))

def download_scripts(mode, overwrite=None,):
    """ Downloads Scripts to ./scripts and Extension Attributes to ./extension_attributes

    Folder Structure:
    ./scripts/script_name/script.sh
    ./scripts/script_name/script.xml
    ./extension_attributes/ea_name/ea.sh
    ./extension_attributes/ea_name/ea.xml

    Usage:

    Download all Extension Attributes from JSS:
    download_scripts('ea','overwrite=False)

    Download all Extension Attributes from JSS:
    download_scripts('script','overwrite=False)

    Params:
    mode = 'script' or 'ea'
    overwrite = True/False
    Returns: None
    """

    # Set various values based on resource type
    if mode == 'ea':
        resource = 'computerextensionattributes'
        download_path = 'extension_attributes'
        script_xml = 'input_type/script'

    if mode == 'script':
        resource = 'scripts'
        download_path = 'scripts'
        script_xml = 'script_contents'


    # Get all IDs of resource type
    r = requests.get(args.url + '/JSSResource/%s' %resource,
        auth = (args.username, password),
        headers= {'Accept': 'application/xml','Content-Type': 'application/xml'},
        verify=args.do_not_verify_ssl)

    # Basic error handling
    if r.status_code != 200:
        print("Something went wrong with the request, check your password and privileges and try again. \n \
        It's also possible that the url is incorrect. \n \
        Here is the HTTP Status code: %s" % r.status_code)
        exit(1)
    tree = ET.fromstring(r.content)
    resource_ids = [ e.text for e in tree.findall('.//id') ]

    # Download each resource and save to disk
    for resource_id in resource_ids:
        get_script = True

        r = requests.get(args.url + '/JSSResource/%s/id/%s' % (resource,resource_id),
            auth = (args.username, password),
            headers= {'Accept': 'application/xml','Content-Type': 'application/xml'}, verify=args.do_not_verify_ssl)
        tree = ET.fromstring(r.content)

        if mode == 'ea':
            if tree.find('input_type/type').text != 'script':
                print('No script found in: %s' % tree.find('name').text)
                get_script = False
                # continue

        # Determine resource path (folder name)
        resource_path = os.path.join(mypath, '..', download_path ,tree.find('name').text)

        # Check to see if it exists
        if os.path.exists(resource_path):
            print("Resource is already in the repo: ", tree.find('name').text)

            if not overwrite:
                print("\tSkipping: ", tree.find('name').text)
                continue


        else:    # Make the folder
            os.makedirs(resource_path)

        print('Saving: ', tree.find('name').text)

        # Create script string, and determine the file extension
        if get_script:
            xmlstr = ET.tostring(tree.find(script_xml), encoding='unicode', method='text').replace('\r','')
            if xmlstr.startswith('#!/bin/sh'):
                ext = '.sh'
            elif xmlstr.startswith('#!/usr/bin/env sh'):
                ext = '.sh'
            elif xmlstr.startswith('#!/bin/bash'):
                ext = '.sh'
            elif xmlstr.startswith('#!/usr/bin/env bash'):
                ext = '.sh'
            elif xmlstr.startswith('#!/bin/zsh'):
                ext = '.sh'
            elif xmlstr.startswith('#!/usr/bin/python'):
                ext = '.py'
            elif xmlstr.startswith('#!/usr/bin/env python'):
                ext = '.py'
            elif xmlstr.startswith('#!/usr/bin/perl'):
                ext = '.pl'
            elif xmlstr.startswith('#!/usr/bin/ruby'):
                ext = '.rb'
            else:
                print('No interpreter directive found for: ', tree.find('name').text)
                ext = '.sh' # Call it sh for now so the uploader detects it

            with open(os.path.join(resource_path, '%s%s' % (mode,ext)), 'w') as f:
                f.write(xmlstr)

            # Need to remove ID and script contents and write out xml
            try:
                tree.find(script_xml).clear()
                tree.remove(tree.find('id'))
                tree.remove(tree.find('script_contents_encoded'))
                tree.remove(tree.find('filename'))
            except:
                pass

        xmlstr = minidom.parseString(ET.tostring(tree, encoding='unicode', method='xml')).toprettyxml(indent="   ")
        with open(os.path.join(resource_path, '%s.xml' % mode), 'w') as f:
            f.write(xmlstr)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download Scripts from Jamf')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--overwrite', action='store_true') # Overwrites existing files
    parser.add_argument('--do_not_verify_ssl', action='store_false') # Skips SSL verification
    args = parser.parse_args()
    # Get configs from files
    CONFIG_FILE_LOCATIONS = ['jamfapi.cfg',os.path.expanduser('~/jamfapi.cfg')]
    CONFIG_FILE = ''
    # Parse Config File
    CONFPARSER = configparser.ConfigParser()
    for config_path in CONFIG_FILE_LOCATIONS:
        if os.path.exists(config_path):
            print("Found Config: {0}".format(config_path))
            CONFIG_FILE = config_path

    if CONFIG_FILE == "":
        config_ = configparser.ConfigParser()
        config_['jss'] = {}
        config_['jss']['username'] = "username"
        config_['jss']['password'] = "password"
        config_['jss']['server'] = "server"
        print(config_)
        with open('jamfapi.cfg', 'w') as configfile:
            config_.write(configfile)
        print("Config File Created. Please edit jamfapi.cfg and run again.")
        
        print("No Config File found!")
        exit(0)
    else:
        # Read local directory, user home, then /etc/ for besapi.conf
        CONFPARSER.read(CONFIG_FILE)
        # If file exists
        # Get config
        args.username = CONFPARSER.get('jss', 'username')
        args.password = CONFPARSER.get('jss', 'password')
        args.url = CONFPARSER.get('jss', 'server')
    
    # Ask for password if not supplied via command line args
    if args.password:
        password = args.password
    else:
        password = getpass.getpass()

    # Run script download for extension attributes
    download_scripts(overwrite=args.overwrite, mode='ea')
    # Run script download for scripts
    download_scripts(overwrite=args.overwrite, mode='script')
