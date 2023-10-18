#!/bin/sh
lastUser=`defaults read /Library/Preferences/com.apple.loginwindow lastUserName`

if [ $lastUser == "" ]; then
	echo "<result>No logins</result>"
else
	echo "<result>$lastUser</result>"