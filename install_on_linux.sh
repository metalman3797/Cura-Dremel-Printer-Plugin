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

cp $downloaded_plugin_dir/plugins/DremelGCodeWriter/DremelGCodeWriter.py $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter/
cp $downloaded_plugin_dir/plugins/DremelGCodeWriter/__init__.py $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter/
cp $downloaded_plugin_dir/plugins/DremelGCodeWriter/plugin.json $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter/

cp $downloaded_plugin_dir/resources/definitions/Dremel3D20.def.json $cura_local_dir/definitions/
cp $downloaded_plugin_dir/resources/materials/dremel_pla.xml.fdm_material $cura_local_dir/materials/

if [ -f $cura_local_dir/plugins/DremelGCodeWriter/DremelGCodeWriter/DremelGCodeWriter.py ] 
then 
  echo "***Plugin successfully installed"
else
  echo "***Errors encountered installing plugin"
fi
