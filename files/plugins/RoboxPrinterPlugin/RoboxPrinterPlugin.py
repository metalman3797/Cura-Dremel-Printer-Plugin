####################################################################
# Dremel Ideabuilder 3D20, 3D40 & 3D45 plugin for Ultimaker Cura
# A plugin to enable Cura to write .g3drem files for
# the Dremel IdeaBuilder 3D20, 3D40 & 3D45
#
# Written by Tim Schoenmackers
# Based on the GcodeWriter plugin written by Ultimaker
#
# the GcodeWriter plugin source can be found here:
# https://github.com/Ultimaker/Cura/tree/master/plugins/GCodeWriter
#
# This plugin is released under the terms of the LGPLv3 or higher.
# The full text of the LGPLv3 License can be found here:
# https://github.com/timmehtimmeh/Cura-Dremel-Printer-Plugin/blob/master/LICENSE
####################################################################

import os  # for listdir
import platform  # for platform.system
import os.path  # for isfile and join and path
import sys
import zipfile  # For unzipping the printer files
import shutil  # For deleting plugin directories
import stat  # For setting file permissions correctly
import re  # For escaping characters in the settings.
import json
import copy
import struct
import time

from . import _version

from distutils.version import StrictVersion  # for upgrade installations

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
from cura.Snapshot import Snapshot

from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPixmap, QScreen, QColor, qRgb, QImageReader, QImage, QDesktopServices
from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt, QSize, pyqtSlot, QObject, QUrl, pyqtSlot

from . import G3DremHeader

catalog = i18nCatalog("cura")


class RoboxPrinterPlugin(QObject, MeshWriter, Extension):
    ######################################################################
    ##  The version number of this plugin
    ##  Please ensure that the version number is the same match in all
    ##  three of the following Locations:
    ##    1) below (this file)
    ##    2) .\plugin.json
    ##    3) ..\..\resources\package.json
    ######################################################################
    version = _version.__version__

    ######################################################################
    ##  Dictionary that defines how characters are escaped when embedded in
    #   g-code.
    #
    #   Note that the keys of this dictionary are regex strings. The values are
    #   not.
    ######################################################################
    escape_characters = {
        re.escape("\\"): "\\\\",  # The escape character.
        re.escape("\n"): "\\n",  # Newlines. They break off the comment.
        re.escape("\r"): "\\r"  # Carriage return. Windows users may need this for visualisation in their editors.
    }

    _setting_keyword = ";SETTING_"

    def __init__(self):
        super().__init__(add_to_recent_files=False)
        self._application = Application.getInstance()

        if self.getPreferenceValue("curr_version") is None:
            self.setPreferenceValue("curr_version", "0.0.0")

        self.this_plugin_path = os.path.join(Resources.getStoragePath(Resources.Resources), "plugins",
                                             "RoboxPrinterPlugin", "RoboxPrinterPlugin")

        Logger.log("i", "Robox Plugin setting up")
        # Prompt user to uninstall the old plugin, as this one supercedes it
        self.PromptToUninstallOldPluginFiles()

        needs_to_be_installed = False

        if self.isInstalled():
            Logger.log("i", "All Dremel files are installed")

            # if the version isn't the same, then force installation
            if not self.versionsMatch():
                Logger.log("i", "Robox Plugin detected that plugin needs to be upgraded")
                needs_to_be_installed = True

        else:
            Logger.log("i", "Some Robox Plugin files are NOT installed")
            needs_to_be_installed = True

        # if we need to install the files, then do so
        if needs_to_be_installed:
            self.installPluginFiles()

        self.addMenuItem(catalog.i18nc("@item:inmenu", "Preferences"), self.showPreferences)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Report Issue"), self.reportIssue)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Help "), self.showHelp)
        self.addMenuItem(catalog.i18nc("@item:inmenu", "Robox Printer Plugin Version " + RoboxPrinterPlugin.version),
                         self.openPluginWebsite)

        # finally save the cura.cfg file
        Logger.log("i", "Robox Plugin - Writing to " + str(
            Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg")))
        self._application.getPreferences().writeToFile(
            Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))

    ######################################################################
    ## Taking snapshot needs to be called on QT thread
    ## see this function for more info
    ## https://github.com/Ultimaker/Cura/blob/bcf180985d8503245822d420b420f826d0b2de72/plugins/CuraEngineBackend/CuraEngineBackend.py#L250-L261
    ######################################################################
    @call_on_qt_thread
    def _createSnapshot(self, w=80, h=60):
        # must be called from the main thread because of OpenGL
        Logger.log("d", "Creating thumbnail image with size (", w, ",", h, ")")
        self._snapshot = Snapshot.snapshot(width=w, height=h)
        Logger.log("d", "Thumbnail taken")

    def createPreferencesWindow(self):
        path = os.path.join(PluginRegistry.getInstance().getPluginPath(self.getPluginId()), "DremelPluginprefs.qml")
        Logger.log("i", "Creating RoboxPrinterPlugin preferences UI " + path)
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
        url = QUrl('https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/releases', QUrl.TolerantMode)
        if not QDesktopServices.openUrl(url):
            message = Message(catalog.i18nc("@info:status",
                                            "Robox Plugin could not navigate to https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/releases"))
            message.show()
        return

    ######################################################################
    ##  Show the help
    ######################################################################
    @pyqtSlot()
    def showHelp(self):
        url = os.path.join(PluginRegistry.getInstance().getPluginPath(self.getPluginId()), "README.pdf")
        Logger.log("i", "Robox Plugin opening help document: " + url)
        try:
            if not QDesktopServices.openUrl(QUrl("file:///" + url, QUrl.TolerantMode)):
                message = Message(catalog.i18nc("@info:status",
                                                "Robox Plugin could not open help document.\n Please download it from here: https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/raw/cura-3.4/README.pdf"))
                message.show()
        except:
            message = Message(catalog.i18nc("@info:status",
                                            "Robox Plugin could not open help document.\n Please download it from here: https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/raw/cura-3.4/README.pdf"))
            message.show()
        return

    ######################################################################
    ##  Open up the Github Issues Page
    ######################################################################
    @pyqtSlot()
    def reportIssue(self):
        Logger.log("i",
                   "Robox Plugin opening issue page: https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/issues/new")
        try:
            if not QDesktopServices.openUrl(
                    QUrl("https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/issues/new")):
                message = Message(catalog.i18nc("@info:status",
                                                "Robox Plugin could not open https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/issues/new please navigate to the page and report an issue"))
                message.show()
        except:
            message = Message(catalog.i18nc("@info:status",
                                            "Robox Plugin could not open https://github.com/Automaker-Unofficial/Cura-Robox-Printer-Plugin/issues/new please navigate to the page and report an issue"))
            message.show()
        return

    ######################################################################
    ## returns true if the versions match and false if they don't
    ######################################################################
    def versionsMatch(self):
        # get the currently installed plugin version number
        if self.getPreferenceValue("curr_version") is None:
            self.setPreferenceValue("curr_version", "0.0.0")
            # self._application.getPreferences().writeToFile(Resources.getStoragePath(Resources.Preferences, self._application.getApplicationName() + ".cfg"))

        installedVersion = self._application.getPreferences().getValue("RoboxPrinterPlugin/curr_version")

        if StrictVersion(installedVersion) == StrictVersion(RoboxPrinterPlugin.version):
            # if the version numbers match, then return true
            Logger.log("i",
                       "Robox Plugin versions match: " + installedVersion + " matches " + RoboxPrinterPlugin.version)
            return True
        else:
            Logger.log("i",
                       "Robox Plugin - The currently installed version: " + installedVersion + " doesn't match this version: " + RoboxPrinterPlugin.version)
            return False

    ######################################################################
    ## Check to see if the plugin files are all installed
    ## Return True if all files are installed, false if they are not
    ######################################################################
    def isInstalled(self):
        robox_dual_def_file = os.path.join(Resources.getStoragePathForType(Resources.Resources), "definitions",
                                           "CEL_Robox_Dual.def.json")
        robox_dual_extruder1 = os.path.join(Resources.getStoragePathForType(Resources.Resources), "extruders",
                                            "CEL_Robox_Dual_Extruder_1.def.json")
        robox_dual_extruder2 = os.path.join(Resources.getStoragePathForType(Resources.Resources), "extruders",
                                            "CEL_Robox_Dual_Extruder_2.def.json")

        # if some files are missing then return that this plugin as not installed
        if not os.path.isfile(robox_dual_def_file):
            Logger.log("i", "Robox Plugin - Robox Dual definition file is NOT installed ")
            return False
        if not os.path.isfile(robox_dual_extruder1):
            Logger.log("i", "Robox Plugin - Robox Dual extruder 1 file is NOT installed ")
            return False
        if not os.path.isfile(robox_dual_extruder2):
            Logger.log("i", "Robox Plugin - Robox Dual extruder 2 file is NOT installed ")
            return False

        # if everything is there, return True
        Logger.log("i", "Robox Plugin all files ARE installed")
        return True

    ######################################################################
    ##  Gets a value from Cura's preferences
    ######################################################################
    def getPreferenceValue(self, preferenceName):
        return self._application.getPreferences().getValue("RoboxPrinterPlugin/" + str(preferenceName))

    ######################################################################
    ## Sets a value to be stored in Cura's preferences file
    ######################################################################
    def setPreferenceValue(self, preferenceName, preferenceValue):
        if preferenceValue is None:
            return False
        name = "RoboxPrinterPlugin/" + str(preferenceName)
        Logger.log("i", "Robox Plugin: setting preference " + name + " to " + str(preferenceValue))
        if self.getPreferenceValue(preferenceName) is None:
            Logger.log("i", "Adding preference " + name);
            self._application.getPreferences().addPreference(name, preferenceValue)

        self._application.getPreferences().setValue(name, preferenceValue)
        return self.getPreferenceValue(preferenceName) == preferenceValue

    ######################################################################
    ## Install the plugin files from the included zip file.
    ######################################################################
    def installPluginFiles(self):
        Logger.log("i", "Robox Plugin installing printer files")

        try:
            resources_path = os.path.join(self.this_plugin_path, "../../../")
            zipdata = os.path.join(self.this_plugin_path, "resources.zip")
            Logger.log("i", "Robox Plugin: found zipfile: " + zipdata)
            with zipfile.ZipFile(zipdata, "r") as zip_ref:
                for info in zip_ref.infolist():
                    Logger.log("i", "Robox Plugin: found in zipfile: " + info.filename)
                    extracted_path = zip_ref.extract(info.filename, resources_path)
                    permissions = os.stat(extracted_path).st_mode
                    os.chmod(extracted_path, permissions | stat.S_IEXEC)  # Make these files executable.
                    Logger.log("i", "Robox Plugin installing " + info.filename + " to " + resources_path)

            if self.isInstalled():
                # The files are now installed, so set the curr_version prefrences value
                if not self.setPreferenceValue("curr_version", RoboxPrinterPlugin.version):
                    Logger.log("e", "Robox Plugin could not set curr_version preference ")

        except:  # Installing a new plugin should never crash the application so catch any random errors and show a message.
            Logger.logException("w", "An exception occurred in Robox Printer Plugin while installing the files")
            message = Message(catalog.i18nc("@warning:status",
                                            "Robox Printer Plugin experienced an error installing the necessary files"))
            message.show()

    ######################################################################
    ## Prompt the user that the old  plugin is installed
    ######################################################################
    def PromptToUninstallOldPluginFiles(self):
        # currently this will prompt the user to uninstall the old plugin, but not actually uninstall anything
        dremel3D20PluginDir = os.path.join(Resources.getStoragePath(Resources.Resources), "plugins", "Dremel3D20")
        if os.path.isdir(dremel3D20PluginDir):
            message = Message(catalog.i18nc("@warning:status",
                                            "Please uninstall the Robox old plugin.\n\t• The Robox Printer Plugin replaces the older Robox plugin.\n\t• Currently both are installed. "))
            message.show()

    ######################################################################
    ##  Performs the writing of the dremel header and gcode - for a technical
    ##  breakdown of the dremel g3drem file format see the following page:
    ##  https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/blob/master/README.md#technical-details-of-the-g3drem-file-format
    ######################################################################
    def write(self, stream, nodes, mode=MeshWriter.OutputMode.BinaryMode):
        try:
            if mode != MeshWriter.OutputMode.BinaryMode:
                Logger.log("e", "Robox Plugin does not support non-binary mode.")
                return False
            if stream is None:
                Logger.log("e", "Robox Plugin - Error writing - no output stream.")
                return False

            g3dremHeader = G3DremHeader.G3DremHeader()

            global_container_stack = self._application.getGlobalContainerStack()

            print_information = self._application.getPrintInformation()
            extruders = [global_container_stack]
            extruder = extruders[0]

            # get estimated length
            length = int(print_information.materialLengths[int(extruder.getMetaDataEntry("position", "0"))] * 1000)
            g3dremHeader.setMaterialLen(length)

            materialName = "PLA"
            # TODO: currently this gets the values set in the quality profile, however
            # it does not account for user quality changes
            active_machine_stack = self._application.getMachineManager().activeMachine
            if len(active_machine_stack.extruderList) > 0:
                currExtruder = active_machine_stack.extruderList[0]

                # set the material
                material = currExtruder.material
                materialName = material.getName()
                Logger.log("i", "Robox Plugin - active material is: " + str(materialName))
                if "ABS" in materialName:
                    g3dremHeader.setMaterialType(G3DremHeader.MaterialType.ABS)

                # set num shell layers
                numShells = currExtruder.getProperty("wall_line_count", "value")
                Logger.log("i", "Robox Plugin - num walls is: " + str(numShells))
                if numShells is None:
                    numShells = 3
                g3dremHeader.setNumShells(int(numShells))

                currQuality = currExtruder.quality
                # currQuality = currExtruder.qualityChanges
                # if currQuality.getId() == "empty_quality_changes":
                #     currQuality = currExtruder.quality
                #     Logger.log("i","Robox Plugin - no quality changes detected for profile "+currQuality.getName())
                # else:
                #     Logger.log("i","Robox Plugin - quality changes are detected for profile "+currQuality.getName())

                # set print print speed
                printSpeed = currQuality.getProperty("speed_print", "value")
                Logger.log("i", "Robox Plugin - print speed is: " + str(printSpeed))
                if printSpeed is None:
                    printSpeed = 50
                g3dremHeader.setPrintSpeed(int(printSpeed))

                # set print temperature in header
                extruderTemp = currQuality.getProperty("default_material_print_temperature", "value")
                Logger.log("i", "Robox Plugin - extruder temperature is: " + str(extruderTemp))
                if extruderTemp is None:
                    extruderTemp = 50
                g3dremHeader.setExtruderTemp(int(extruderTemp))

                # get infill percentage
                infillPct = currQuality.getProperty("infill_sparse_density", "value")
                Logger.log("i", "Robox Plugin - infill percentage is: " + str(infillPct))
                if infillPct is None:
                    infillPct = 20
                g3dremHeader.setInfillPct(int(infillPct))

                # set the bed temperature
                bedTemp = currQuality.getProperty("material_bed_temperature", "value")
                if bedTemp is None:
                    bedTemp = 60
                g3dremHeader.setBedTemperature(int(bedTemp))

            bHeatedBed = False
            active_printer = global_container_stack.definition.getName()
            if active_printer == "Dremel3D45":
                bHeatedBed = True
            bSupportEnabled = active_machine_stack.getProperty("support_enable", "value")

            # set the information flag bits
            g3dremHeader.setFlags(leftExtruderExists=False, heatedBed=bHeatedBed, supportEnabled=bSupportEnabled)

            # get the estimated number of seconds that the print will take
            seconds = int(print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))
            g3dremHeader.setEstimatedTime(seconds)

            # set layer height
            g3dremHeader.setLayerHeight(int(global_container_stack.getProperty("layer_height", "value") * 1000))

            # finally, write the header to the file
            if not g3dremHeader.writeHeader(stream):
                Logger.log("e", "Robox Plugin - Error Writing Dremel Header.")
                return False
            Logger.log("i", "Robox Plugin - Finished Writing Dremel Header.")

            # now that the header is written, write the ascii encoded gcode

            # write a comment in the gcode with  the Plugin name, version number, printer, and quality name to the g3drem file
            quality_name = global_container_stack.quality.getName()
            if quality_name is None:
                quality_name = "unknown"

            # warn the user if they save out a PETG file at ultra quality
            if ("Ultra" in quality_name) and ("PETG" in materialName) and ("3D45" in active_printer):
                message = Message(catalog.i18nc("@warning:status",
                                                "WARNING: Printing Ultra quality with Dremel PETG is currently unreliable"))
                message.show()

            stream.write(
                "\n;Cura-Dremel-Printer-Plugin version {}\n;Printing on: {}\n;Using material: \"{}\"\n;Quality: \"{}\"\n".format(
                    RoboxPrinterPlugin.version, active_printer, materialName, quality_name).encode())

            # after the plugin info - write the gcode from Cura
            active_build_plate = self._application.getMultiBuildPlateModel().activeBuildPlate
            scene = self._application.getController().getScene()
            if not hasattr(scene, "gcode_dict"):
                message = Message(catalog.i18nc("@warning:status", "Please prepare G-code before exporting."))
                message.show()
                return False

            gcode_dict = getattr(scene, "gcode_dict")
            gcode_list = gcode_dict.get(active_build_plate, None)
            # Logger.log("i", "Got active build plate")
            if gcode_list is not None:
                has_settings = False
                for gcode in gcode_list:
                    try:
                        if gcode[:len(self._setting_keyword)] == self._setting_keyword:
                            has_settings = True
                        stream.write(gcode.encode())
                    except:
                        Logger.logException("w", "Robox Plugin - Error writing gcode to file.")
                        return False
                try:
                    ## Serialise the current container stack and put it at the end of the file.
                    if not has_settings:
                        settings = self._serialiseSettings(global_container_stack)
                        stream.write(settings.encode())
                    Logger.log("i", "Done writing settings - write complete")
                    return True
                except Exception as e:
                    Logger.logException("w", "Exception caught while serializing settings.")
                    Logger.log("d", sys.exc_info()[:2])
            message = Message(catalog.i18nc("@warning:status", "Please prepare G-code before exporting."))
            message.show()
            return False
        except Exception as e:
            Logger.logException("w", "Exception caught while writing gcode.")
            Logger.log("d", sys.exc_info()[:2])
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

        prefix = self._setting_keyword + str(RoboxPrinterPlugin.version) + " "  # The prefix to put before each line.
        prefix_length = len(prefix)

        quality_type = stack.quality.getMetaDataEntry("quality_type")
        container_with_profile = stack.qualityChanges
        machine_definition_id_for_quality = ContainerTree.getInstance().machines[
            stack.definition.getId()].quality_definition
        if container_with_profile.getId() == "empty_quality_changes":
            # If the global quality changes is empty, create a new one
            quality_name = container_registry.uniqueName(stack.quality.getName())
            quality_id = container_registry.uniqueName(
                (stack.definition.getId() + "_" + quality_name).lower().replace(" ", "_"))
            container_with_profile = InstanceContainer(quality_id)
            container_with_profile.setName(quality_name)
            container_with_profile.setMetaDataEntry("type", "quality_changes")
            container_with_profile.setMetaDataEntry("quality_type", quality_type)
            if stack.getMetaDataEntry(
                    "position") is not None:  # For extruder stacks, the quality changes should include an intent category.
                container_with_profile.setMetaDataEntry("intent_category",
                                                        stack.intent.getMetaDataEntry("intent_category", "default"))
            container_with_profile.setDefinition(machine_definition_id_for_quality)
            container_with_profile.setMetaDataEntry("setting_version",
                                                    stack.quality.getMetaDataEntry("setting_version"))

        flat_global_container = self._createFlattenedContainerInstance(stack.userChanges, container_with_profile)
        # If the quality changes is not set, we need to set type manually
        if flat_global_container.getMetaDataEntry("type", None) is None:
            flat_global_container.setMetaDataEntry("type", "quality_changes")

        # Ensure that quality_type is set. (Can happen if we have empty quality changes).
        if flat_global_container.getMetaDataEntry("quality_type", None) is None:
            flat_global_container.setMetaDataEntry("quality_type",
                                                   stack.quality.getMetaDataEntry("quality_type", "normal"))

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
                quality_id = container_registry.uniqueName(
                    (stack.definition.getId() + "_" + quality_name).lower().replace(" ", "_"))
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
                flat_extruder_quality.setMetaDataEntry("quality_type",
                                                       extruder.quality.getMetaDataEntry("quality_type", "normal"))

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
        pattern = re.compile("|".join(RoboxPrinterPlugin.escape_characters.keys()))

        # Perform the replacement with a regular expression.
        escaped_string = pattern.sub(lambda m: RoboxPrinterPlugin.escape_characters[re.escape(m.group(0))], json_string)

        # Introduce line breaks so that each comment is no longer than 80 characters. Prepend each line with the prefix.
        result = ""
        # Lines have 80 characters, so the payload of each line is 80 - prefix.
        for pos in range(0, len(escaped_string), 80 - prefix_length):
            result += prefix + escaped_string[pos: pos + 80 - prefix_length] + "\n"
        return result
