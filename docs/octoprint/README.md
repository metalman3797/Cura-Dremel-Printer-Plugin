#How to Enable Octoprint for the Dremel 3D20

This page will walk you through how to set up an Octoprint enabled Dremel 3D20.

***Note*** this is for advanced users who know what they're doing.  This configuration is not officially supported by the Dremel 3D20 plugin author.  If you break your machine by modifying the plugin files then ***Do NOT*** try to upgrade the firmware on the printer using the button in Cura. You may ***permanently damage*** your printer if you do so.  As always - remain by your printer while it's printing.  

# Requirements
1.  Raspberry Pi
2.  MicroSD card for the Pi
3.  Wifi dongle for the Pi (if the Pi doesn't have built-in wifi)
3.  Dremel 3D20
4.  USB Type A to Type B cable (the type that comes with printers)

# Instructions
1.  Install the latest version of octoprint onto the SD card following the instructions [here](https://octoprint.org/download/).  Be sure to edit the `octopi-wpa-supplicant.txt` using an appropriate text editor (see notes on the link for which text editors are approved)
2.  Insert the SD card into the raspberry pi & boot it
3.  SSH into the pi and change the password
4.  Go to `http://<your printer ip>` or `http://octopi.local`
5.  Click the gear (settings) icon in the upper right corner
6.  Find "plugin manager" and at the bottom of the list of installed plugins click "Get More"
7.  Locate the "Flashforge/Dremel/PowerSpec Printer Support" plugin and install it
8.  Connect the usb A->B cable between the raspberry pi and the Dremel 3D20
9.  Launch Cura
10.  Install the Dremel Plugin & the "Octoprint Connection" plugin & reboot Cura
11.  Close Cura again & navigate to the directory where the 3D20 definition is installed (replacing `<cura version>` with the appropriate version number, i.e. `4.8`)
```
    Windows:  %APPDATA%\cura\<cura version>\definitions\Dremel3D20.def.json
    Linux:  ~/.local/share/cura/<cura version>/definitions/Dremel3D20.def.json
    Mac:  ~/Library/Application\ Support/Cura/<cura version>/definitions/Dremel3D20.def.json
```
12.  Open this file in a text editor.
13.  Locate the line that reads `"supports_usb_connection": false,` and change it to `"supports_usb_connection": true,`
14.  Save & close the Dremel3D20.def.json
15.  Open Cura again
16.  Add a Dremel 3D20 printer to Cura - now you should see a button to "connect octoprint"  press it.
17.  Follow the [instructions here](https://all3dp.com/2/cura-octoprint-plugin-connection/) to get the API key 7 connect cura to Octoprint
18.  Enjoy

***Note*** When Dremel plugin updates are installed, the update will overwrite the modified printer definition & you will have to re-modify the definition file after installing the update.

***Note*** If you encouter errors when modifying the Dremel definition file, the original file will be re-installed by the plugin if you delete the modified copy and restart cura.
