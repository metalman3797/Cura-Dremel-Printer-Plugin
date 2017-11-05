# Cura-Dremel-3D20-Plugin
Dremel Ideabuilder 3d20 plugin for Cura 3.x

#Installation
To install, simply clone the repository onto your machine, then copy the plugins/DremelGCodeWriter folder into your <cura install>/plugins folder.  Then copy the resources/definitions/Dremel3D20.def.json file into the <cura install>/resources/definitions folder and you're set.

#Usage
Once installed, open cura, select the Dremel 3D20 as your printer (cura->preferences->printers->add), slice the print with the options you want, then save to file, selecting .g3drem as the output file format.  Save this file to a SD card, insert the SD card into your IdeaBuilder 3D20, and print.

Enjoy!

#Note
Please note that the Dremel 3D20 printer file json has not been completely optimized.  While it works in the basic print case, you may encounter problems if you attempt to print multiple parts on the same print bed one-after-another instead of all-at-once.  
