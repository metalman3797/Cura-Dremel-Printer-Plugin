import os
import os.path
import sys
import zipfile
import shutil  # For deleting plugin directories;
import stat    # For setting file permissions correctly;

from UM.i18n import i18nCatalog
from UM.Application import Application
from UM.Extension import Extension
from UM.Message import Message
from UM.Resources import Resources
from UM.Logger import Logger
from UM.Preferences import Preferences

from PyQt5.QtCore import pyqtSlot, QObject

catalog = i18nCatalog("cura")

##      This Extension runs in the background and sends several bits of information to the Ultimaker servers.
#       The data is only sent when the user in question gave permission to do so. All data is anonymous and
#       no model files are being sent (Just a SHA256 hash of the model).
class Dremel3D20(QObject, Extension):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.this_plugin_path = None
        self.local_meshes_path = None
        self.local_printer_def_path = None
        self.local_materials_path = None
        self.local_quality_path = None
        Logger.log("i", "Dremel 3D20 Plugin setting up")
        local_plugin_path = os.path.join(Resources.getStoragePath(Resources.Resources), "plugins")
        self.this_plugin_path=os.path.join(local_plugin_path,"Dremel3D20","Dremel3D20")
        local_meshes_paths = Resources.getAllPathsForType(Resources.Meshes)

        for path in local_meshes_paths:
            if os.path.isdir(path):
                self.local_meshes_path = path
        self.local_printer_def_path = Resources.getStoragePath(Resources.DefinitionContainers)
        self.local_materials_path = os.path.join(Resources.getStoragePath(Resources.Resources), "materials")
        self.local_quality_path = os.path.join(Resources.getStoragePath(Resources.Resources), "quality")

        # Check to see if the user had installed the plugin from an old version
        bExit = False
        for fil in self.oldVersionInstalled():
            Logger.log("i", "Dremel 3D20 Plugin found files from previous install: " + fil)
            message = Message(catalog.i18nc("@info:status", "Old Dremel IdeaBuilder 3D20 files detected.  Please delete "+ fil))
            message.show()
            bExit = True

        if bExit:
            return False

        # if something got messed up, set back to reasonable values
        if not self.isInstalled() and Preferences.getInstance().getValue("Dremel3D20/install_status") is "installed":
            Preferences.getInstance().setValue("Dremel3D20/install_status", "unknown")

        if self.isInstalled() and Preferences.getInstance().getValue("Dremel3D20/install_status") is "uninstalled":
            Preferences.getInstance().setValue("Dremel3D20/install_status", "installed")

        # Check the preferences to see if the user uninstalled the files -
        # if so don't automatically install them
        if Preferences.getInstance().getValue("Dremel3D20/install_status") is None and not self.isInstalled():
            Preferences.getInstance().addPreference("Dremel3D20/install_status", "unknown")
            Preferences.getInstance().writeToFile(Resources.getStoragePath(Resources.Preferences, Application.getInstance().getApplicationName() + ".cfg"))
            # if the user never installed the files, then automatically install it
            self.installPluginFiles()

        # check to see that the install succeeded - if so change the menu item options
        if os.path.isfile(os.path.join(self.local_printer_def_path,"Dremel3D20.def.json")):
            Logger.log("i", "Dremel 3D20 Plugin adding menu item for uninstallation")
            self.addMenuItem(catalog.i18nc("@item:inmenu", "Uninstall Dremel3D20 Printer"), self.uninstallPluginFiles)
        else:
            Logger.log("i", "Dremel 3D20 Plugin adding menu item for installation")
            self.addMenuItem(catalog.i18nc("@item:inmenu", "Install Dremel3D20 Printer"), self.installPluginFiles)

    def oldVersionInstalled(self):
        cura_dir=os.path.dirname(os.path.realpath(sys.argv[0]))
        dremelDefinitionFile=os.path.join(cura_dir,"resources","definitions","Dremel3D20.def.json")
        dremelMaterialFile=os.path.join(cura_dir,"resources","materials","dremel_pla.xml.fdm_material")
        dremelQualityFolder=os.path.join(cura_dir,"resources","quality","dremel_3d20")
        ret = []
        if os.path.isfile(dremelDefinitionFile):
            ret.append(dremelDefinitionFile)
        if os.path.isfile(dremelMaterialFile):
            ret.append(dremelMaterialFile)
        if os.path.isdir(dremelQualityFolder):
            ret.append(dremelQualityFolder)
        return ret


    def isInstalled(self):
        dremel3D20DefFile = os.path.join(self.local_printer_def_path,"Dremel3D20.def.json")
        dremelPLAfile = os.path.join(self.local_materials_path,"dremel_pla.xml.fdm_material")
        dremelQualityDir = os.path.join(self.local_quality_path,"dremel_3d20")
        if not os.path.isfile(dremel3D20DefFile):
            return False
        if not os.path.isfile(dremelPLAfile):
            return False
        if not os.path.isdir(dremelQualityDir):
            return False
        return True

    # Install the plugin files.
    def installPluginFiles(self):
        Logger.log("i", "Dremel 3D20 Plugin installing printer files")

        try:
            restartRequired = False
            zipdata = os.path.join(self.this_plugin_path,"Dremel3D20.zip")
            with zipfile.ZipFile(zipdata, "r") as zip_ref:
                for info in zip_ref.infolist():
                    Logger.log("i", "Dremel 3D20 Plugin: found in zipfile: " + info.filename )
                    folder = None
                    if info.filename.endswith(".json"):
                        folder = self.local_printer_def_path
                    elif info.filename.endswith("fdm_material"):
                        folder = self.local_materials_path
                    elif info.filename.endswith(".cfg"):
                        folder = self.local_quality_path
                    # TODO: figure out a way to install the stl file
                    # currently Cura doesn't have a local "meshes" folder
                    # and on windows writing to Program Files requires admin
                    # access
                    elif info.filename.endswith(".stl"):
                        folder = self.local_meshes_path

                    if folder is not None:
                        extracted_path = zip_ref.extract(info.filename, path = folder)
                        permissions = os.stat(extracted_path).st_mode
                        os.chmod(extracted_path, permissions | stat.S_IEXEC) #Make these files executable.
                        Logger.log("i", "Dremel 3D20 Plugin installing " + info.filename + " to " + extracted_path)
                        restartRequired = True

            if restartRequired and self.isInstalled():
                # only show the message if the user called this after having already uninstalled
                if Preferences.getInstance().getValue("Dremel3D20/install_status") is not "unknown":
                    message = Message(catalog.i18nc("@info:status", "Dremel 3D20 files installed.  Please Restart cura to complete installation"))
                    message.show()
                # either way, the files are now installed, so set the prefrences value
                Preferences.getInstance().setValue("Dremel3D20/install_status", "installed")
                Preferences.getInstance().writeToFile(Resources.getStoragePath(Resources.Preferences, Application.getInstance().getApplicationName() + ".cfg"))

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

        # remove the pla material file
        try:
            dremelPLAfile = os.path.join(self.local_materials_path,"dremel_pla.xml.fdm_material")
            if os.path.isfile(dremelPLAfile):
                Logger.log("i", "Dremel 3D20 Plugin removing dremel pla file from " + dremelPLAfile)
                os.remove(dremelPLAfile)
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
            Preferences.getInstance().setValue("Dremel3D20/install_status", "uninstalled")
            Preferences.getInstance().writeToFile(Resources.getStoragePath(Resources.Preferences, Application.getInstance().getApplicationName() + ".cfg"))
            message = Message(catalog.i18nc("@info:status", "Dremel 3D20 files uninstalled.  Please Restart cura to complete installation"))
            message.show()
