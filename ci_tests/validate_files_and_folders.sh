#!/bin/bash
###################################################################################
## Looks for the existance of files in both folders
###################################################################################

echo "This tool has been moved under the tools/ci_tests/ directory, please use the updated path as this file will be removed in future versions"

#Load up some variables
#Define scripts and templates folders
scripts=$(ls -p scripts | grep -v '/$' | sed -e 's/\..*$//')
scripts_templates=$(ls -p  scripts/templates/| sed -e 's/\..*$//')

#Define EA and templates
extensionattributes=$(ls -p  extension_attributes | grep -v '/$' | sed -e 's/\..*$//')
extensionattributes_templates=$(ls -p extension_attributes/templates/| sed -e 's/\..*$//')


#Validate both the Script and the Template for the Script exist.
echo "Making sure files exist in both places in scripts and scripts/Templates"
scriptcompare=$(sdiff -bBWsw 75 <(echo "$scripts") <(echo "$scripts_templates" ))

if [ "$scriptcompare" == "" ]; then
 	echo "Script and Script Template Exist All good in the hood!"
else
	echo "Errors! occurred please correct the below"
	echo "             Scripts                 |            Templates"
	echo "_____________________________________|______________________________"      
	echo "$scriptcompare"
	echo "_____________________________________|______________________________"  
	echo "____________"
	exit 1
fi


#Valate both the EA and the Template for the EA exist.
echo "Making sure files exist in both places extension_attributes and extension_attributes/Templates"
eacompare=$(sdiff -bBWsw 75 <(echo "$extensionattributes") <(echo "$extensionattributes_templates"))
if [ "$eacompare" == "" ]; then
 	echo "EA and EA Template Exist All good in the hood!"
else
	echo "Errors! occurred please correct the below"
	echo "       Extension Attributes          |          Templates"
	echo "_____________________________________|______________________________"      
	echo "$eacompare"
	echo "_____________________________________|______________________________"  
	exit 1
fi
