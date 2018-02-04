#!/bin/bash
CuraDir=/Applications/Ultimaker\ Cura.app
PluginDir=.

if [ -d "${CuraDir}" ] ; then
	echo "Cura Found installing plguin"
	cp -r "$PluginDir"/plugins/DremelGCodeWriter "$CuraDir"/Contents/Resources/plugins/plugins/
	cp -a "$PluginDir"/resources/definitions/. "$CuraDir"/Contents/Resources/resources/definitions/
	cp -a "$PluginDir"/resources/materials/. "$CuraDir"/Contents/Resources/resources/materials/
	cp -a "$PluginDir"/resources/meshes/. "$CuraDir"/Contents/Resources/resources/meshes/
	echo "***Plugin Successfully Installed"
else
	echo "Cura Not Found"
fi
sleep 10

