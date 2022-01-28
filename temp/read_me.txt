Compatible with CURA 3.6

Version 2.0 instructions - Charles Jackson 2019
****No liability for incorrect installation or damage to your Robox Printeris provided ****

1) Copy fdmprinter.def.json, CEL_Robox.def.json into C:\Program Files\Ultimaker Cura 3.6\resources\definitions
2) Copy CEL_Robox_Extruder_1.def.json & CEL_Robox_Extruder_2.def.json into C:\Program Files\Ultimaker Cura 3.6\resources\extruders
3) Copy Robox.stl into C:\Program Files\Ultimaker Cura 3.6\resources\meshes
4) Copy _RoboxPostProcess.py to C:\Program Files\Ultimaker Cura 3.6\plugins\PostProcessingPlugin\scripts
5) Start CURA 3.6 - if its the first time running cura then when launched just add an ultimaker printer then quit and restart Cura 3.6
6) Select Settings->Printer->Manage Printers
7) Click Add
8) Click Other to expand the list of other printer types
9) Select CEL Robox from list
10) Click on CEL Robox in the list of local printers and click Machine Settings
11) Check Printer settings are as per Printer.jpg & Extruder.jpg for the Printer and both Extruders
12) Click Settins->Profile-> Manage Profiles and click import 
13) Select "Robox_Dual_Get_started.curaprofile"
14) Select "Robox_Dual_Get_started" in the Custom Profiles list.  In the CURA settings make sure Relative Extrusion is set.. this is very important.
15) Select Extensions->Post Processing->Modify Gcode.  Click 'Add a Script' and then select the Dual Head and check the 'Close valves on Retract check box'
16) Start using Cura,  add a model and slice :-)
17) Save the gcode file then launch automaker and within the maintenance section, select transfer and execute gcode file, navigate to your CURA file you just saved and select it
18) the print should start - on the first print keep an eye on things to ensure the needle valves are operating correctly.

Report any issues on the Unoffical CEL Facebook group and I will try and answer / provide suppport






