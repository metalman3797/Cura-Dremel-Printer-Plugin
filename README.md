# Cura-Dremel-3D20-Plugin
Dremel Ideabuilder 3D20 plugin for [Cura version 3.2](https://ultimaker.com/en/products/ultimaker-cura-software) or greater. This plugin enables the user to export the proprietary .g3drem files using Cura.  This code is **heavily** based upon the [cura gcode writer plugin](https://github.com/Ultimaker/Cura/tree/master/plugins/GCodeWriter).  Although the software functions reasonably well for the author, the author will not guarantee that the software won't break your 3D printer, set it on fire, or do other **really_bad_things**.  The software is supplied without warranty and the user is responsible if they use this software and bad things happen either to their person, their 3d printer, or any of their other property as a result of using this software, or the files that it creates.  Please remain near the 3D printer while using files generated by this software, and pay close attention to the 3D printer to verify that the machine is functioning properly. The software is provided as-is and any usage of this software or its output files is strictly at the user's own risk.

![The Cura GUI](/docs/GUI.PNG)

**Note:**  This version of the Cura-Dremel-3D20-Plugin will not work with Cura versions 3.1 or earlier due to changes that Ultimaker implemented in the Cura architecture.  For a version that works with Cura versions 3.0 or 3.1, please check out version 0.2.5 of the plugin [here](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases/tag/0.2.5)

---
# Installation
To install, follow the instructions below:

0.  [Download and install Cura](https://ultimaker.com/en/products/ultimaker-cura-software) on your machine.  This plugin has been tested on Windows 10 Professional 64 bit edition, and MacOS 10.12 (Sierra), but this plugin should work equally well on linux or any other operating system that Cura supports.

1.  Download the plugin files by peforming one of the two actions:

    EITHER
    1. clone the repository onto your machine using the following command
    ```
    git clone https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin.git
    ```

    OR

    2.  Navigate to the ["Releases"](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases/latest) page to download the latest released version in zip format and extract the zip file to your computer

2.  Navigate to the folder where you downloaded or extracted the plugin

### Easy Windows Installation Instructions
Edit the [install_on_windows.bat](install_on_windows.bat) batch file by changing two Lines

change the line that reads:
`set DOWNLOADED_PLUGIN_DIR=C:\Users\timsc\Documents\Cura-Dremel-3D20-Plugin`
to point to the directory where the Cura-Dremel-3D20-Plugin was unzipped

and change the line that reads:
`set CURA_EXE_DIR=C:\Program Files\Ultimaker Cura`
to point to the directory where Cura was installed

![edit batch file](/docs/edit_batch_file.png)

then, right click on the install_on_windows.bat and select "Run As Administrator" (if Cura was installed to C:\Program Files\ this step is necessary because the "Program Files" director requires administrative access to create directories within it)  If Cura was installed to an alternate location the administrative access may not be necessary.  If the console window reads `***Plugin Successfully Installed!` then skip to step 7, otherwise follow the instructions below to manually install the plugin.

### Easy MacOS Installation Instructions:
If you haven't done so after installing Cura, launch Cura and close it.  This ensures that MacOS's security features won't think that Cura is corrupted when the plugin is installed.

Open a MacOS Terminal and run the following commands:
`cd <Extracted Plugin Directory>`  where <Extracted Plugin Directory> is the directory where you extracted the Dremel Plugin.  The easiest way to do this is to type `cd` followed by a space into the terminal window then drag the Cura-Dremel-Plugin folder onto the terminal.  Press the enter key

Type 'chmod 755 install_on_mac.sh' followed by the enter key into the terminal window.  This will give the appropriate permissions to allow you to run the installation description

Type `./install_on_mac.sh` this will run the installation script and copy the files to the appropriate locations.

If successful, you should see the test `***Plugin Successfully installed` then skip to step 7 below. If any error messages appear, follow the manual installation instructions below

![Install On Mac](/docs/install_on_mac.png)

### Easy Linux Installation Instructions (with thanks to [SwapFaceL](https://github.com/SwapFaceL) for their help):
If you haven't done so after installing Cura, open a terminal window and type the following in:
Then type `chmod a+x Cura-<cura version>.AppImage`
replacing the <cura version> with the appropriate version of cura that was downloaded.
Then launch Cura and close it.  This ensures that the files within ~/.local/share/cura/<%CURA VERSION%>/ are created.

Open a terminal window and type the following in:
`cd <Extracted Plugin Directory>`  where <Extracted Plugin Directory> is the directory where you extracted the Dremel Plugin.  The easiest way to do this is to type `cd` followed by a space into the terminal window then drag the Cura-Dremel-Plugin folder onto the terminal.  Press the enter key.

Type `chmod 755 install_on_linux.sh` followed by the enter key into the terminal window.  This will give the appropriate permissions to allow you to run the installation description.

Edit the [install_on_linux.bat](install_on_linux.bat) batch file by changing two lines indicated at the top of the script to point to the appropriate locations:
```
# modify this folder to point to the location where the Dremel plugin was downloaded
downloaded_plugin="~/Desktop/Cura-Dremel-3D20-Plugin"

# This should only need the version number changed
cura_local="~/.local/share/cura/3.2/"
```

Then run the script by typing the following command into the command prompt:
`./install_on_linux.sh`

If any error messages appear, follow the manual installation instructions below

###  Manual Installation:

3.  Install the main plugin that enables Cura to export .g3drem files by following the instructions below:

    EITHER

    3a. Install the DremelGCodeWriter.umplugin located at `Cura-Dremel-3D20-Plugin\plugins\DremelGCodeWriter.umplugin` using Cura's plugin install interface (Cura Menu->Plugins->Install Plugin)  **Note:**  On Windows this method installs the plugin to `%OS_USER_DIR%\AppData\Roaming\cura\%CURA VERSION%\plugins`.  For Operating System specific directories of where Cura installs plugins please see [this page](https://github.com/Ultimaker/Cura/wiki/Cura-Preferences-and-Settings-Locations)

    OR

    3b. Copy the plugins/DremelGCodeWriter folder into your `%CURA_DIR%/plugins` folder.  On MacOS this is located at `Ultimaker Cura.app/Contents/Resources/plugins/plugins/`  The easiest way on the mac to get to this folder is to right click on the Ultimaker Cura.app application and select the "show package contents" option.

    ![Copy the contents of DremelOutputDevice to the plugin directory of cura](/docs/plugindir.PNG)

4.   Copy the resources/definitions/Dremel3D20.def.json file into the `%CURA_DIR%/resources/definitions` folder.  This file contains the printer bed size, along with other Ideabuilder 3D20 specific settings. On MacOS this folder is located at `Ultimaker Cura.app/Contents/Resources/resources/definitions/`  The easiest way on the mac to get to this folder is to right click on the Ultimaker Cura.app application and select the "show package contents" option
![Copy the contents of Dremel printer json file to the definitions directory of cura](/docs/dremelresource.PNG)

5.  Copy the resources/meshes/dremel_3D20_platform.stl to the `%CURA_DIR%/resources/meshes` folder.  This file contains the 3D model of the Dremel Ideabuilder print bed.  On MacOS this is folder located at `Ultimaker Cura.app/Contents/Resources/resources/meshes/`  The easiest way on the mac to get to this folder is to right click on the Ultimaker Cura.app application and select the "show package contents" option
![Copy the contents of Dremel print bed file to the meshes directory of cura](/docs/meshesdir.png)

6.  Copy the resources/materials/dremel_pla.xml.fdm_material to the `%CURA_DIR%/resources/materials` folder.   This file contains the Dremel brand PLA material settings.  On MacOS this folder is located at `Ultimaker Cura.app/Contents/Resources/resources/materials/`  The easiest way on the mac to get to this folder is to right click on the Ultimaker Cura.app application and select the "show package contents" option
![Copy the contents of Dremel PLA material to the materials directory of cura](/docs/material.png)    

7.  Congratulations - the plugin is now installed!
---
# Uninstallation
To uninstall, simply close Cura and delete the files listed in the "manual installation" step above.  

**Note:**  If you installed using the .umplugin file, then Cura copies the plugin files to the plugins directory here: `%OS_USER_DIR%\AppData\Roaming\cura\%CURA VERSION%\plugins` as
specified on [this page](https://github.com/Ultimaker/Cura/wiki/Cura-Preferences-and-Settings-Locations)  Simply navigate to the plugins directory there, and delete the DremelGCodeWriter folder.  

---
# Usage
Once the plugin has been installed you can use it by following the steps outlined below:
1. open Cura
2. (Skip if Step 4 above was not performed) select the Dremel 3D20 as your printer (cura->preferences->printers->add)
![Select the Dremel 3D20](/docs/addprinter.png)

3. Select Dremel PLA (if step 6 above was performed) or any other PLA filament (if step 6 was not performed, or if other PLA settings are preferred) as your filament type
![Select the Dremel pla](/docs/selectpla.png)

4. Set the slicing options that you want.

5. <a name="Step5"></a>(Optional, but recommended if using the screenshot feature outlined in the [Preview Image Options](#Preview_Image_Options) section below) Zoom in on the part until it fills the screen.  As the plugin saves out the .g3drem file it will grab a screenshot of the main cura window for use as the preview image that is displayed on the Ideabuilder screen. The area inside the red box shown in the image below will be used in the screenshot (the red box will not appear in the actual cura window when you use the plugin).  **Please Note:** The preview on the Dremel will be **much** better if you zoom in on the part that you're printing until the part fills the screenshot area.

For instance:
![Zoom in on the part](/docs/Zoom_For_Screenshot.PNG)

Will show this on the IdeaBuilder 3D20:
![Ideabuilder Screen](docs/Ideabuilder_screen.jpg)

**Nifty Feature:** The screenshot will work with the visualizer plugins, so feel free to try the "xray view" or "layer view" options if you like those visualizations better.

6. Click "File->Save As", or "save to file", selecting .g3drem as the output file format.

![Save as .g3drem file](/docs/saveas.PNG)

7. Save this file to a SD card
8. Insert the SD card into your IdeaBuilder 3D20
9. Turn on the printer
10. Select the appropriate file to print.  
    **New - [Version 0.3 and above](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases/latest):** The plugin now can implements the logic outlined in the [Preview Image Options](#Preview_Image_Options) section below to select a preview image on the Dremel screen.
11. Click print
12. Enjoy - if you have any feature suggestions or encounter issues, feel free to raise them in the ["Issues" section](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues).
---
# <a name="Preview_Image_Options"></a>Preview Image Options
The plugin has implemented the following logic for selecting a preview image that will show up on the Dremel screen:

1. The plugin searches the directory where the user saves the .g3drem file for an image file with the same name.  Valid image extensions are .png, .jpg, .jpeg, .gif, and .bmp.  For example if the user saves llama.g3drem to the dekstop and the desktop folder has a llama.jpg image file within it then the llama.jpg file will be used as the preview image on the Dremel:
![llama preview](/docs/llama.png)

2.  If no image file with the same name is found in the same directory, then the plugin attempts to take a screenshot of the main Cura window as it saves out the file (see [Step 5 above](#Step5))

3.  If the screenshot fails then a generic Cura icon  will be shown on the Dremel IdeaBuilder screen as the preview.

![cura icon](https://github.com/Ultimaker/Cura/blob/master/icons/cura-64.png)
---
# Note
Please note the following:
* This plugin has been tested using Cura 3.2.1 on Windows 10 x64, MacOS Sierra (MacOS 10.12), MacOS El Capitan (10.11), and Ubuntu versions 17.10 and 16.04.  If you are using another platform and encounter issues with the plugin, feel free to raise an issue with the ["Issues" section](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues) above.
* With many thanks to [metalman3797](https://github.com/metalman3797) the Dremel 3D20 printer json definition has had an optimization pass - it should work even better now than it did before!
  * While this plugin works in the basic print case, you may still encounter problems with the print head crashing into your parts if you attempt to print multiple parts on the same print bed one-after-another instead of printing them all-at-once.
* The .g3drem file format is not fully understood yet - I've done a bit of reverse engineering on the file format, as described here: http://forums.reprap.org/read.php?263,785652 and have used the information I discovered to create this plugin, however there are still magic numbers in the Dremel header that may or may not have an effect on the print.  See more information in the [Technical Details below](#Technical_Details).
---
# Wishlist
The following items would be great to add to this plugin - any and all collaboration is welcome - feel free to raise an issue if there's a feature you'd like
* Optimized print profiles for IdeaBuilder 3D20 (current non-custom profiles are pretty generic and may not work as well on the Dremel as they could)
* ~~Optimized [Dremel3D20.def.json](resources/definitions/Dremel3D20.def.json) file~~ **New - [Version 0.3 and above](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases/latest):** Thanks to  [metalman3797](https://github.com/metalman3797) the Dremel json file has been further improved
* ~~Optimization of Dremel brand PLA settings~~  **New - [Version 0.3 and above](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases/latest):** Thanks to  [metalman3797](https://github.com/metalman3797) the Dremel brand PLA material has been optimized.
* Better understanding of the remaining unknown items in the Dremel .g3drem file format
* Creation of plugin container with Dremel printer json, material json, and printer bed mesh to ease user installation
---
# <a name="Technical_Details"></a>Technical Details of the .g3drem File Format
The g3drem file format consists of a few sections.  The header is a mix of binary data and ASCII data, which is followed by an 80x60 pixel bitmap image written to the file, which is then followed by standard 3d printer gcode saved in ASCII format.

**An Example of the binary header looks like this:**

![File Header](/docs/FileHeader.JPG)

A description of the current understanding of this file format is below:

| Binary Data                                     | Description                                  |
|-------------------------------------------------|----------------------------------------------|
`67 33 64 72 65 6d 20 31 2e 30 20 20 20 20 20 20` | Ascii for 'g3drem 1.0      ' (see 1 below )  |
`3a 00 00 00 b0 38 00 00 b0 38 00 00 38 04 00 00` | Magic #s and Time(sec) (See 2 and 3 below )  |
`8f 04 00 00 00 00 00 00 01 00 00 00 19 00 03 00` | Filament(mm), Magic #s (See 4, 5, 6 and 7 )  |
`64 00 00 00 DC 00 00 00 01 ff [80x60 Bmp image]` | Magic #s and BMP image (See 8, 9, 10, 11  )  |
`[standard 3d printer gcode]`                     | Gcode in ASCII         (See 12 below      )  |

**The sections of the file are:**
1. `67 33 64 72 65 6d 20 31 2e 30 20 20 20 20 20 20` = ASCII text 'g3drem 1.0      '
2. `3a 00 00 00 b0 38 00 00 b0 38 00 00` = Some magic numbers that seem to be the same for every file
3. `38 04 00 00` = four-byte little-endian integer representing the number of seconds that the print will take
4. `8f 04 00 00` = four-byte little-endian integer representing the estimated number of millimeters of filament that the print will use
5. `00 00 00 00 01 00 00 00` = Two four-byte magic numbers that seem to be the same for every file
6. `19 00` = A two-byte number that is different in some files that I've downloaded, but seem to remain the same on all files that I've generated with both the Dremel 3D and Simplify 3D software that I have, and doesn't have an obvious effect on the print.
7. `03 00` = A two-byte magic number that always seems to be the same
8. `64 00 00 00` = Two two-byte, or one four-byte number that is different in some files that I've downloaded, but seem to remain the same on all files that I've generated with both the Dremel 3D and Simplify 3D software that I have, and doesn't have an obvious effect on the print. **Note**, the last two bytes seem to be zeros in all files I've encountered.
9. `DC 00 00 00` = Two two-byte, or one four-byte number that is different in some files that I've downloaded, but seem to remain the same on all files that I've generated with both the Dremel 3D and Simplify 3D software that I have, and doesn't have an obvious effect on the print. **Note**, the last two bytes seem to be zeros in all files I've encountered.
10. `01 ff` = Another magic numbers that don't seem to change across files, and seems to indicate the end of the header
11. An 80x60 bitmap containing the image that the Dremel 3D20 will use to display on the screen (See the usage instructions [step 5](#Step5))
12. Standard 3d printer gcode (Marlin flavor seems to be working, but if you encounter issues please feel free to raise them [here](https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues)

**Interesting observations about the file format:**
1.  The maximum number of minutes that the Dremel can read is 0xFFFFFF00, which comes out to 4660 hours and 20 minutes
2.  The maximum fiament length that the file can handle is hex 0xFFFFFFFF, or 4,294,967,295 millimeters. The [Dremel 3D software](https://dremel3d.at/pages/software) reports this value as (after some rounding): 4,294,967.5 meters
3.  The image size seems to be hardcoded inside the Dremel firmware (at least for firmware 1.3.20160621).  Storing an image that is larger than 80x60 is allowable in the file, and the Windows-based ["Dremel 3D" software](https://dremel3d.at/pages/software) will read this file with a larger image with no problem.  The Dremel 3D sofware will read and show the correct part to build, but loading this file with the larger image into the actual Ideabuilder will result in the ideabuilder successfully showing the image, and allowing the user to select it, but will result in the IdeaBuilder rebooting when the user tries to print the file.
---
# Contributors:
Many thanks belong to the following users, who have spent their time and energy to report issues and help make the plugin better:
* [WeavingColors](https://github.com/WeavingColors)
* [SwapFaceL](https://github.com/SwapFaceL)
* [metalman3797](https://github.com/metalman3797)
