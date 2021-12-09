#!/bin/bash
chartpath=$1 
chartname=$2 
if [ -z $chartpath ] || [ -z $chartname ]; then
	echo "Usage: ./chart_create.sh chartpath chartname"
        echo " chartpath: the path of the helm chart directory that will be used as template, i.e. protegochart/"
	echo " chartname: the name of the new chart"
	echo ""
	echo "Please run again with the corresponding parameters"
	exit 1
fi 
helm create $chartname 
cp $chartpath/values.yaml $chartname/ 
cp $chartpath/app-readme.md $chartname/ 
cp $chartpath/questions.yml $chartname/ 
rm $chartname/templates/*.yaml 
rm $chartname/templates/NOTES.txt 
rm -rf $chartname/templates/tests
cp $chartpath/templates/protegoapp.yaml $chartname/templates/
