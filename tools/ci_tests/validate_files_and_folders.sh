#!/bin/bash
###################################################################################
## Looks for the existance of files in both folders
###################################################################################

#Load up some variables
#Define scripts and templates folders
scripts=$(ls -1 scripts | grep -v "templates")
scripts_templates=$(ls -1 scripts/templates/)

#Define EA and templates
extensionattributes=$(ls -1  extension_attributes | grep -v "templates")
extensionattributes_templates=$(ls -1 extension_attributes/templates/)


#Validate both the Script and the Template for the Script exist.
echo "Making sure files with same names exist in both places in scripts and scripts/Templates"
scriptcompare=$(sdiff -bBWsw 75 <(echo "$scripts") <(echo "$scripts_templates" ))

if [ "$scriptcompare" == "" ]; then
 	echo "Script and Script Template Exist in both folders!"
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
echo "Making sure files with same names exist in both places extension_attributes and extension_attributes/Templates"
eacompare=$(sdiff -bBWsw 75 <(echo "$extensionattributes") <(echo "$extensionattributes_templates"))
if [ "$eacompare" == "" ]; then
 	echo "EA and EA Template Exist in both folders!"
else
	echo "Errors! occurred please correct the below"
	echo "       Extension Attributes          |          Templates"
	echo "_____________________________________|______________________________"      
	echo "$eacompare"
	echo "_____________________________________|______________________________"  
	exit 1
fi
