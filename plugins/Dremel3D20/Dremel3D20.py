####################################################################
# Dremel Ideabuilder 3D20 plugin for Ultimaker Cura
# A plugin to enable Cura to write .g3drem files for
# the Dremel IdeaBuilder 3D20
#
# Written by Tim Schoenmackers
# Based on the GcodeWriter plugin written by Ultimaker
#
# the GcodeWriter plugin source can be found here:
# https://github.com/Ultimaker/Cura/tree/master/plugins/GCodeWriter
#
# This plugin is released under the terms of the LGPLv3 or higher.
# The full text of the LGPLv3 License can be found here:
# https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/blob/master/LICENSE
####################################################################

import os # for listdir
import platform # for platform.system
import os.path  # for isfile and join and path
import sys
import zipfile  # For unzipping the printer files
import shutil   # For deleting plugin directories
import stat     # For setting file permissions correctly
import re       # For escaping characters in the settings.
import json
import copy
import struct
import time

from distutils.version import StrictVersion # for upgrade installations

from UM.i18n import i18nCatalog
from UM.Extension import Extension
from UM.Message import Message
from UM.Resources import Resources
from UM.Logger import Logger
from UM.Preferences import Preferences
from UM.Mesh.MeshWriter import MeshWriter
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Qt.Duration import DurationFormat
from UM.Qt.Bindings.Theme import Theme
from UM.PluginRegistry import PluginRegistry

from UM.Application import Application
from UM.Settings.InstanceContainer import InstanceContainer
from cura.Machines.ContainerTree import ContainerTree

from cura.Utils.Threading import call_on_qt_thread

from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPixmap, QScreen, QColor, qRgb, QImageReader, QImage, QDesktopServices
from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt, QSize, pyqtSlot, QObject, QUrl, pyqtSlot
from cura.Snapshot import Snapshot

from . import G3DremHeader

catalog = i18nCatalog("cura")


class Dremel3D20(QObject, MeshWriter, Extension):
    # The version number of this plugin - please change this in all three of the following Locations:
    # 1) here
    # 2) plugin.json
    # 3) package.json
    version = "0.6.5"

    ######################################################################
    ##  Dictionary that defines how characters are escaped when embedded in
    #   g-code.
    #
    #   Note that the keys of this dictionary are regex strings. The values are
    #   not.
    ######################################################################
    escape_characters = {
        re.escape("\\"): "\\\\",  # The escape character.
        re.escape("\n"): "\\n",   # Newlines. They break off the comment.
        re.escape("\r"): "\\r"    # Carriage return. Windows users may need this for visualisation in their editors.
    }

    _setting_keyword = ";SETTING_"

    def __init__(self):
        super().__init__(add_to_recent_files = False)
        self._application = Application.getInstance()

        if self._application.getPreferences().getValue("Dremel3D20/curr_version") is None:
            self._application.getPreferences().addPreference("Dremel3D20/curr_version","0.0.0")

        self.this_plugin_path=os.path.join(Resources.getStoragePath(Resources.Resources), "plugins","Dremel3D20","Dremel3D20")

        if self._application.getPreferences().getValue("Dremel3D20/select_screenshot") is None:
            self._application.getPreferences().addPreference("Dremel3D20/select_screenshot", False)

        if self._application.getPreferences().getValue("Dremel3D20/last_screenshot_folder") is None:
            self._application.getPreferences().addPreference("Dremel3D20/last_screenshot_folder",str(os.path.expanduser('~')))
        Logger.log("i", "Dremel3D20 Plugin adding menu item for screenshot toggling")

        self._preferences_window = None
        self._snapshot = None
        self.local_meshes_path = None
        self.local_printer_def_path = None
        self.local_materials_path = None
        self.local_quality_path = None
        self.local_extruder_path = None

        Logger.log("i", "Dremel 3D20 Plugin setting up")
        self.local_meshes_path = os.path.join(Resources.getStoragePathForType(Resources.Resources), "meshes")
        self.local_printer_def_path = Resources.getStoragePath(Resources.DefinitionContainers)
        self.local_materials_path = os.path.join(Resources.getStoragePath(Resources.Resources), "materials")
        self.local_quality_path = os.path.join(Resources.getStoragePath(Resources.Resources), "quality")
        self.local_extruder_path = os.path.join(Resources.getStoragePath(Resources.Resources),"extruders")

        # if the plugin was never installed, then force installation
        if self._application.getPreferences().getValue("Dremel3D20/install_status") is None:
            Logger.log("i","Dremel 3D20 Plugin can't find the install_status preference")
            self._application.getPreferences().addPreference("Dremel3D20/install_status", "unknown")
        else:
            Logger.log("i","Dremel 3D20 Plugin install_status="+str(self._application.getPreferences().getValue("Dremel3D20/install_status")))

        # if something got messed up, force installation
        if not self.isInstalled() and self._application.getPreferences().getValue("Dremel3D20/install_status") == "installed":
            Logger.log("i","Dremel 3D20 Plugin detected that plugin should be installed but isn't")
            self._application.getPreferences().setValue("Dremel3D20/install_status", "unknown")

        # if it's installed, and it's listed as uninstalled, then change that to reflect the truth
        if self.isInstalled() and self._application.getPreferences().getValue("Dremel3D20/install_status") == "uninstalled":
            self._application.getPreferences().setValue("Dremel3D20/install_status", "installed")

        # if the version isn't the same, then force installation
        if self.isInstalled() and not self.versionsMatch():
            Logger.log("i","Dremel 3D20 Plugin detected that plugin needs to be upgraded")
            self._application.getPreferences().setValue("Dremel3D20/install_status", "unknown")

        # Check the preferences to see if the user uninstalled the files -
        # if so don't automatically install them
        if self._application.getPreferences().getValue("Dremel3D20/install_status") == "unknown":
            # if the user never installed the files, then automatically install it
            Logger.log("i","Dremel 3D20 Plugin now calling install function")
            self.installPluginFiles()

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Preferences"), self.showPreferences)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Report Issue"), self.reportIssue)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Help "), self.showHelp)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Dremel Printer Plugin Version "+Dremel3D20.version), self.openPluginWebsite)

        # finally save the cura.cfg file
        self._application.getPreferences().writeToFile(Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))

    ######################################################################
    ## Taking snapshot needs to be called on QT thread
    ## see this function for more info
    ## https://github.com/Ultimaker/Cura/blob/bcf180985d8503245822d420b420f826d0b2de72/plugins/CuraEngineBackend/CuraEngineBackend.py#L250-L261
    ######################################################################
    @call_on_qt_thread
    def _createSnapshot(self, w=80, h=60):
        # must be called from the main thread because of OpenGL
        Logger.log("d", "Creating thumbnail image with size (",w,",",h,")")
        self._snapshot = Snapshot.snapshot(width = w, height = h)
        Logger.log("d","Thumbnail taken")

    def createPreferencesWindow(self):
        path = os.path.join(PluginRegistry.getInstance().getPluginPath(self.getPluginId()), "Dremel3D20prefs.qml")
        Logger.log("i", "Creating Dremel3D20 preferences UI "+path)
        self._preferences_window = self._application.createQmlComponent(path, {"manager": self})

    def showPreferences(self):
        if self._preferences_window is None:
            self.createPreferencesWindow()
        self._preferences_window.show()

    def hidePreferences(self):
        if self._preferences_window is not None:
            self._preferences_window.hide()

    ######################################################################
    ##  function so that the preferences menu can open website
    ######################################################################
    @pyqtSlot()
    def openPluginWebsite(self):
        url = QUrl('https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases', QUrl.TolerantMode)
        if not QDesktopServices.openUrl(url):
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 plugin could not navigate to https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/releases"))
            message.show()
        return

    ######################################################################
    ##  Show the help
    ######################################################################
    @pyqtSlot()
    def showHelp(self):
        url = os.path.join(PluginRegistry.getInstance().getPluginPath(self.getPluginId()), "README.pdf")
        Logger.log("i", "Dremel 3D20 Plugin opening help document: "+url)
        try:
            if not QDesktopServices.openUrl(QUrl("file:///"+url, QUrl.TolerantMode)):
                message = Message(catalog.i18nc("@info:status", "Dremel 3D20 plugin could not open help document.\n Please download it from here: https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/raw/cura-3.4/README.pdf"))
                message.show()
        except:
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 plugin could not open help document.\n Please download it from here: https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/raw/cura-3.4/README.pdf"))
            message.show()
        return

    ######################################################################
    ##  Open up the Github Issues Page
    ######################################################################
    @pyqtSlot()
    def reportIssue(self):
        Logger.log("i", "Dremel 3D20 Plugin opening issue page: https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues/new")
        try:
            if not QDesktopServices.openUrl(QUrl("https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues/new")):
                message = Message(catalog.i18nc("@info:status", "Dremel 3D20 plugin could not open https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues/new please navigate to the page and report an issue"))
                message.show()
        except:
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 plugin could not open https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/issues/new please navigate to the page and report an issue"))
            message.show()
        return

    ######################################################################
    ## returns true if the versions match and false if they don't
    ######################################################################
    def versionsMatch(self):
        # get the currently installed plugin version number
        if self._application.getPreferences().getValue("Dremel3D20/curr_version") is None:
            self._application.getPreferences().addPreference("Dremel3D20/curr_version", "0.0.0")

        installedVersion = self._application.getPreferences().getValue("Dremel3D20/curr_version")

        if StrictVersion(installedVersion) == StrictVersion(Dremel3D20.version):
            # if the version numbers match, then return true
            Logger.log("i", "Dremel 3D20 Plugin versions match: "+installedVersion+" matches "+Dremel3D20.version)
            return True
        else:
            Logger.log("i", "Dremel 3D20 Plugin installed version: " +installedVersion+ " doesn't match this version: "+Dremel3D20.version)
            return False


    ######################################################################
    ## Check to see if the plugin files are all installed
    ## Return True if all files are installed, false if they are not
    ######################################################################
    def isInstalled(self):
        dremel3D20DefFile = os.path.join(self.local_printer_def_path,"Dremel3D20.def.json")
        dremelExtruderDefFile = os.path.join(self.local_extruder_path,"dremel_3d20_extruder_0.def.json")
        dremelPLAfile = os.path.join(self.local_materials_path,"dremel_pla.xml.fdm_material")
        dremeloldPLAfile = os.path.join(self.local_materials_path,"dremel_pla_0.5kg.xml.fdm_material")
        dremelQualityDir = os.path.join(self.local_quality_path,"dremel_3d20")

        # if some files are missing then return that this plugin as not installed
        if not os.path.isfile(dremel3D20DefFile):
            Logger.log("i", "Dremel 3D20 Plugin dremel definition file is NOT installed ")
            return False
        if not os.path.isfile(dremelExtruderDefFile):
            Logger.log("i", "Dremel 3D20 Plugin dremel extruder file is NOT installed ")
            return False
        if not os.path.isfile(dremelPLAfile):
            Logger.log("i", "Dremel 3D20 Plugin dremel PLA file is NOT installed ")
            return False
        if not os.path.isfile(dremeloldPLAfile):
            Logger.log("i", "Dremel 3D20 Plugin dremel 0.5kg PLA file is NOT installed ")
            return False
        if not os.path.isdir(dremelQualityDir):
            Logger.log("i", "Dremel 3D20 Plugin dremel quality files are NOT installed ")
            return False

        # if everything is there, return True
        Logger.log("i", "Dremel 3D20 Plugin all files ARE installed")
        return True

    # install based on preference checkbox
    @pyqtSlot(bool)
    def changePluginInstallStatus(self, bInstallFiles):
        if bInstallFiles and not self.isInstalled():
            self.installPluginFiles()
        elif not bInstallFiles and self.isInstalled():
            self.uninstallPluginFiles()


    ######################################################################
    ## Install the plugin files from the included zip file.
    ######################################################################
    def installPluginFiles(self):
        Logger.log("i", "Dremel 3D20 Plugin installing printer files")

        try:
            restartRequired = False
            zipdata = os.path.join(self.this_plugin_path,"Dremel3D20.zip")
            #zipdata = os.path.join(self._application.getPluginRegistry().getPluginPath(self.getPluginId()), "Dremel3D20.zip")
            Logger.log("i", "Dremel 3D20 Plugin: found zipfile: " + zipdata)
            with zipfile.ZipFile(zipdata, "r") as zip_ref:
                for info in zip_ref.infolist():
                    Logger.log("i", "Dremel 3D20 Plugin: found in zipfile: " + info.filename )
                    folder = None
                    if info.filename == "Dremel3D20.def.json":
                        folder = self.local_printer_def_path
                    if info.filename == "dremel_3d20_extruder_0.def.json":
                        folder = self.local_extruder_path
                    elif info.filename.endswith("fdm_material"):
                        folder = self.local_materials_path
                    elif info.filename.endswith(".cfg"):
                        folder = self.local_quality_path
                    elif info.filename.endswith(".stl"):
                        folder = self.local_meshes_path
                        # Cura didn't always create the meshes folder by itself.
                        # We may have to manually create it if it doesn't exist
                        if not os.path.exists(folder):
                            os.mkdir(folder)
                    # now that we know where this file goes, extract it to the proper directory
                    if folder is not None:
                        extracted_path = zip_ref.extract(info.filename, path = folder)
                        permissions = os.stat(extracted_path).st_mode
                        os.chmod(extracted_path, permissions | stat.S_IEXEC) #Make these files executable.
                        Logger.log("i", "Dremel 3D20 Plugin installing " + info.filename + " to " + extracted_path)
                        restartRequired = True

            if restartRequired and self.isInstalled():
                # only show the message if the user called this after having already uninstalled
                if self._application.getPreferences().getValue("Dremel3D20/install_status") is not "unknown":
                    message = Message(catalog.i18nc("@info:status", "Dremel 3D20 files have been installed.  Please restart Cura to complete installation"))
                    message.show()
                # either way, the files are now installed, so set the prefrences value
                self._application.getPreferences().setValue("Dremel3D20/install_status", "installed")
                self._application.getPreferences().setValue("Dremel3D20/curr_version",Dremel3D20.version)
                Logger.log("i", "Dremel 3D20 Plugin is now installed - Please restart ")
                self._application.getPreferences().writeToFile(Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))

        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while installing the files")
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 Plugin experienced an error installing the files"))
            message.show()




    # Uninstall the plugin files.
    def uninstallPluginFiles(self):
        Logger.log("i", "Dremel 3D20 Plugin uninstalling plugin files")
        restartRequired = False
        # remove the printer definition file
        try:
            dremel3D20DefFile = os.path.join(self.local_printer_def_path,"Dremel3D20.def.json")
            if os.path.isfile(dremel3D20DefFile):
                Logger.log("i", "Dremel 3D20 Plugin removing printer definition from " + dremel3D20DefFile)
                os.remove(dremel3D20DefFile)
                restartRequired = True
        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # remove the extruder definition file
        try:
            dremel3D20ExtruderFile = os.path.join(self.local_printer_def_path,"dremel_3d20_extruder_0.def.json")
            if os.path.isfile(dremel3D20ExtruderFile):
                Logger.log("i", "Dremel 3D20 Plugin removing extruder definition from " + dremel3D20ExtruderFile)
                os.remove(dremel3D20ExtruderFile)
                restartRequired = True
        except: # Installing a new plug-in should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # remove the pla material file
        try:
            dremelPLAfile = os.path.join(self.local_materials_path,"dremel_pla.xml.fdm_material")
            if os.path.isfile(dremelPLAfile):
                Logger.log("i", "Dremel 3D20 Plugin removing dremel pla file from " + dremelPLAfile)
                os.remove(dremelPLAfile)
                restartRequired = True
        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # remove the extruder file
        try:
            dremelExtruder = os.path.join(self.local_extruder_path,"dremel_3d20_extruder_0.def.json")
            if os.path.isfile(dremelExtruder):
                Logger.log("i", "Dremel 3D20 Plugin removing dremel extruder file from " + dremelExtruder)
                os.remove(dremelExtruder)
                restartRequired = True
        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # remove the platform file (on windows this doesn't work because it needs admin rights)
        try:
            dremelSTLfile = os.path.join(self.local_meshes_path,"dremel_3D20_platform.stl")
            if os.path.isfile(dremelSTLfile):
                Logger.log("i", "Dremel 3D20 Plugin removing dremel stl file from " + dremelSTLfile)
                os.remove(dremelSTLfile)
                restartRequired = True
        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # remove the folder containing the quality files
        try:
            dremelQualityDir = os.path.join(self.local_quality_path,"dremel_3d20")
            if os.path.isdir(dremelQualityDir):
                Logger.log("i", "Dremel 3D20 Plugin removing dremel quality files from " + dremelQualityDir)
                shutil.rmtree(dremelQualityDir)
                restartRequired = True
        except: # Installing a new plugin should never crash the application.
            Logger.logException("d", "An exception occurred in Dremel 3D20 Plugin while uninstalling files")

        # prompt the user to restart
        if restartRequired:
            self._application.getPreferences().setValue("Dremel3D20/install_status", "uninstalled")
            self._application.getPreferences().writeToFile(Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 files have been uninstalled.  Please restart Cura to complete uninstallation"))
            message.show()

    ######################################################################
    ##  Updates the saved setting in the cura settings folder when the user checks the box
    ######################################################################
    @pyqtSlot(bool)
    def setSelectScreenshot(self,bManualSelectEnabled):
        if not bManualSelectEnabled:
            self._application.getPreferences().setValue("Dremel3D20/select_screenshot",False)
            Logger.log("i", "Dremel3D20 Plugin manual screenshot selection disabled")
            message = Message(catalog.i18nc("@info:status", "Manual screenshot selection is disabled when exporting g3drem files"))
            message.show()
        else:
            self._application.getPreferences().setValue("Dremel3D20/select_screenshot",True)
            Logger.log("i", "Dremel3D20 Plugin manual screenshot selection enabled")
            message = Message(catalog.i18nc("@info:status", "Manual screenshot selection is enabled when exporting g3drem files"))
            message.show()
        self._application.getPreferences().writeToFile(Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))

    ######################################################################
    ##  find_images_with_name tries to find an image file with the same name in the same direcory where the
    ##  user is writing out the g3drem file.  If it finds an image then it reuturns the filename so that the
    ##  image can be used for a preview
    ######################################################################
    def find_images_with_name(self, gcodefilename):
        # get the path where the user requested the .g3drem file save to go
        savepth, savefname = os.path.split(os.path.realpath(gcodefilename))
        # get the path+filename-extension i.e. "/usr/home/llama.g3drem" would split to "/usr/home/llama"  and ".g3drem"
        gcode_path_and_name, file_extension = os.path.splitext(os.path.realpath(gcodefilename))
        Logger.log("i", "Dremel 3D20 Plugin looking for image with name " + gcode_path_and_name +".[jpg,gif,bmp]")
        # get a list of all files in the save directory so that we can traverse over them
        allfiles = [os.path.join(savepth, f) for f in os.listdir(savepth) if os.path.isfile(os.path.join(savepth, f))]
        # search over all the files to see if we find a valid image
        for currfile in allfiles:
            # split the current file name in the same way ("/usr/home/llama.g3drem" would split to "/usr/home/llama"  and ".g3drem")
            currfile_path_and_name, currfile_extension = os.path.splitext(os.path.realpath(currfile))
            # compare the path+filename section (i.e. compare /usr/home/llama to /usr/home/camel) if they match then check to see
            # if the extension is a valid image format. and if so, return it.
            if gcode_path_and_name.lower() == currfile_path_and_name.lower():
                if currfile_extension.lower() in [".png", ".jpg",".jpeg",".gif",".bmp"]:
                    Logger.log("i", "Dremel 3D20 Plugin - using image: " + currfile.lower() )
                    return currfile
        # if no image with a matching name was found, return
        Logger.log("d", "Dremel 3D20 Plugin did not find any appropriate image files  - trying to take screenshot instead")
        return None

    # this might need to be on the main QT Thread, so do it just to be safe
    # see:
    # https://github.com/Ultimaker/Cura/blob/master/plugins/UFPWriter/UFPWriter.py
    @call_on_qt_thread
    def getBitmapBytes(self,stream):

        bmpError = False
        image_with_same_name = None
        if self._application.getPreferences().getValue("Dremel3D20/select_screenshot"):
            image_with_same_name, _ = QFileDialog.getOpenFileName(None, 'Select Preview Image', self._application.getPreferences().getValue("Dremel3D20/last_screenshot_folder"),"Image files (*png *.jpg *.gif *.bmp *.jpeg)")
            Logger.log("d", "Dremel 3D20 Plugin using image for screenshot: " + image_with_same_name)
            self._application.getPreferences().setValue("Dremel3D20/last_screenshot_folder",str(os.path.dirname(image_with_same_name)))
            # need to test this when cancel button is clicked
            if image_with_same_name == "":
                image_with_same_name = None
        else:
            image_with_same_name = self.find_images_with_name(stream.name)

        # find image with same name as saved filename
        if image_with_same_name is not None:
            try:
                pixMpImg = QImage()
                reader = QImageReader(image_with_same_name)
                reader.setScaledSize(QSize(80,60))
                if reader.canRead():
                    reader.read(pixMpImg)
                    # now prepare to write the bitmap
                    ba = QByteArray()
                    bmpData = QBuffer(ba)
                    if not bmpData.open(QIODevice.WriteOnly):
                        Logger.log("d", "Dremel 3D20 Plugin - Could not open qbuffer - using generic icon instead")
                        bmpError = True
                    if bmpData is None:
                        Logger.log("d", "Dremel 3D20 Plugin - could not copy image data into buffer - using generic icon instead")
                        bmpError = True
                    # copy the raw image data to bitmap image format in memory
                    if not bmpError and not pixMpImg.save(bmpData, "BMP"):
                        Logger.log("d", "Dremel 3D20 Plugin - Could not save pixmap - trying to take screenshot instead")
                        bmpError = True
                    # finally write the bitmap to the g3drem file
                    if not bmpError and len(ba)>0:
                        return ba
                else:
                    Logger.log("e", "Dremel 3D20 Plugin - Could not read image file - trying to grab screenshot")
            except:
                Logger.log("e", "Dremel 3D20 Plugin - Could not use pixmap - trying to grab screenshot")
        else:
            bmpError = False
            self._createSnapshot()

            # now prepare to write the bitmap
            ba = QByteArray()
            bmpData = QBuffer(ba)
            if not bmpData.open(QIODevice.WriteOnly):
                Logger.log("e", "Dremel 3D20 Plugin - Could not open qbuffer - using generic icon instead")
                bmpError = True
            if bmpData is None or self._snapshot is None:
                Logger.log("e", "Dremel 3D20 Plugin - could not copy bmp data into buffer - using generic icon instead")
                bmpError = True
            # copy the raw image data to bitmap image format in memory
            if not bmpError and not self._snapshot.save(bmpData, "BMP"):
                Logger.log("e", "Dremel 3D20 Plugin - Could not save pixmap - using generic icon instead")
                bmpError = True
            # finally write the bitmap to the g3drem file
            if not bmpError and len(ba)>0:
                return ba

        # if there was an error, then use the generic icon
        Logger.log("d", "Dremel 3D20 Plugin - using generic icon")

        # if an error ocurred when grabbing a screenshot write the generic cura icon instead
        bmpBytes = struct.pack("{}B".format(len(self.dremel3D20IconBmpData)), *self.dremel3D20IconBmpData)
        return bmpBytes

    ######################################################################
    ##  Performs the writing of the dremel header and gcode - for a technical
    ##  breakdown of the dremel g3drem file format see the following page:
    ##  https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/blob/master/README.md#technical-details-of-the-g3drem-file-format
    ######################################################################
    def write(self, stream, nodes, mode = MeshWriter.OutputMode.BinaryMode):
        try:
            if mode != MeshWriter.OutputMode.BinaryMode:
                Logger.log("e", "Dremel 3D20 Plugin does not support non-binary mode.")
                return False
            if stream is None:
                Logger.log("e", "Dremel 3D20 Plugin - Error writing - no output stream.")
                return False

            g3dremHeader = G3DremHeader.G3DremHeader()

            active_printer = self._application.getGlobalContainerStack().definition.getName()
            Logger.log("i", "Dremel Plugin - Active Printer is " + active_printer)

            global_container_stack = self._application.getGlobalContainerStack()
            print_information = self._application.getPrintInformation()
            extruders = [global_container_stack]
            extruder = extruders[0]
            # get estimated length
            length = int(print_information.materialLengths[int(extruder.getMetaDataEntry("position", "0"))]*1000)
            g3dremHeader.setMaterialLen(length)

            materialName = "PLA"
            #TODO: currently this gets the values set in the quality profile, however
            # it does not account for user quality changes
            active_machine_stack = self._application.getMachineManager().activeMachine
            if len(active_machine_stack.extruderList)>0:
                currExtruder = active_machine_stack.extruderList[0]

                # set the material
                material = currExtruder.material
                materialName = material.getName()
                Logger.log("i","Dremel Plugin - active material is: "+str(materialName))
                if "ABS" in materialName:
                    g3dremHeader.setMaterialType(G3DremHeader.MaterialType.ABS)

                # set num shell layers
                numShells = currExtruder.getProperty("wall_line_count","value")
                Logger.log("i","Dremel Plugin - num walls is: "+str(numShells))
                if numShells is  None:
                    numShells = 3
                g3dremHeader.setNumShells(int(numShells))

                currQuality = currExtruder.quality

                # set print print speed
                printSpeed = currQuality.getProperty("speed_print","value")
                Logger.log("i","Dremel3D20 Plugin - print speed is: "+str(printSpeed))
                if printSpeed is  None:
                    printSpeed = 50
                g3dremHeader.setPrintSpeed(int(printSpeed))

                # set print temperature in header
                extruderTemp = currQuality.getProperty("default_material_print_temperature","value")
                Logger.log("i","Dremel3D20 Plugin - extruder temperature is: "+str(extruderTemp))
                if extruderTemp is  None:
                    extruderTemp = 50
                g3dremHeader.setExtruderTemp(int(extruderTemp))

                # get infill percentage
                infillPct = currQuality.getProperty("infill_sparse_density","value")
                Logger.log("i","Dremel3D20 Plugin - infill percentage is: "+str(infillPct))
                if infillPct is  None:
                    infillPct = 20
                g3dremHeader.setInfillPct(int(infillPct))

                # set the bed temperature
                bedTemp = currQuality.getProperty("material_bed_temperature", "value")
                if bedTemp is None:
                    bedTemp = 60
                g3dremHeader.setBedTemperature(int(bedTemp))

            bHeatedBed = False
            bSupportEnabled = active_machine_stack.getProperty("support_enable", "value")

            # set the information flag bits
            g3dremHeader.setFlags(leftExtruderExists=False,heatedBed=bHeatedBed,supportEnabled=bSupportEnabled)

            # get the estimated number of seconds that the print will take
            seconds = int(print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))
            g3dremHeader.setEstimatedTime(seconds)

            # set layer height
            g3dremHeader.setLayerHeight(int(global_container_stack.getProperty("layer_height", "value")*1000))

            # set the thumbnail
            g3dremHeader.setThumbnailBitmap(self.getBitmapBytes(stream))

            # debugging: write bmp image out to the same directory
            #savepth, savefname = os.path.split(os.path.realpath(stream.name))
            #with open(savepth+'CapturedImage.bmp','wb') as f:
            #    f.write(self.getBitmapBytes(stream).data())
            #    f.close();

            # finally, write the header to the file
            if not g3dremHeader.writeHeader(stream):
                Logger.log("e", "Dremel3D20 Plugin - Error Writing Dremel Header.")
                return False
            Logger.log("i", "Dremel3D20 Plugin - Finished Writing Dremel Header.")

            # now that the header is written, write the ascii encoded gcode

            # write a comment in the gcode with  the Plugin name, version number, printer, and quality name to the g3drem file
            quality_name = global_container_stack.quality.getName()
            if quality_name is None:
                quality_name="unknown"

            stream.write("\n;Cura-Dremel-Plugin version {}\n;Printing on: {}\n;Using material: \"{}\"\n;Quality: \"{}\"\n".format(Dremel3D20.version,active_printer,materialName,quality_name).encode())

            # after the plugin info - write the gcode from Cura
            active_build_plate = self._application.getMultiBuildPlateModel().activeBuildPlate
            scene = self._application.getController().getScene()
            if not hasattr(scene, "gcode_dict"):
                self.setInformation(catalog.i18nc("@warning:status", "Please prepare G-code before exporting."))
                return False

            gcode_dict = getattr(scene, "gcode_dict")
            gcode_list = gcode_dict.get(active_build_plate, None)
            #Logger.log("i", "Got active build plate")
            if gcode_list is not None:
                has_settings = False
                for gcode in gcode_list:
                    try:
                        if gcode[:len(self._setting_keyword)] == self._setting_keyword:
                             has_settings = True
                        stream.write(gcode.encode())
                    except:
                        Logger.log("e", "Dremel 3D20 plugin - Error writing gcode to file.")
                        return False
                try:
                    ## Serialise the current container stack and put it at the end of the file.
                    if not has_settings:
                        settings = self._serialiseSettings(global_container_stack)
                        stream.write(settings.encode())
                    return True
                except Exception as e:
                    Logger.log("i", "Exception caught while serializing settings.")
                    Logger.log("d",sys.exc_info()[:2])
            self.setInformation(catalog.i18nc("@warning:status", "Please prepare G-code before exporting."))
            return False
        except Exception as e:
            Logger.log("i", "Exception caught while writing gcode.")
            Logger.log("d",sys.exc_info()[:2])
            return False

    ##  Create a new container with container 2 as base and container 1 written over it.
    def _createFlattenedContainerInstance(self, instance_container1, instance_container2):
        flat_container = InstanceContainer(instance_container2.getName())

        # The metadata includes id, name and definition
        flat_container.setMetaData(copy.deepcopy(instance_container2.getMetaData()))

        if instance_container1.getDefinition():
            flat_container.setDefinition(instance_container1.getDefinition().getId())

        for key in instance_container2.getAllKeys():
            flat_container.setProperty(key, "value", instance_container2.getProperty(key, "value"))

        for key in instance_container1.getAllKeys():
            flat_container.setProperty(key, "value", instance_container1.getProperty(key, "value"))

        return flat_container


    ######################################################################
    ##  Serialises a container stack to prepare it for writing at the end of the
    #   g-code.
    #
    #   The settings are serialised, and special characters (including newline)
    #   are escaped.
    #
    #   \param settings A container stack to serialise.
    #   \return A serialised string of the settings.
    ######################################################################
    def _serialiseSettings(self, stack):
        container_registry = self._application.getContainerRegistry()

        prefix = self._setting_keyword + str(Dremel3D20.version) + " "  # The prefix to put before each line.
        prefix_length = len(prefix)

        quality_type = stack.quality.getMetaDataEntry("quality_type")
        container_with_profile = stack.qualityChanges
        machine_definition_id_for_quality = ContainerTree.getInstance().machines[stack.definition.getId()].quality_definition
        if container_with_profile.getId() == "empty_quality_changes":
            # If the global quality changes is empty, create a new one
            quality_name = container_registry.uniqueName(stack.quality.getName())
            quality_id = container_registry.uniqueName((stack.definition.getId() + "_" + quality_name).lower().replace(" ", "_"))
            container_with_profile = InstanceContainer(quality_id)
            container_with_profile.setName(quality_name)
            container_with_profile.setMetaDataEntry("type", "quality_changes")
            container_with_profile.setMetaDataEntry("quality_type", quality_type)
            if stack.getMetaDataEntry("position") is not None:  # For extruder stacks, the quality changes should include an intent category.
                container_with_profile.setMetaDataEntry("intent_category", stack.intent.getMetaDataEntry("intent_category", "default"))
            container_with_profile.setDefinition(machine_definition_id_for_quality)
            container_with_profile.setMetaDataEntry("setting_version", stack.quality.getMetaDataEntry("setting_version"))

        flat_global_container = self._createFlattenedContainerInstance(stack.userChanges, container_with_profile)
        # If the quality changes is not set, we need to set type manually
        if flat_global_container.getMetaDataEntry("type", None) is None:
            flat_global_container.setMetaDataEntry("type", "quality_changes")

        # Ensure that quality_type is set. (Can happen if we have empty quality changes).
        if flat_global_container.getMetaDataEntry("quality_type", None) is None:
            flat_global_container.setMetaDataEntry("quality_type", stack.quality.getMetaDataEntry("quality_type", "normal"))

        # Get the machine definition ID for quality profiles
        flat_global_container.setMetaDataEntry("definition", machine_definition_id_for_quality)

        serialized = flat_global_container.serialize()
        data = {"global_quality": serialized}

        all_setting_keys = flat_global_container.getAllKeys()
        for extruder in stack.extruderList:
            extruder_quality = extruder.qualityChanges
            if extruder_quality.getId() == "empty_quality_changes":
                # Same story, if quality changes is empty, create a new one
                quality_name = container_registry.uniqueName(stack.quality.getName())
                quality_id = container_registry.uniqueName((stack.definition.getId() + "_" + quality_name).lower().replace(" ", "_"))
                extruder_quality = InstanceContainer(quality_id)
                extruder_quality.setName(quality_name)
                extruder_quality.setMetaDataEntry("type", "quality_changes")
                extruder_quality.setMetaDataEntry("quality_type", quality_type)
                extruder_quality.setDefinition(machine_definition_id_for_quality)
                extruder_quality.setMetaDataEntry("setting_version", stack.quality.getMetaDataEntry("setting_version"))

            flat_extruder_quality = self._createFlattenedContainerInstance(extruder.userChanges, extruder_quality)
            # If the quality changes is not set, we need to set type manually
            if flat_extruder_quality.getMetaDataEntry("type", None) is None:
                flat_extruder_quality.setMetaDataEntry("type", "quality_changes")

            # Ensure that extruder is set. (Can happen if we have empty quality changes).
            if flat_extruder_quality.getMetaDataEntry("position", None) is None:
                flat_extruder_quality.setMetaDataEntry("position", extruder.getMetaDataEntry("position"))

            # Ensure that quality_type is set. (Can happen if we have empty quality changes).
            if flat_extruder_quality.getMetaDataEntry("quality_type", None) is None:
                flat_extruder_quality.setMetaDataEntry("quality_type", extruder.quality.getMetaDataEntry("quality_type", "normal"))

            # Change the default definition
            flat_extruder_quality.setMetaDataEntry("definition", machine_definition_id_for_quality)

            extruder_serialized = flat_extruder_quality.serialize()
            data.setdefault("extruder_quality", []).append(extruder_serialized)

            all_setting_keys.update(flat_extruder_quality.getAllKeys())

        # Check if there is any profiles
        if not all_setting_keys:
            Logger.log("i", "No custom settings found, not writing settings to g-code.")
            return ""

        json_string = json.dumps(data)

        # Escape characters that have a special meaning in g-code comments.
        pattern = re.compile("|".join(Dremel3D20.escape_characters.keys()))

        # Perform the replacement with a regular expression.
        escaped_string = pattern.sub(lambda m: Dremel3D20.escape_characters[re.escape(m.group(0))], json_string)

        # Introduce line breaks so that each comment is no longer than 80 characters. Prepend each line with the prefix.
        result = ""

        # Lines have 80 characters, so the payload of each line is 80 - prefix.
        for pos in range(0, len(escaped_string), 80 - prefix_length):
            result += prefix + escaped_string[pos: pos + 80 - prefix_length] + "\n"
        return result

    # dremel 3d20 icon in bmp format in binary
    dremel3D20IconBmpData = [66, 77, 120, 56, 0, 0, 0, 0, 0, 0, 54, 0, 0, 0, 40, 0, 0, 0, 80, 0, 0, 0, 60, 0, 0, 0, 1, 0, 24, 0, 0, 0, 0, 0, 66, 56, 0, 0, 195, 14, 0, 0, 195, 14, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 232, 232, 232, 205, 205, 206, 187, 187, 189, 181, 181, 182, 178, 178, 179, 179, 179, 180, 174, 174, 175, 178, 178, 179, 182, 182, 182, 198, 198, 199, 232, 232, 232, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 250, 250, 250, 173, 173, 174, 180, 180, 181, 177, 177, 178, 176, 176, 177, 176, 176, 177, 170, 170, 172, 144, 145, 147, 160, 161, 162, 178, 178, 179, 180, 180, 181, 173, 173, 174, 247, 247, 247, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 241, 241, 241, 187, 187, 188, 177, 177, 178, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 175, 176, 164, 164, 165, 141, 142, 144, 158, 159, 160, 176, 176, 177, 174, 174, 175, 179, 179, 180, 195, 195, 195, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 237, 237, 237, 204, 204, 205, 187, 187, 188, 174, 174, 175, 177, 177, 178, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 175, 176, 164, 164, 165, 142, 143, 145, 161, 161, 162, 176, 176, 177, 174, 174, 175, 175, 175, 176, 174, 174, 175, 191, 191, 192, 243, 243, 243, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 247, 247, 247, 218, 218, 218, 195, 195, 196, 177, 177, 177, 173, 173, 174, 178, 178, 178, 177, 177, 178, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 176, 164, 164, 165, 142, 143, 145, 162, 162, 164, 176, 176, 177, 174, 174, 175, 174, 174, 175, 175, 175, 176, 178, 178, 179, 172, 172, 173, 211, 211, 212, 254, 254, 254, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 254, 254, 254, 235, 235, 235, 212, 212, 213, 182, 182, 183, 176, 176, 178, 176, 176, 177, 178, 178, 179, 177, 177, 178, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 176, 164, 164, 165, 142, 143, 145, 161, 161, 163, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 178, 178, 179, 178, 178, 179, 182, 182, 183, 224, 224, 224, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 253, 253, 253, 235, 235, 235, 214, 214, 215, 196, 196, 196, 179, 179, 180, 173, 173, 174, 177, 177, 178, 177, 177, 178, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 176, 164, 164, 165, 142, 143, 145, 159, 160, 161, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 177, 177, 178, 174, 174, 175, 186, 186, 187, 216, 216, 216, 250, 250, 250, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 253, 253, 253, 235, 235, 235, 215, 215, 215, 198, 198, 199, 179, 179, 179, 174, 174, 175, 176, 176, 177, 177, 177, 178, 177, 177, 178, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 176, 164, 164, 165, 142, 143, 145, 159, 159, 160, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 177, 177, 178, 176, 176, 177, 176, 176, 177, 209, 209, 210, 242, 242, 242, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 254, 254, 254, 244, 244, 245, 221, 221, 222, 202, 202, 202, 188, 188, 188, 179, 179, 179, 173, 173, 174, 176, 176, 177, 177, 177, 178, 176, 176, 177, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 175, 175, 176, 175, 175, 176, 176, 176, 177, 176, 175, 176, 177, 176, 176, 164, 164, 165, 143, 144, 146, 156, 157, 158, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 177, 177, 178, 177, 177, 178, 174, 174, 175, 189, 189, 190, 225, 225, 225, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 223, 223, 223, 194, 194, 194, 187, 187, 188, 235, 235, 235, 255, 255, 255, 241, 241, 241, 226, 226, 226, 212, 212, 213, 188, 188, 188, 178, 178, 179, 175, 175, 176, 176, 176, 177, 178, 178, 179, 177, 177, 178, 176, 176, 177, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 175, 175, 176, 176, 176, 177, 176, 176, 177, 175, 175, 176, 172, 172, 173, 169, 169, 170, 167, 167, 168, 160, 160, 161, 153, 154, 155, 151, 152, 153, 147, 148, 150, 113, 111, 112, 143, 143, 144, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 177, 178, 178, 179, 175, 175, 177, 184, 184, 185, 218, 218, 218, 233, 233, 233, 203, 203, 203, 194, 194, 195, 230, 230, 230, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 187, 187, 188, 180, 180, 181, 179, 179, 180, 180, 180, 181, 176, 176, 176, 177, 177, 178, 175, 175, 176, 173, 173, 174, 176, 176, 177, 178, 178, 179, 177, 177, 178, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 176, 176, 176, 176, 176, 177, 175, 175, 176, 171, 171, 172, 168, 168, 169, 162, 162, 163, 156, 157, 158, 152, 153, 155, 146, 147, 149, 145, 146, 148, 144, 145, 147, 143, 144, 146, 143, 144, 146, 146, 147, 149, 133, 133, 135, 93, 90, 90, 128, 127, 128, 178, 178, 179, 176, 177, 178, 176, 177, 178, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 176, 176, 177, 165, 164, 164, 99, 94, 92, 128, 125, 124, 169, 169, 170, 180, 180, 181, 182, 182, 183, 172, 172, 173, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 172, 172, 172, 179, 179, 180, 174, 174, 175, 174, 174, 175, 175, 175, 176, 177, 177, 178, 175, 175, 176, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 176, 176, 177, 176, 176, 177, 174, 174, 175, 171, 171, 172, 165, 165, 166, 160, 161, 162, 153, 154, 155, 147, 148, 150, 147, 148, 150, 147, 149, 151, 148, 149, 151, 148, 149, 150, 148, 149, 151, 144, 145, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 149, 151, 130, 129, 131, 94, 91, 90, 128, 127, 127, 178, 179, 181, 163, 159, 158, 166, 163, 163, 179, 181, 183, 179, 180, 182, 175, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 178, 178, 179, 156, 155, 155, 52, 43, 39, 52, 44, 40, 71, 63, 60, 160, 159, 159, 178, 178, 179, 180, 180, 181, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 178, 178, 179, 177, 177, 178, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 175, 175, 176, 176, 176, 177, 176, 176, 177, 174, 174, 175, 167, 168, 169, 162, 163, 164, 156, 157, 158, 149, 150, 152, 147, 148, 150, 147, 148, 150, 148, 150, 152, 148, 150, 152, 144, 145, 148, 134, 134, 136, 118, 116, 117, 122, 121, 121, 171, 171, 172, 168, 169, 169, 144, 145, 147, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 149, 151, 130, 130, 131, 94, 91, 91, 128, 127, 128, 182, 185, 187, 130, 114, 106, 86, 53, 36, 115, 94, 84, 147, 138, 134, 174, 175, 176, 180, 182, 184, 177, 178, 180, 174, 174, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 178, 178, 179, 155, 154, 155, 64, 57, 54, 84, 79, 78, 72, 66, 64, 119, 115, 114, 182, 182, 184, 180, 180, 181, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 179, 179, 179, 177, 177, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 176, 176, 177, 175, 175, 176, 172, 172, 173, 168, 168, 169, 161, 161, 163, 156, 156, 158, 150, 151, 153, 144, 145, 147, 143, 144, 146, 143, 144, 146, 144, 145, 147, 143, 144, 146, 128, 128, 129, 109, 107, 107, 90, 86, 85, 71, 65, 63, 58, 51, 48, 45, 35, 31, 60, 53, 49, 160, 161, 162, 174, 174, 175, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 149, 151, 130, 130, 132, 94, 91, 90, 128, 127, 127, 182, 184, 186, 132, 116, 109, 77, 38, 20, 97, 65, 49, 81, 45, 28, 92, 63, 49, 127, 111, 103, 160, 155, 153, 177, 178, 180, 179, 181, 183, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 173, 173, 174, 100, 94, 93, 55, 47, 44, 51, 43, 40, 122, 118, 117, 182, 182, 184, 179, 179, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 180, 180, 181, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 176, 176, 177, 175, 175, 176, 173, 173, 174, 168, 168, 169, 159, 159, 160, 154, 154, 156, 147, 148, 150, 144, 145, 147, 143, 144, 146, 143, 144, 146, 144, 145, 147, 145, 146, 148, 145, 146, 148, 145, 146, 148, 149, 150, 152, 122, 121, 122, 51, 42, 38, 44, 35, 31, 44, 34, 30, 45, 36, 31, 47, 38, 33, 47, 37, 33, 54, 46, 43, 144, 144, 145, 176, 176, 177, 148, 148, 150, 144, 145, 147, 145, 146, 148, 145, 146, 148, 147, 148, 151, 131, 131, 133, 94, 91, 91, 126, 126, 126, 181, 184, 186, 136, 122, 115, 74, 36, 18, 194, 184, 181, 212, 207, 205, 150, 131, 122, 91, 57, 42, 78, 43, 26, 98, 71, 58, 134, 120, 114, 169, 168, 169, 175, 176, 177, 174, 174, 175, 175, 175, 176, 175, 175, 177, 176, 176, 177, 179, 179, 180, 154, 152, 152, 116, 112, 111, 158, 157, 157, 177, 178, 179, 179, 179, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 179, 179, 180, 176, 176, 177, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 175, 176, 175, 176, 176, 176, 177, 175, 175, 176, 172, 172, 173, 166, 166, 167, 161, 161, 163, 153, 154, 155, 148, 149, 151, 145, 145, 147, 143, 144, 146, 143, 145, 147, 144, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 148, 150, 152, 124, 123, 124, 49, 41, 37, 48, 39, 34, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 50, 42, 38, 133, 132, 133, 177, 177, 178, 149, 150, 152, 144, 145, 147, 145, 146, 148, 145, 146, 148, 147, 149, 151, 131, 131, 132, 94, 91, 91, 126, 124, 125, 180, 182, 184, 146, 136, 133, 73, 35, 16, 188, 178, 172, 250, 253, 255, 245, 247, 248, 227, 225, 224, 185, 173, 168, 129, 104, 92, 87, 53, 36, 85, 51, 35, 149, 140, 137, 181, 184, 186, 176, 177, 178, 171, 170, 171, 176, 178, 179, 178, 180, 182, 178, 178, 179, 182, 182, 184, 176, 177, 178, 175, 175, 176, 179, 179, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 179, 179, 180, 176, 176, 177, 175, 175, 176, 176, 176, 177, 176, 176, 176, 172, 172, 173, 165, 165, 167, 160, 160, 162, 151, 152, 154, 147, 148, 150, 144, 145, 147, 143, 144, 146, 144, 145, 147, 144, 145, 147, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 148, 149, 151, 130, 130, 131, 54, 46, 42, 48, 38, 34, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 39, 35, 47, 38, 34, 124, 123, 124, 177, 178, 179, 151, 151, 153, 144, 145, 147, 145, 146, 148, 145, 146, 148, 147, 148, 151, 132, 132, 133, 94, 91, 91, 125, 124, 125, 177, 178, 179, 169, 167, 168, 84, 52, 36, 163, 147, 139, 246, 248, 249, 236, 236, 236, 240, 241, 242, 244, 246, 247, 243, 245, 246, 224, 222, 221, 150, 130, 120, 140, 128, 123, 160, 155, 154, 105, 79, 67, 92, 61, 46, 101, 75, 63, 147, 137, 133, 179, 181, 183, 174, 175, 176, 174, 174, 175, 174, 174, 176, 178, 178, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 181, 181, 181, 174, 174, 174, 168, 169, 170, 161, 161, 162, 154, 155, 156, 148, 148, 150, 143, 144, 146, 143, 144, 146, 144, 145, 147, 144, 145, 147, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 136, 137, 139, 59, 51, 48, 47, 37, 33, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 44, 35, 31, 116, 114, 114, 179, 179, 181, 151, 151, 153, 144, 145, 147, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 133, 135, 95, 91, 91, 124, 123, 124, 175, 175, 176, 180, 183, 185, 116, 95, 86, 116, 88, 74, 242, 243, 244, 237, 237, 237, 227, 226, 225, 242, 244, 245, 244, 245, 246, 249, 251, 253, 201, 194, 190, 131, 117, 110, 98, 69, 56, 73, 34, 16, 97, 64, 49, 111, 82, 68, 89, 55, 38, 130, 116, 109, 178, 180, 182, 174, 175, 176, 174, 174, 175, 178, 178, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 163, 164, 164, 149, 150, 151, 144, 145, 147, 143, 144, 146, 144, 145, 147, 144, 145, 147, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 144, 145, 147, 67, 60, 58, 46, 36, 32, 49, 40, 36, 49, 40, 36, 48, 39, 35, 47, 37, 33, 39, 29, 25, 105, 102, 101, 182, 183, 184, 152, 153, 154, 144, 145, 147, 145, 146, 148, 145, 146, 148, 147, 148, 150, 135, 135, 137, 96, 93, 93, 123, 123, 123, 175, 175, 176, 178, 178, 180, 161, 156, 155, 85, 51, 35, 197, 189, 185, 250, 253, 254, 177, 166, 160, 128, 104, 92, 190, 180, 175, 236, 235, 235, 203, 196, 193, 93, 65, 52, 76, 38, 20, 112, 84, 70, 226, 224, 223, 240, 242, 243, 217, 212, 210, 124, 99, 86, 130, 115, 108, 179, 181, 183, 174, 174, 175, 178, 178, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 154, 154, 156, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 149, 148, 149, 152, 77, 72, 70, 41, 31, 26, 45, 35, 31, 46, 37, 33, 50, 41, 37, 60, 53, 50, 70, 64, 62, 117, 115, 116, 154, 155, 156, 146, 147, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 136, 137, 138, 97, 93, 93, 123, 122, 123, 175, 175, 176, 175, 175, 176, 180, 181, 184, 124, 106, 98, 111, 82, 67, 239, 240, 241, 234, 233, 233, 111, 84, 71, 110, 89, 80, 140, 125, 117, 135, 115, 105, 81, 47, 30, 81, 45, 28, 194, 186, 181, 246, 248, 249, 241, 242, 242, 248, 251, 252, 235, 235, 234, 128, 106, 95, 158, 154, 153, 177, 178, 179, 178, 178, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 155, 156, 157, 146, 147, 149, 145, 146, 148, 144, 145, 147, 133, 133, 134, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 146, 147, 149, 151, 153, 155, 100, 97, 96, 67, 60, 57, 83, 79, 78, 97, 94, 93, 112, 110, 111, 122, 121, 123, 122, 122, 123, 123, 123, 124, 127, 127, 129, 143, 143, 146, 146, 147, 149, 145, 146, 148, 145, 146, 148, 147, 148, 150, 137, 138, 140, 97, 94, 94, 121, 120, 121, 174, 174, 176, 177, 178, 180, 179, 181, 183, 177, 179, 180, 103, 78, 67, 156, 137, 128, 254, 255, 255, 215, 210, 208, 109, 84, 72, 163, 161, 161, 155, 150, 149, 84, 51, 35, 105, 75, 61, 235, 235, 235, 240, 241, 242, 216, 212, 210, 211, 206, 203, 248, 251, 252, 196, 187, 182, 129, 114, 107, 179, 181, 183, 179, 179, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 155, 155, 157, 146, 147, 149, 146, 147, 149, 142, 142, 144, 116, 115, 116, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 146, 147, 149, 147, 148, 150, 147, 148, 150, 145, 146, 148, 141, 142, 143, 136, 136, 138, 134, 134, 135, 126, 126, 128, 126, 126, 127, 131, 131, 133, 133, 134, 135, 137, 137, 139, 141, 142, 144, 143, 144, 146, 146, 147, 149, 147, 148, 150, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 139, 140, 142, 98, 96, 95, 119, 118, 118, 174, 175, 177, 159, 153, 152, 153, 146, 143, 175, 176, 177, 175, 176, 177, 101, 75, 62, 185, 173, 167, 253, 255, 255, 188, 177, 171, 117, 96, 86, 160, 156, 155, 78, 43, 25, 127, 103, 90, 243, 245, 246, 236, 237, 236, 111, 83, 70, 86, 52, 36, 215, 211, 209, 238, 237, 237, 136, 118, 110, 172, 172, 173, 179, 179, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 154, 155, 157, 145, 146, 149, 146, 147, 149, 140, 141, 143, 104, 102, 102, 140, 140, 142, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 146, 147, 149, 147, 148, 150, 147, 148, 150, 146, 148, 150, 144, 145, 147, 141, 141, 143, 136, 137, 138, 131, 130, 132, 128, 127, 129, 126, 125, 127, 123, 121, 123, 125, 125, 127, 135, 135, 137, 141, 141, 143, 144, 145, 147, 146, 147, 150, 148, 149, 151, 148, 149, 151, 148, 149, 151, 148, 149, 151, 147, 148, 151, 146, 147, 149, 145, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 141, 142, 144, 99, 97, 97, 117, 116, 116, 176, 179, 181, 129, 111, 104, 77, 39, 21, 92, 62, 48, 129, 113, 106, 134, 121, 115, 91, 59, 43, 212, 207, 204, 253, 255, 255, 161, 145, 137, 113, 94, 85, 77, 41, 24, 150, 131, 122, 249, 251, 253, 220, 217, 216, 91, 58, 41, 71, 32, 14, 171, 157, 150, 253, 255, 255, 157, 141, 134, 156, 151, 150, 180, 181, 182, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 154, 154, 156, 145, 146, 148, 146, 147, 149, 140, 140, 142, 100, 98, 98, 131, 131, 133, 147, 149, 151, 145, 146, 148, 146, 147, 149, 146, 148, 150, 147, 148, 150, 147, 148, 150, 145, 146, 148, 142, 143, 145, 138, 138, 140, 132, 132, 133, 128, 128, 129, 125, 124, 126, 124, 123, 124, 126, 125, 126, 130, 130, 131, 135, 135, 136, 138, 139, 140, 144, 145, 147, 146, 148, 150, 148, 149, 152, 148, 149, 151, 148, 149, 151, 148, 149, 151, 146, 147, 149, 145, 146, 148, 142, 143, 145, 137, 137, 139, 133, 133, 134, 125, 124, 125, 114, 112, 112, 134, 135, 136, 147, 148, 150, 145, 146, 148, 145, 146, 148, 146, 147, 149, 142, 143, 145, 101, 98, 98, 116, 115, 116, 176, 178, 181, 130, 113, 105, 78, 42, 24, 126, 102, 89, 102, 70, 55, 95, 65, 51, 104, 80, 69, 121, 96, 83, 242, 243, 244, 234, 234, 233, 110, 84, 71, 70, 33, 15, 163, 147, 138, 252, 255, 255, 205, 200, 197, 83, 49, 32, 74, 36, 18, 147, 128, 119, 253, 255, 255, 176, 162, 156, 142, 132, 128, 182, 183, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 154, 154, 156, 145, 146, 148, 146, 147, 149, 140, 141, 143, 99, 96, 96, 118, 117, 118, 149, 150, 153, 145, 146, 148, 140, 140, 142, 135, 135, 137, 131, 131, 132, 124, 123, 125, 118, 117, 118, 117, 116, 117, 124, 124, 125, 132, 132, 133, 136, 136, 138, 141, 141, 143, 145, 146, 148, 147, 149, 151, 148, 150, 152, 149, 150, 152, 148, 150, 152, 148, 149, 151, 146, 148, 150, 143, 144, 146, 141, 142, 143, 136, 137, 138, 125, 125, 126, 116, 115, 115, 107, 105, 104, 98, 95, 94, 87, 83, 81, 73, 68, 65, 86, 82, 80, 104, 102, 101, 126, 125, 126, 147, 149, 151, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 143, 145, 102, 99, 99, 115, 114, 115, 175, 177, 180, 136, 121, 114, 76, 39, 21, 208, 203, 200, 244, 246, 247, 167, 153, 146, 135, 122, 117, 81, 46, 29, 199, 191, 187, 253, 255, 255, 163, 148, 141, 65, 26, 7, 164, 148, 140, 252, 255, 255, 200, 193, 190, 80, 45, 28, 76, 39, 21, 132, 109, 98, 250, 253, 254, 187, 176, 170, 137, 125, 119, 183, 184, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 156, 145, 146, 148, 146, 147, 149, 144, 145, 147, 105, 103, 104, 101, 99, 99, 121, 120, 121, 120, 119, 120, 120, 119, 120, 126, 125, 127, 130, 129, 131, 136, 137, 138, 142, 143, 145, 146, 147, 149, 149, 150, 152, 149, 150, 153, 149, 150, 152, 148, 149, 151, 145, 146, 148, 142, 143, 145, 140, 141, 143, 134, 135, 136, 127, 127, 128, 119, 118, 119, 108, 106, 106, 98, 95, 93, 88, 84, 82, 75, 69, 66, 67, 60, 57, 60, 52, 48, 51, 43, 39, 49, 40, 36, 46, 37, 33, 44, 34, 30, 55, 47, 43, 103, 100, 99, 125, 125, 126, 148, 149, 151, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 144, 146, 103, 100, 100, 114, 113, 114, 173, 174, 177, 152, 144, 141, 74, 37, 19, 186, 175, 170, 254, 255, 255, 192, 183, 178, 116, 96, 87, 77, 41, 24, 170, 156, 148, 253, 255, 255, 190, 181, 176, 67, 29, 11, 156, 138, 129, 252, 255, 255, 201, 193, 190, 81, 46, 29, 76, 39, 21, 127, 103, 92, 248, 251, 252, 195, 186, 182, 137, 124, 119, 183, 184, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 154, 154, 155, 145, 146, 148, 145, 146, 148, 146, 147, 149, 139, 139, 141, 133, 133, 135, 140, 141, 143, 145, 146, 148, 148, 150, 152, 150, 151, 153, 149, 151, 153, 147, 149, 151, 146, 147, 149, 145, 146, 148, 139, 140, 141, 135, 135, 136, 130, 130, 131, 119, 119, 119, 109, 107, 107, 98, 95, 94, 88, 84, 82, 80, 75, 73, 70, 64, 61, 57, 50, 47, 51, 42, 38, 48, 39, 35, 46, 37, 33, 45, 36, 32, 46, 36, 32, 47, 37, 33, 48, 39, 35, 48, 39, 35, 49, 40, 36, 48, 38, 34, 56, 47, 44, 102, 99, 98, 125, 124, 125, 148, 149, 151, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 145, 147, 104, 101, 102, 114, 112, 112, 169, 170, 171, 176, 176, 178, 92, 64, 49, 151, 131, 122, 249, 252, 253, 223, 221, 220, 96, 64, 48, 63, 24, 4, 172, 158, 151, 252, 255, 255, 200, 193, 190, 70, 33, 16, 135, 113, 102, 249, 252, 254, 207, 201, 198, 84, 49, 33, 76, 38, 20, 128, 105, 93, 248, 251, 252, 198, 190, 186, 139, 126, 121, 182, 184, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 148, 149, 152, 144, 145, 147, 139, 139, 141, 135, 135, 136, 132, 132, 133, 126, 126, 127, 118, 117, 117, 110, 108, 107, 97, 94, 93, 86, 82, 80, 78, 73, 70, 66, 60, 57, 58, 51, 47, 54, 46, 43, 49, 40, 36, 46, 37, 33, 46, 36, 32, 46, 36, 32, 47, 38, 34, 48, 39, 35, 49, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 38, 34, 56, 48, 44, 102, 99, 98, 125, 124, 125, 148, 149, 151, 145, 146, 148, 145, 146, 148, 146, 147, 149, 144, 145, 147, 105, 103, 103, 112, 111, 112, 168, 168, 170, 181, 182, 184, 139, 127, 122, 96, 64, 49, 230, 229, 228, 244, 246, 247, 205, 198, 195, 151, 132, 123, 220, 216, 215, 246, 248, 249, 197, 189, 185, 74, 39, 22, 115, 87, 74, 241, 243, 244, 223, 221, 220, 93, 60, 45, 73, 36, 17, 138, 117, 107, 250, 253, 254, 194, 184, 180, 138, 126, 121, 183, 184, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 144, 145, 119, 118, 119, 106, 104, 103, 97, 95, 93, 89, 86, 84, 77, 72, 70, 69, 62, 59, 63, 56, 53, 54, 46, 42, 47, 38, 34, 46, 37, 32, 45, 36, 32, 46, 37, 32, 47, 38, 33, 48, 38, 34, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 38, 34, 56, 48, 44, 102, 99, 98, 125, 125, 125, 147, 149, 151, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 106, 104, 104, 112, 110, 111, 168, 168, 169, 176, 176, 177, 177, 178, 180, 110, 87, 76, 143, 121, 111, 245, 247, 248, 244, 246, 247, 245, 247, 248, 238, 239, 239, 245, 247, 248, 185, 175, 170, 108, 86, 77, 95, 62, 46, 228, 226, 226, 240, 240, 241, 111, 83, 70, 64, 25, 5, 160, 143, 135, 253, 255, 255, 184, 173, 168, 141, 130, 126, 183, 185, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 154, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 135, 136, 80, 75, 74, 67, 61, 59, 65, 58, 56, 61, 53, 50, 57, 49, 46, 52, 44, 40, 48, 39, 35, 47, 37, 33, 48, 38, 34, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 38, 34, 55, 47, 44, 101, 98, 97, 126, 125, 126, 148, 149, 152, 145, 146, 148, 145, 146, 148, 145, 146, 148, 146, 147, 149, 108, 106, 106, 110, 109, 109, 168, 168, 169, 176, 176, 177, 176, 176, 178, 175, 175, 177, 116, 96, 87, 150, 130, 121, 231, 230, 229, 244, 246, 246, 246, 247, 248, 228, 226, 224, 154, 143, 138, 164, 162, 162, 81, 47, 31, 175, 162, 156, 252, 255, 255, 192, 183, 179, 99, 69, 54, 206, 199, 196, 250, 252, 253, 176, 165, 159, 153, 147, 146, 181, 182, 184, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 151, 133, 134, 135, 73, 67, 65, 65, 58, 56, 68, 61, 59, 69, 62, 60, 69, 62, 60, 69, 62, 60, 67, 60, 57, 62, 54, 51, 56, 47, 44, 50, 41, 37, 48, 39, 35, 49, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 38, 34, 54, 46, 42, 106, 105, 104, 119, 118, 118, 144, 144, 146, 146, 147, 149, 145, 146, 148, 145, 146, 148, 147, 148, 150, 109, 107, 107, 110, 108, 109, 167, 168, 169, 176, 176, 177, 176, 177, 178, 178, 179, 181, 170, 169, 169, 129, 115, 108, 130, 111, 102, 165, 153, 146, 178, 168, 163, 155, 143, 139, 164, 162, 162, 181, 183, 186, 125, 108, 100, 108, 78, 63, 237, 238, 239, 243, 244, 245, 231, 230, 230, 238, 239, 239, 240, 241, 241, 159, 147, 141, 169, 168, 169, 180, 180, 181, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 134, 135, 75, 69, 67, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 69, 62, 60, 66, 58, 56, 59, 51, 48, 51, 42, 38, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 54, 45, 42, 108, 106, 105, 98, 85, 79, 135, 135, 136, 147, 148, 150, 145, 146, 148, 145, 146, 148, 147, 148, 150, 109, 107, 108, 110, 108, 109, 167, 167, 169, 178, 179, 181, 167, 164, 164, 110, 86, 75, 88, 55, 40, 88, 56, 41, 91, 62, 47, 108, 86, 76, 154, 149, 147, 176, 177, 179, 178, 179, 181, 179, 181, 182, 179, 180, 182, 118, 99, 89, 144, 124, 113, 241, 243, 243, 247, 249, 250, 247, 249, 250, 210, 204, 201, 148, 138, 134, 177, 179, 180, 180, 180, 181, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 134, 135, 75, 69, 67, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 69, 62, 61, 67, 59, 57, 58, 50, 46, 50, 41, 37, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 53, 45, 42, 101, 98, 97, 93, 75, 66, 135, 135, 136, 147, 148, 150, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 108, 109, 107, 108, 167, 168, 170, 178, 179, 181, 111, 88, 77, 72, 33, 13, 90, 57, 40, 128, 104, 92, 122, 96, 83, 97, 64, 49, 93, 64, 50, 160, 156, 154, 162, 158, 157, 150, 141, 138, 168, 167, 167, 179, 183, 185, 131, 116, 109, 140, 121, 112, 186, 176, 171, 191, 183, 178, 152, 140, 135, 170, 169, 170, 176, 176, 177, 179, 179, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 134, 135, 75, 69, 67, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 62, 60, 69, 63, 61, 66, 59, 57, 56, 48, 45, 49, 40, 36, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 52, 43, 40, 99, 97, 95, 93, 75, 65, 134, 133, 134, 147, 148, 151, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 108, 109, 107, 108, 171, 173, 175, 151, 142, 139, 77, 40, 21, 96, 65, 49, 210, 205, 203, 246, 247, 249, 241, 243, 243, 231, 230, 230, 178, 166, 159, 111, 87, 75, 118, 98, 89, 79, 42, 25, 84, 51, 35, 102, 76, 64, 128, 110, 103, 140, 130, 126, 147, 140, 137, 158, 154, 153, 172, 172, 173, 175, 176, 177, 175, 175, 176, 180, 180, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 134, 135, 75, 70, 68, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 69, 62, 60, 63, 56, 53, 53, 45, 41, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 50, 41, 38, 97, 94, 93, 92, 74, 65, 133, 132, 132, 147, 149, 151, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 108, 108, 107, 107, 172, 175, 177, 132, 116, 108, 69, 30, 11, 163, 147, 140, 249, 252, 253, 237, 237, 237, 244, 246, 246, 244, 245, 246, 249, 252, 254, 197, 188, 184, 88, 56, 40, 80, 44, 27, 128, 103, 91, 124, 98, 85, 87, 53, 36, 80, 44, 27, 98, 71, 58, 156, 150, 148, 179, 181, 183, 174, 174, 175, 175, 175, 176, 179, 179, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 134, 135, 76, 71, 69, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 68, 61, 59, 59, 52, 49, 49, 41, 37, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 48, 39, 35, 95, 92, 90, 92, 74, 66, 130, 129, 129, 147, 149, 151, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 109, 109, 107, 107, 171, 173, 176, 117, 96, 86, 75, 38, 20, 200, 193, 189, 244, 246, 246, 235, 235, 235, 190, 180, 176, 209, 203, 200, 240, 242, 242, 247, 249, 250, 138, 117, 107, 69, 31, 12, 199, 191, 188, 248, 251, 253, 222, 219, 218, 199, 191, 187, 143, 122, 112, 92, 60, 45, 145, 136, 132, 179, 181, 183, 175, 175, 176, 179, 179, 179, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 134, 135, 77, 72, 70, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 65, 58, 55, 54, 46, 43, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 47, 38, 34, 91, 88, 86, 92, 75, 67, 127, 125, 124, 148, 149, 152, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 109, 109, 107, 107, 171, 173, 175, 108, 84, 72, 85, 50, 33, 226, 225, 224, 253, 255, 255, 192, 183, 178, 72, 35, 17, 86, 52, 35, 203, 197, 193, 250, 253, 254, 187, 176, 171, 70, 33, 15, 192, 183, 178, 244, 246, 247, 240, 240, 241, 243, 245, 246, 246, 248, 250, 212, 206, 204, 117, 92, 80, 157, 152, 150, 179, 180, 181, 176, 176, 177, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 134, 135, 78, 72, 71, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 69, 62, 60, 59, 51, 48, 49, 40, 36, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 46, 37, 33, 86, 83, 81, 93, 75, 66, 126, 122, 121, 148, 149, 152, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 109, 109, 107, 107, 171, 172, 174, 125, 108, 100, 93, 62, 47, 172, 158, 151, 213, 208, 206, 164, 148, 141, 75, 38, 21, 72, 34, 16, 159, 142, 134, 251, 255, 255, 207, 202, 199, 77, 42, 25, 192, 182, 177, 243, 245, 246, 239, 240, 240, 246, 248, 249, 241, 242, 242, 246, 249, 250, 201, 193, 189, 122, 104, 95, 181, 183, 185, 172, 172, 172, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 133, 135, 78, 74, 72, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 64, 57, 54, 53, 44, 41, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 46, 36, 32, 82, 79, 77, 95, 79, 71, 123, 118, 117, 148, 150, 152, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 108, 108, 107, 107, 167, 168, 169, 177, 178, 179, 166, 164, 164, 151, 144, 142, 122, 104, 95, 89, 55, 38, 77, 41, 23, 66, 26, 7, 161, 144, 136, 250, 254, 255, 212, 208, 206, 80, 46, 29, 191, 182, 177, 249, 251, 252, 193, 184, 180, 154, 136, 127, 211, 206, 203, 241, 243, 244, 242, 244, 244, 144, 125, 117, 162, 158, 157, 170, 171, 171, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 133, 134, 80, 75, 73, 66, 59, 57, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 68, 61, 59, 57, 49, 45, 48, 39, 35, 49, 40, 36, 49, 40, 36, 49, 40, 36, 49, 40, 36, 44, 35, 31, 83, 79, 77, 117, 115, 115, 134, 133, 134, 147, 148, 150, 145, 146, 148, 145, 146, 148, 147, 148, 150, 110, 108, 108, 108, 107, 107, 167, 168, 168, 179, 180, 181, 182, 184, 187, 187, 192, 195, 146, 135, 131, 76, 38, 20, 147, 128, 118, 152, 134, 125, 217, 214, 212, 249, 251, 253, 197, 188, 184, 72, 35, 18, 193, 184, 179, 252, 255, 255, 169, 154, 147, 63, 23, 4, 93, 61, 46, 217, 213, 211, 249, 252, 253, 178, 165, 158, 138, 125, 120, 185, 186, 188, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 133, 134, 80, 76, 74, 66, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 61, 53, 51, 49, 41, 37, 48, 39, 35, 49, 40, 36, 49, 40, 36, 45, 36, 32, 73, 67, 64, 126, 126, 126, 148, 149, 151, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 109, 107, 108, 109, 107, 108, 170, 172, 174, 152, 144, 140, 128, 111, 104, 155, 149, 147, 133, 118, 111, 75, 38, 20, 205, 198, 195, 253, 255, 255, 240, 241, 241, 231, 230, 230, 139, 119, 109, 70, 33, 14, 194, 185, 180, 252, 255, 255, 172, 158, 151, 76, 39, 21, 72, 35, 17, 163, 147, 139, 251, 254, 255, 204, 197, 193, 135, 121, 114, 188, 189, 191, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 133, 134, 82, 77, 75, 66, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 64, 57, 55, 52, 43, 39, 48, 39, 35, 49, 40, 36, 46, 36, 32, 71, 65, 62, 124, 124, 124, 147, 148, 150, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 109, 107, 107, 110, 108, 108, 173, 176, 179, 133, 117, 110, 74, 35, 15, 77, 41, 23, 75, 38, 20, 74, 37, 19, 192, 183, 179, 247, 250, 251, 244, 246, 247, 162, 147, 140, 85, 54, 39, 78, 41, 23, 194, 185, 181, 252, 255, 255, 172, 158, 151, 76, 39, 21, 76, 39, 21, 131, 108, 97, 245, 247, 248, 224, 221, 219, 142, 128, 122, 186, 186, 187, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 133, 134, 135, 84, 80, 78, 65, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 67, 60, 58, 55, 47, 43, 48, 39, 34, 46, 36, 32, 69, 63, 60, 123, 123, 123, 147, 148, 150, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 106, 104, 104, 111, 109, 109, 173, 176, 178, 137, 123, 117, 76, 38, 20, 156, 138, 130, 166, 150, 142, 116, 89, 76, 91, 58, 42, 131, 107, 96, 226, 225, 224, 237, 237, 237, 114, 88, 75, 72, 34, 16, 195, 186, 182, 252, 255, 255, 172, 158, 151, 76, 39, 21, 78, 41, 23, 117, 91, 78, 240, 241, 242, 231, 230, 229, 146, 133, 127, 184, 184, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 134, 134, 136, 85, 81, 79, 65, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 60, 68, 61, 59, 58, 50, 46, 45, 36, 31, 66, 60, 57, 121, 121, 121, 147, 148, 150, 145, 146, 148, 145, 146, 148, 146, 147, 149, 144, 145, 147, 104, 102, 103, 111, 110, 110, 173, 175, 177, 145, 134, 130, 72, 34, 15, 193, 184, 179, 255, 255, 255, 181, 169, 163, 71, 34, 15, 69, 31, 12, 174, 161, 154, 255, 255, 255, 171, 157, 151, 68, 31, 13, 195, 186, 182, 252, 255, 255, 172, 157, 151, 76, 39, 21, 77, 41, 23, 122, 97, 84, 242, 243, 244, 232, 230, 230, 148, 135, 130, 183, 183, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 154, 145, 146, 148, 145, 146, 148, 147, 148, 150, 135, 135, 136, 86, 81, 80, 65, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 69, 62, 61, 54, 46, 43, 72, 66, 63, 121, 121, 121, 147, 148, 150, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 144, 146, 103, 100, 101, 112, 110, 111, 171, 172, 173, 167, 164, 163, 81, 47, 30, 169, 154, 147, 251, 254, 255, 207, 201, 198, 80, 44, 27, 65, 26, 7, 171, 157, 150, 253, 255, 255, 187, 176, 171, 71, 34, 16, 195, 187, 182, 252, 255, 255, 170, 155, 148, 74, 37, 18, 73, 35, 17, 145, 125, 115, 247, 249, 250, 228, 225, 224, 149, 137, 132, 185, 185, 187, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 154, 145, 146, 148, 145, 146, 148, 147, 148, 150, 135, 135, 136, 86, 82, 80, 65, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 67, 60, 58, 66, 59, 57, 66, 59, 57, 66, 58, 56, 65, 58, 56, 66, 59, 56, 66, 58, 56, 74, 69, 67, 101, 98, 97, 118, 117, 117, 147, 148, 150, 145, 146, 148, 145, 146, 148, 146, 147, 149, 142, 142, 144, 100, 97, 97, 113, 112, 112, 169, 169, 170, 181, 183, 185, 116, 95, 86, 119, 92, 79, 244, 246, 247, 240, 242, 242, 181, 169, 163, 144, 124, 114, 220, 217, 216, 248, 250, 251, 184, 173, 168, 70, 33, 15, 196, 187, 183, 251, 254, 255, 176, 163, 157, 80, 44, 27, 84, 50, 33, 195, 186, 181, 247, 249, 250, 214, 209, 206, 143, 131, 126, 187, 188, 189, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 154, 145, 146, 148, 145, 146, 148, 147, 148, 150, 136, 136, 137, 86, 82, 80, 66, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 60, 58, 67, 60, 58, 67, 59, 57, 66, 59, 57, 66, 58, 56, 66, 59, 57, 66, 59, 57, 68, 61, 59, 72, 66, 64, 77, 72, 70, 81, 75, 74, 84, 79, 77, 86, 82, 80, 92, 88, 86, 95, 91, 90, 103, 101, 99, 105, 103, 102, 122, 121, 121, 147, 148, 150, 145, 146, 148, 145, 146, 148, 147, 148, 150, 138, 139, 140, 98, 95, 95, 115, 113, 114, 169, 169, 170, 177, 178, 179, 168, 167, 167, 97, 69, 55, 179, 166, 160, 249, 252, 254, 245, 247, 248, 245, 247, 248, 239, 239, 240, 248, 250, 251, 151, 133, 124, 69, 32, 14, 197, 188, 184, 244, 246, 246, 231, 231, 230, 213, 208, 206, 213, 209, 206, 238, 239, 239, 244, 246, 247, 187, 177, 172, 144, 134, 130, 187, 189, 191, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 137, 137, 139, 86, 82, 81, 66, 58, 56, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 68, 61, 59, 67, 60, 58, 67, 59, 57, 66, 58, 56, 66, 58, 56, 66, 59, 57, 66, 59, 57, 69, 62, 60, 72, 66, 64, 74, 69, 67, 78, 73, 71, 85, 81, 79, 89, 85, 83, 92, 88, 87, 98, 95, 93, 103, 101, 100, 107, 105, 104, 111, 109, 108, 114, 112, 112, 116, 115, 115, 120, 119, 119, 126, 126, 127, 129, 129, 129, 132, 132, 133, 143, 144, 145, 146, 147, 149, 145, 146, 148, 145, 146, 148, 147, 148, 150, 135, 136, 137, 97, 94, 94, 115, 114, 115, 169, 169, 171, 175, 175, 176, 178, 179, 181, 160, 156, 155, 108, 82, 70, 179, 166, 159, 232, 231, 230, 242, 243, 243, 242, 242, 243, 209, 204, 201, 107, 81, 69, 74, 36, 18, 201, 194, 190, 246, 249, 249, 239, 239, 240, 241, 242, 243, 241, 242, 242, 237, 237, 237, 243, 244, 244, 163, 151, 146, 166, 165, 165, 185, 185, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 147, 148, 150, 139, 140, 141, 87, 83, 82, 63, 56, 54, 66, 59, 57, 65, 58, 56, 65, 58, 56, 66, 59, 57, 67, 60, 58, 68, 61, 59, 69, 62, 60, 73, 68, 65, 80, 75, 74, 87, 83, 81, 90, 86, 84, 93, 90, 88, 100, 98, 96, 105, 103, 102, 108, 106, 105, 110, 109, 108, 115, 114, 114, 121, 120, 121, 127, 127, 128, 130, 130, 131, 132, 132, 134, 135, 136, 137, 141, 142, 143, 143, 144, 146, 145, 146, 148, 146, 148, 150, 147, 149, 151, 147, 149, 151, 147, 148, 150, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 147, 148, 150, 136, 137, 139, 98, 95, 95, 116, 115, 116, 169, 169, 171, 175, 175, 176, 174, 174, 175, 178, 179, 181, 169, 168, 169, 133, 120, 114, 134, 116, 108, 148, 131, 123, 154, 140, 134, 156, 149, 147, 138, 126, 121, 75, 38, 20, 171, 157, 150, 225, 222, 220, 229, 227, 225, 236, 236, 236, 242, 243, 243, 242, 243, 243, 193, 184, 180, 150, 141, 138, 179, 180, 181, 184, 184, 184, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 146, 147, 149, 141, 142, 144, 97, 94, 93, 76, 71, 69, 80, 75, 73, 82, 78, 76, 85, 81, 79, 93, 90, 88, 98, 95, 93, 102, 99, 98, 105, 103, 102, 112, 111, 111, 119, 119, 118, 123, 122, 122, 125, 125, 125, 129, 128, 129, 135, 135, 136, 138, 138, 139, 140, 140, 142, 142, 143, 144, 145, 146, 148, 147, 148, 150, 147, 149, 151, 147, 148, 151, 147, 148, 150, 147, 148, 150, 146, 147, 149, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 144, 145, 147, 144, 145, 147, 145, 146, 148, 139, 140, 142, 99, 96, 96, 119, 118, 119, 171, 172, 173, 175, 175, 176, 174, 174, 175, 174, 174, 175, 175, 176, 177, 179, 180, 182, 171, 171, 172, 162, 159, 159, 167, 166, 167, 176, 177, 179, 174, 174, 175, 156, 150, 148, 142, 131, 127, 138, 124, 117, 141, 125, 118, 145, 129, 121, 160, 147, 140, 159, 146, 141, 151, 142, 139, 174, 175, 176, 176, 177, 178, 184, 184, 184, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 155, 145, 146, 148, 145, 146, 148, 146, 147, 149, 143, 144, 146, 116, 115, 114, 113, 112, 111, 116, 115, 115, 121, 120, 120, 127, 127, 128, 134, 134, 135, 138, 138, 140, 140, 141, 142, 142, 143, 145, 144, 145, 147, 146, 148, 150, 147, 148, 150, 147, 148, 151, 147, 149, 151, 147, 148, 150, 147, 148, 150, 146, 147, 149, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 144, 145, 147, 144, 145, 147, 144, 145, 147, 144, 145, 147, 143, 145, 147, 143, 144, 146, 143, 144, 146, 144, 145, 147, 144, 145, 147, 145, 147, 149, 147, 149, 152, 149, 152, 155, 151, 154, 157, 152, 156, 159, 145, 150, 154, 110, 111, 114, 133, 135, 138, 178, 181, 183, 175, 177, 179, 174, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 175, 176, 175, 176, 177, 175, 175, 176, 174, 174, 175, 174, 175, 176, 178, 179, 180, 178, 180, 181, 176, 178, 179, 174, 174, 175, 169, 169, 169, 162, 160, 160, 168, 168, 168, 176, 177, 178, 174, 175, 176, 176, 176, 176, 184, 184, 184, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 144, 145, 147, 144, 145, 147, 145, 146, 149, 147, 148, 150, 147, 149, 151, 147, 148, 150, 147, 148, 150, 146, 147, 149, 146, 147, 149, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 144, 145, 147, 144, 145, 147, 144, 145, 147, 144, 145, 147, 143, 144, 146, 143, 145, 147, 143, 145, 147, 144, 146, 149, 146, 148, 150, 148, 150, 153, 150, 153, 157, 151, 155, 159, 153, 157, 161, 156, 160, 165, 161, 165, 170, 162, 166, 171, 164, 168, 171, 164, 166, 169, 164, 163, 163, 167, 162, 159, 167, 158, 153, 167, 154, 146, 166, 150, 139, 153, 129, 113, 128, 106, 93, 148, 131, 121, 170, 157, 148, 169, 163, 159, 172, 172, 173, 175, 178, 182, 176, 180, 184, 176, 179, 183, 175, 179, 182, 175, 177, 179, 175, 175, 177, 174, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 174, 175, 174, 175, 176, 175, 175, 177, 174, 175, 176, 174, 174, 175, 174, 174, 175, 175, 175, 176, 184, 184, 186, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 153, 155, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 145, 146, 148, 144, 146, 148, 144, 145, 147, 144, 145, 147, 144, 145, 148, 143, 145, 148, 144, 146, 148, 144, 146, 149, 145, 147, 150, 146, 149, 152, 147, 151, 155, 147, 151, 155, 148, 152, 156, 151, 156, 160, 154, 159, 163, 155, 160, 165, 157, 161, 165, 157, 161, 164, 159, 161, 164, 162, 162, 164, 165, 163, 163, 168, 165, 164, 167, 162, 159, 165, 154, 148, 165, 148, 137, 164, 144, 130, 163, 139, 122, 162, 133, 114, 160, 126, 103, 155, 114, 86, 151, 102, 68, 149, 92, 53, 147, 86, 42, 147, 83, 38, 145, 79, 32, 147, 77, 27, 126, 66, 25, 81, 44, 26, 92, 50, 27, 141, 77, 34, 150, 86, 41, 149, 95, 57, 152, 111, 83, 158, 128, 107, 162, 138, 121, 165, 146, 135, 167, 158, 153, 172, 169, 168, 173, 173, 174, 174, 177, 180, 176, 180, 183, 176, 179, 183, 176, 179, 182, 175, 177, 179, 174, 175, 177, 174, 175, 176, 174, 174, 175, 174, 174, 175, 174, 174, 175, 175, 175, 176, 185, 185, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 153, 154, 156, 146, 149, 153, 147, 150, 154, 148, 152, 156, 147, 152, 156, 149, 154, 158, 152, 156, 160, 153, 157, 161, 154, 157, 160, 155, 157, 159, 156, 156, 156, 157, 156, 155, 161, 158, 157, 161, 156, 153, 160, 150, 144, 160, 145, 135, 160, 141, 128, 160, 138, 123, 161, 135, 118, 161, 132, 112, 159, 126, 104, 155, 117, 90, 153, 108, 77, 154, 103, 68, 152, 99, 62, 150, 94, 55, 148, 90, 49, 146, 84, 41, 144, 79, 33, 144, 75, 27, 143, 74, 25, 142, 73, 24, 142, 72, 23, 143, 73, 24, 144, 75, 26, 146, 77, 29, 148, 80, 33, 148, 82, 36, 150, 85, 40, 154, 90, 47, 162, 97, 53, 137, 82, 46, 100, 57, 32, 79, 46, 32, 113, 63, 32, 146, 79, 33, 145, 77, 30, 147, 77, 27, 149, 77, 26, 149, 78, 28, 148, 79, 30, 148, 83, 38, 150, 91, 50, 151, 97, 60, 152, 107, 75, 157, 123, 100, 162, 136, 119, 164, 145, 133, 168, 160, 156, 173, 171, 171, 174, 175, 177, 175, 179, 183, 176, 179, 182, 175, 177, 180, 176, 177, 178, 184, 184, 185, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 170, 169, 168, 164, 149, 140, 161, 146, 135, 154, 136, 124, 152, 129, 113, 154, 123, 101, 154, 116, 90, 152, 109, 79, 153, 103, 69, 153, 101, 65, 152, 98, 60, 151, 94, 55, 150, 90, 49, 148, 86, 42, 146, 81, 36, 145, 77, 30, 145, 76, 27, 144, 75, 26, 143, 73, 24, 142, 72, 23, 142, 72, 22, 143, 73, 24, 144, 74, 25, 144, 75, 27, 145, 78, 30, 148, 82, 35, 151, 85, 39, 153, 88, 43, 156, 91, 47, 157, 94, 51, 161, 99, 57, 167, 106, 66, 174, 115, 75, 181, 121, 82, 186, 126, 88, 188, 129, 91, 191, 132, 94, 193, 135, 98, 196, 138, 101, 199, 141, 105, 202, 144, 108, 204, 144, 107, 165, 105, 65, 83, 47, 29, 80, 47, 32, 88, 51, 32, 93, 53, 32, 98, 56, 32, 107, 61, 32, 120, 67, 33, 131, 72, 34, 135, 74, 33, 140, 75, 31, 144, 77, 30, 148, 78, 28, 149, 77, 27, 149, 78, 28, 149, 79, 30, 149, 85, 39, 151, 94, 53, 152, 102, 66, 155, 119, 94, 163, 143, 130, 168, 158, 152, 172, 169, 168, 185, 186, 188, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 151, 125, 109, 102, 55, 27, 100, 55, 29, 104, 56, 27, 120, 63, 26, 145, 76, 27, 146, 76, 27, 144, 74, 25, 143, 74, 25, 143, 74, 25, 143, 75, 27, 144, 76, 29, 146, 79, 32, 149, 83, 37, 151, 86, 41, 154, 89, 45, 156, 92, 48, 158, 95, 52, 161, 100, 58, 169, 107, 67, 174, 113, 72, 177, 116, 76, 181, 120, 81, 184, 124, 86, 188, 129, 92, 194, 135, 98, 197, 138, 101, 198, 140, 103, 200, 142, 105, 201, 143, 107, 201, 143, 107, 201, 143, 107, 198, 140, 103, 195, 137, 100, 193, 134, 97, 190, 131, 93, 187, 128, 89, 184, 124, 86, 178, 118, 78, 171, 111, 70, 168, 106, 65, 167, 105, 63, 159, 95, 52, 116, 65, 32, 98, 56, 32, 92, 53, 32, 87, 50, 32, 80, 47, 32, 77, 45, 32, 77, 45, 32, 79, 46, 32, 82, 48, 32, 85, 49, 32, 91, 52, 32, 101, 58, 32, 108, 61, 33, 114, 64, 33, 124, 69, 33, 133, 73, 32, 137, 74, 31, 142, 75, 29, 147, 76, 26, 149, 79, 29, 151, 84, 37, 150, 89, 45, 170, 145, 127, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 165, 135, 115, 122, 67, 32, 137, 76, 34, 144, 80, 35, 148, 81, 35, 147, 81, 35, 148, 83, 37, 164, 102, 60, 171, 109, 69, 173, 112, 72, 178, 118, 79, 183, 124, 86, 188, 130, 93, 193, 135, 98, 196, 137, 101, 196, 138, 101, 197, 139, 102, 198, 139, 103, 198, 140, 103, 198, 139, 103, 197, 139, 102, 196, 137, 100, 191, 133, 96, 188, 129, 92, 184, 125, 87, 181, 121, 82, 178, 118, 78, 176, 115, 75, 173, 112, 71, 169, 108, 67, 162, 101, 59, 157, 95, 52, 153, 89, 45, 149, 85, 41, 149, 83, 38, 147, 82, 36, 146, 80, 35, 145, 79, 33, 144, 78, 32, 144, 77, 31, 144, 78, 31, 144, 78, 31, 146, 79, 33, 150, 83, 35, 149, 82, 35, 146, 80, 35, 143, 79, 34, 133, 74, 34, 121, 68, 33, 112, 63, 33, 106, 60, 33, 98, 56, 32, 89, 52, 32, 85, 49, 32, 81, 47, 32, 78, 46, 32, 76, 45, 32, 77, 45, 32, 80, 47, 32, 83, 48, 32, 87, 50, 32, 97, 55, 32, 108, 61, 32, 117, 64, 31, 142, 76, 30, 170, 155, 144, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 240, 236, 233, 181, 147, 123, 159, 109, 76, 151, 91, 50, 146, 81, 37, 147, 81, 34, 154, 89, 44, 180, 119, 79, 179, 116, 76, 178, 116, 75, 177, 114, 73, 172, 110, 69, 169, 106, 65, 165, 102, 60, 161, 99, 57, 158, 95, 53, 158, 94, 51, 156, 92, 49, 155, 91, 47, 153, 89, 44, 152, 87, 42, 150, 85, 40, 148, 83, 38, 146, 80, 35, 144, 79, 33, 145, 79, 32, 144, 78, 32, 144, 78, 31, 144, 77, 31, 144, 77, 31, 145, 78, 31, 145, 79, 32, 146, 79, 33, 146, 80, 34, 146, 80, 34, 147, 80, 34, 147, 81, 35, 147, 81, 35, 147, 81, 35, 147, 81, 35, 147, 81, 35, 147, 81, 35, 147, 81, 35, 148, 82, 35, 149, 82, 35, 148, 82, 35, 149, 82, 35, 152, 84, 36, 152, 83, 35, 152, 84, 36, 154, 84, 36, 150, 82, 35, 145, 80, 35, 143, 79, 36, 137, 76, 34, 130, 72, 33, 121, 68, 33, 115, 65, 34, 107, 60, 32, 102, 58, 32, 99, 57, 33, 95, 55, 33, 96, 56, 33, 106, 69, 48, 175, 159, 150, 244, 244, 244, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 241, 238, 235, 230, 220, 213, 214, 201, 191, 209, 190, 177, 197, 176, 161, 191, 164, 145, 174, 140, 116, 162, 119, 89, 159, 110, 75, 153, 100, 64, 152, 94, 53, 146, 84, 42, 144, 78, 32, 147, 80, 33, 147, 80, 33, 148, 81, 33, 147, 80, 33, 150, 82, 34, 148, 81, 34, 149, 82, 35, 149, 82, 35, 148, 81, 35, 148, 81, 35, 148, 81, 35, 148, 82, 35, 148, 82, 35, 150, 83, 36, 150, 83, 36, 148, 81, 35, 149, 82, 35, 151, 83, 36, 150, 83, 36, 148, 81, 35, 149, 82, 35, 151, 83, 36, 148, 81, 35, 148, 81, 35, 149, 82, 36, 147, 81, 35, 145, 81, 36, 148, 85, 42, 149, 90, 49, 155, 96, 56, 155, 99, 62, 153, 102, 66, 162, 111, 74, 164, 115, 80, 158, 114, 84, 169, 128, 99, 177, 139, 114, 177, 148, 128, 193, 165, 145, 199, 173, 154, 197, 174, 158, 197, 178, 165, 212, 192, 177, 212, 195, 183, 207, 195, 187, 219, 208, 200, 229, 218, 211, 241, 237, 234, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 251, 250, 250, 247, 245, 243, 237, 232, 229, 226, 215, 208, 210, 198, 189, 210, 191, 177, 195, 175, 161, 199, 171, 152, 180, 153, 135, 178, 140, 114, 164, 122, 92, 157, 108, 74, 156, 100, 62, 151, 93, 52, 153, 95, 54, 156, 102, 63, 159, 107, 70, 157, 110, 78, 160, 117, 88, 176, 134, 104, 180, 142, 116, 177, 146, 126, 187, 160, 142, 200, 171, 151, 199, 175, 158, 194, 176, 164, 210, 189, 174, 215, 196, 182, 209, 196, 187, 220, 209, 200, 231, 220, 213, 234, 227, 223, 240, 238, 236, 248, 245, 243, 249, 247, 246, 251, 250, 249, 254, 254, 253, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0]
