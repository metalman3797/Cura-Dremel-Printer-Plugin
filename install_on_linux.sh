#!/bin/bash

# The user should change the directories of the two items below
# modify this folder to point to the location where the dremel plugin was downloaded
downloaded_plugin="~/Desktop/Cura-Dremel-3D20-Plugin"

# This should only need the version number changed
cura_local="~/.local/share/cura/3.2/"

#########################################################
####    Don't modify anything below this line
#########################################################
downloaded_plugin_dir=${downloaded_plugin/\~/$HOME}
cura_local_dir=${cura_local/\~/$HOME}

if [ ! -d $downloaded_pluing_dir ]
then 
  echo "Could not find plugin in downloaded_plugin_dir please edit script to point to directory where cura was installed"
  exit -1
fi

if [ ! -d $cura_local_dir ]
then 
  echo "Could not find ~/.local/share/cura/<version> folder...please launch Cura first and then set script directory correctly"
fi

if [ ! -d $cura_local_dir/plugins/DremelGCodeWriter ]
then
  mkdir $cura_local_dir/plugins/DremelGCodeWriter
fi

if [ ! -d $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter ]
then 
  mkdir $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter
fi

cp -r $downloaded_plugin_dir/plugins/DremelGCodeWriter $cura_local_dir/plugins/DremelGCodeWriter/
cp -r $downloaded_plugin_dir/resources/definitions/. $cura_local_dir/definitions/
cp -r $downloaded_plugin_dir/resources/materials/. $cura_local_dir/materials/
cp -r $downloaded_plugin_dir/resources/quality/dremel_3d20 $cura_local_dir/quality

if [ -f $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter/DremelGCodeWriter.py ] 
then 
  echo "****************************************"
  echo "*****Plugin successfully installed******"
  echo "****************************************"
else
  echo "****************************************"
  echo "**Errors encountered installing plugin**"
  echo "****************************************"
fi
