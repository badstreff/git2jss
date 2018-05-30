#!/usr/bin/env python

import requests
from xml.etree import ElementTree as ET
from xml.dom import minidom
import os
import argparse


import urllib3

# Suppress the warning in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mypath = os.path.dirname(os.path.realpath(__file__))

def download_scripts(mode, overwrite=None,):
    """ Downloads Scripts to ./scripts and Extension Attributes to ./extenstion_attributes

    Folder Structure:
    ./scripts/script_name/script.sh
    ./scripts/script_name/script.xml
    ./extenstion_attributes/ea_name/ea.sh
    ./extenstion_attributes/ea_name/ea.xml    

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
        auth = (args.username, args.password), 
        headers= {'Content-Type': 'application/xml'}, 
        verify=args.do_not_verify_ssl)
    tree = ET.fromstring(r.content) 
    resource_ids = [ e.text for e in tree.findall('.//id') ]

    # Download each resource and save to disk
    for resource_id in resource_ids:

        r = requests.get(args.url + '/JSSResource/%s/id/%s' % (resource,resource_id), 
            auth = (args.username, args.password), 
            headers= {'Content-Type': 'application/xml'}, verify=args.do_not_verify_ssl)
        tree = ET.fromstring(r.content)

        if mode == 'ea':
            if tree.find('input_type/type').text != 'script': 
                print(tree.find(script_xml).text)
                print('No script found in: %s' % tree.find('name').text)
                continue

        # Determine resource path (folder name)
        resource_path = os.path.join(mypath, download_path ,tree.find('name').text)

        # Check to see if it exists
        if os.path.exists(resource_path):
            print("Resource is already in the repo: ", tree.find('name').text)

            if not overwrite:
                print("\tSkipping: ", tree.find('name').text)
                continue


        else:    # Make the folder 
            os.makedirs(resource_path)

        print('Saving: ', tree.find('name').text)

        # Determine the file extension
        if '#!/bin/sh' in ET.tostring(tree.find(script_xml), encoding='unicode', method='text'):
            ext = '.sh'
        
        elif '#!/bin/bash' in ET.tostring(tree.find(script_xml), encoding='unicode', method='text'):
            ext = '.sh'

        elif '#!/usr/bin/python' in ET.tostring(tree.find(script_xml), encoding='unicode', method='text'):
            ext = '.py'

        elif '#!/usr/bin/env python' in ET.tostring(tree.find(script_xml), encoding='unicode', method='text'):
            ext = '.py'

        elif '#!/usr/bin/perl' in ET.tostring(tree.find(script_xml), encoding='unicode', method='text'):
            ext = '.py'

        else:
            print('No interpreter directive found for: ', tree.find('name').text)
            ext = '.sh' # Call it sh for now so the uploader detects it
        
        xmlstr = ET.tostring(tree.find(script_xml), encoding='unicode', method='text').replace('\r','')
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
    parser.add_argument('--do_not_verify_ssl', action='store_false') # Skips SSL verifcation 
    args = parser.parse_args()

    # Run script download for extension attributes
    download_scripts(overwrite=args.overwrite, mode='ea')
    # Run script download for scripts
    download_scripts(overwrite=args.overwrite, mode='script')
