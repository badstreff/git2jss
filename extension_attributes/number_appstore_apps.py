#!/usr/bin/python

import xml.etree.ElementTree as ET
import plistlib

receipt_path = '/Library/Receipts/InstallHistory.plist'
receipts = plistlib.readPlist(receipt_path)

exclude = ('macOS', 'Install macOS High Sierra', 'QuickAdd')

apps = set(item['displayName'] for item in receipts if item['processName'] == 'storedownloadd' and item['displayName'] not in exclude)
print '<result>%s</result>' % len(apps)
