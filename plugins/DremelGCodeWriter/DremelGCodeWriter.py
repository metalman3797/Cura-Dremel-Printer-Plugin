# Based on the GcodeWriter plugin written by Ultimaker
# the original source can be found here: https://github.com/Ultimaker/Cura/tree/master/plugins/GCodeWriter

from UM.Mesh.MeshWriter import MeshWriter
from UM.Logger import Logger
from UM.Application import Application
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Qt.Duration import DurationFormat
from cura.Settings.ExtruderManager import ExtruderManager

import re #For escaping characters in the settings.
import json
import copy
import struct
import os

##  Writes a .g3drem file.

class DremelGCodeWriter(MeshWriter):
    ##  The file format version of the serialised g-code.
    version = 3

    ##  Dictionary that defines how characters are escaped when embedded in
    #   g-code.
    #
    #   Note that the keys of this dictionary are regex strings. The values are
    #   not.
    escape_characters = {
        re.escape("\\"): "\\\\",  # The escape character.
        re.escape("\n"): "\\n",   # Newlines. They break off the comment.
        re.escape("\r"): "\\r"    # Carriage return. Windows users may need this for visualisation in their editors.
    }

    def __init__(self):
        super().__init__()

    ##  Performs the writing of the dremel header and gcode

    def write(self, stream, nodes, mode = MeshWriter.OutputMode.BinaryMode):
        if mode != MeshWriter.OutputMode.BinaryMode:
            Logger.log("e", "GCode Writer does not support non-binary mode.")
            return False

        #write the g3drem header
        stream.write("g3drem 1.0      ".encode())
		#write 3 magic numbers
        stream.write(struct.pack('<lll',58,14512,14512))
		
		#get the filament length and number of seconds
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        print_information = Application.getInstance().getPrintInformation()
        extruders = [global_container_stack]
        extruder = extruders[0]
        length = int(print_information.materialLengths[int(extruder.getMetaDataEntry("position", "0"))]*1000)
        #write the 4 byte number of seconds and the 4 byte filament length
        seconds = int(print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))
        stream.write(struct.pack('<ll',seconds,length))		#write 3 magic numbers
		#write some more magic numbers
        stream.write(struct.pack('<lllllh',0,1,196633,100,220,-255))

        #now write the bitmap
        bmpfilepath = os.path.normpath(os.getcwd()+"/plugins/DremelOutputDevice/cura80x60.bmp")
        with open(bmpfilepath,"rb") as bmp:
            bmpContents = bmp.read()
        stream.write(bmpContents)
		
        scene = Application.getInstance().getController().getScene()
        gcode_list = getattr(scene, "gcode_list")
        if gcode_list:
            for gcode in gcode_list:
                stream.write(gcode.encode())
            # Serialise the current container stack and put it at the end of the file.
            settings = self._serialiseSettings(Application.getInstance().getGlobalContainerStack())
            stream.write(settings.encode())
            return True

        return False

    ##  Create a new container with container 2 as base and container 1 written over it.
    def _createFlattenedContainerInstance(self, instance_container1, instance_container2):
        flat_container = InstanceContainer(instance_container2.getName())
        if instance_container1.getDefinition():
            flat_container.setDefinition(instance_container1.getDefinition())
        else:
            flat_container.setDefinition(instance_container2.getDefinition())
        flat_container.setMetaData(copy.deepcopy(instance_container2.getMetaData()))

        for key in instance_container2.getAllKeys():
            flat_container.setProperty(key, "value", instance_container2.getProperty(key, "value"))

        for key in instance_container1.getAllKeys():
            flat_container.setProperty(key, "value", instance_container1.getProperty(key, "value"))

        return flat_container


    ##  Serialises a container stack to prepare it for writing at the end of the
    #   g-code.
    #
    #   The settings are serialised, and special characters (including newline)
    #   are escaped.
    #
    #   \param settings A container stack to serialise.
    #   \return A serialised string of the settings.
    def _serialiseSettings(self, stack):
        prefix = ";SETTING_" + str(DremelGCodeWriter.version) + " "  # The prefix to put before each line.
        prefix_length = len(prefix)

        container_with_profile = stack.qualityChanges
        if not container_with_profile:
            Logger.log("e", "No valid quality profile found, not writing settings to GCode!")
            return ""

        flat_global_container = self._createFlattenedContainerInstance(stack.getTop(), container_with_profile)
        # If the quality changes is not set, we need to set type manually
        if flat_global_container.getMetaDataEntry("type", None) is None:
            flat_global_container.addMetaDataEntry("type", "quality_changes")

        # Ensure that quality_type is set. (Can happen if we have empty quality changes).
        if flat_global_container.getMetaDataEntry("quality_type", None) is None:
            flat_global_container.addMetaDataEntry("quality_type", stack.quality.getMetaDataEntry("quality_type", "normal"))

        serialized = flat_global_container.serialize()
        data = {"global_quality": serialized}

        for extruder in sorted(ExtruderManager.getInstance().getMachineExtruders(stack.getId()), key = lambda k: k.getMetaDataEntry("position")):
            extruder_quality = extruder.qualityChanges
            if not extruder_quality:
                Logger.log("w", "No extruder quality profile found, not writing quality for extruder %s to file!", extruder.getId())
                continue
            flat_extruder_quality = self._createFlattenedContainerInstance(extruder.getTop(), extruder_quality)
            # If the quality changes is not set, we need to set type manually
            if flat_extruder_quality.getMetaDataEntry("type", None) is None:
                flat_extruder_quality.addMetaDataEntry("type", "quality_changes")

            # Ensure that extruder is set. (Can happen if we have empty quality changes).
            if flat_extruder_quality.getMetaDataEntry("extruder", None) is None:
                flat_extruder_quality.addMetaDataEntry("extruder", extruder.getBottom().getId())

            # Ensure that quality_type is set. (Can happen if we have empty quality changes).
            if flat_extruder_quality.getMetaDataEntry("quality_type", None) is None:
                flat_extruder_quality.addMetaDataEntry("quality_type", extruder.quality.getMetaDataEntry("quality_type", "normal"))
            extruder_serialized = flat_extruder_quality.serialize()
            data.setdefault("extruder_quality", []).append(extruder_serialized)

        json_string = json.dumps(data)

        # Escape characters that have a special meaning in g-code comments.
        pattern = re.compile("|".join(DremelGCodeWriter.escape_characters.keys()))

        # Perform the replacement with a regular expression.
        escaped_string = pattern.sub(lambda m: DremelGCodeWriter.escape_characters[re.escape(m.group(0))], json_string)

        # Introduce line breaks so that each comment is no longer than 80 characters. Prepend each line with the prefix.
        result = ""

        # Lines have 80 characters, so the payload of each line is 80 - prefix.
        for pos in range(0, len(escaped_string), 80 - prefix_length):
            result += prefix + escaped_string[pos : pos + 80 - prefix_length] + "\n"
        return result
