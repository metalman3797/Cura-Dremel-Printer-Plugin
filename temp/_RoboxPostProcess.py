from ..Script import Script
import re

# from cura.Settings.ExtruderManager import ExtruderManager


class _RoboxPostProcess(Script):
    def __init__(self):
        super().__init__()
        self.t0Pattern = re.compile("T0(\s|$)")
        self.t1Pattern = re.compile("T1(\s|$)")
        self.sTemperaturePattern = re.compile("S\d+")
        self.tTemperaturePattern = re.compile("T\d+")
        self.retractPattern = re.compile("E-\d+")
        self.forwardPattern = re.compile("E\d+")

    def getSettingDataString(self):
        return """{
            "name":"_RoboxPostProcess",
            "key": "_RoboxPostProcess",
            "metadata": {},
            "version": 2,
            "settings": {
                "robox_profile":
                {
                    "label": "Profile",
                    "description": "Various nozzles and heads Robox has",
                    "type": "enum",
                    "options": {
                        "singleX":"Single X",
                        "quick_fill":"Quick Fill",
                        "dual":"Dual Material"
                    },
                    "default_value": "dual"
                },
                "robox_close_valve":
                {
                    "label": "Close valve on retracts",
                    "description": "Should needle valves be closed on retracts",
                    "type": "bool",
                    "default_value": false
                }
            }
        }"""

    def execute(self, data: list):

        version = "0.2"

        self.roboxProfile = self.getSettingValueByKey("robox_profile")
        self.roboxCloseValve = self.getSettingValueByKey("robox_close_valve")

        self.selectedTool = ""
        self.valveClosed = True

        index = 0
        for active_layer in data:

            self.output = ""
            # if index == 0:
            self.output += "; Selected robox profile: " + self.roboxProfile + ", close valve \"" + str(self.roboxCloseValve) + "\"\n"
            self.output += "; version " + version + "\n"

            lines = active_layer.split("\n")
            for line in lines:
                commentIndex = line.find(";")
                if commentIndex >= 0:
                    comment = line[commentIndex + 1:]
                    line = line[0:commentIndex]
                else:
                    comment = ""

                if self.roboxProfile == "dual":
                    self.dualRobox(line, comment)
                elif self.roboxProfile == "quick_fill":
                    self.QuickFillRobox(line, comment)
                elif self.roboxProfile == "singleX":
                    # Code for single nozzle goes in here
                    self.output += line + "\n"

            data[index] = self.output
            index += 1
        return data

    def dualRobox(self, line, comment):
	
        toolForLine = self.selectedTool
        if re.search(self.t0Pattern, line):
            if toolForLine != "T0":  # Tool change
                if not line.startswith("T0"):
                    line = line.replace(" T0", "") + " ; removed T0 from the middle"  # Remove tool change
                    toolForLine = "T0"
                else:
                    self.selectedTool = "T0"
                    toolForLine = self.selectedTool
            else:  # No tool changes
                if line.startswith("T0"):  # This is solitary T0 - so remove it
                    comment = comment + " Duplicate T0"
                    self.selectedTool = "T0"
                    toolForLine = self.selectedTool
                else:
                    line = line.replace("T0 ", "")
                    comment = comment + " removed T0 from the middle (no tool change)"  # Remove T0 in the middle of the command as no tool change

        elif re.search(self.t1Pattern, line):
            if toolForLine != "T1":  # Tool change
                if not line.startswith("T1"):
                    # output += "T1 ; forced T1 \n"  # Line is not T1 so we need to add T0 before this line to initiate tool change
                    line = line.replace(" T1", "")
                    comment = comment + " removed T1 from the middle"  # Remove tool change
                    toolForLine = "T1"
                else:
                    self.selectedTool = "T1"
                    toolForLine = self.selectedTool
            else:  # No tool changes
                if line.startswith("T1"):  # This is solitary T1 - so remove it
                    comment = comment + " Duplicate T1"
                    self.selectedTool = "T1"
                    toolForLine = self.selectedTool
                else:
                    line = line.replace("T1 ", "")
                    comment = comment + " removed T1 from the middle (no tool change)"  # Remove T1 in the middle of the command as no tool change

        if toolForLine == "T1" and ("M103" in line or "M104" in line or "M109" in line):
            hasS = re.search(self.sTemperaturePattern, line)
            hasT = re.search(self.tTemperaturePattern, line)

            # There is 'Sxxx' in the line and second tool is selected and line doesn't contain both
            if hasS and not hasT:
                line = line.replace("S", "T")  # Replace "Sxxx" with "Txxx"

        if line.startswith("M109 "):
            line = line +"\n" +"M109 \n" 

        if self.roboxCloseValve:
            if re.search(self.retractPattern, line):  # There is 'E-xxx" in the line - add closing valve
                if toolForLine == "T1":
                    line = line.replace("E", "B0 E")  # Close valve and use second extruder
                elif toolForLine == "T0":
                    line = line.replace("E", "B0 D")  # Close valve
            if re.search(self.forwardPattern, line):  # There is 'Exxx' in the line - add opening valve
                if toolForLine == "T1":
                    line = line.replace("E", "B1 E")  # Open valve and use second extruder
                elif toolForLine == "T0":
                    line = line.replace("E", "B1 D")  # Open valve

        else:  # No close valve handling needed
            if toolForLine == "T0":  # We are using second tool - so we need second extruder as well
                if re.search(self.forwardPattern, line) or re.search(self.retractPattern, line):
                    line = line.replace("E", "B1 D")
            else:
                if re.search(self.forwardPattern, line) or re.search(self.retractPattern, line):
                    line = line.replace("E", "B1 E")

        if comment != "":
            self.output += line + " ;" + comment + "\n"
        else:
            self.output += line + "\n"

    def QuickFillRobox(self, line, comment):

        toolForLine = self.selectedTool
        if re.search(self.t0Pattern, line):
            if toolForLine != "T0":  # Tool change
                if not line.startswith("T0"):
                    line = line.replace(" T0", "") + " ; removed T0 from the middle"  # Remove tool change
                    toolForLine = "T0"
                else:
                    self.selectedTool = "T0"
                    toolForLine = self.selectedTool
            else:  # No tool changes
                if line.startswith("T0"):  # This is solitary T0 - so remove it
                    comment = comment + "T0"
                    self.selectedTool = "T0"
                    toolForLine = self.selectedTool
                else:
                    line = line.replace("T0 ", "")
                    comment = comment + " removed T0 from the middle (no tool change)"  # Remove T0 in the middle of the command as no tool change

        elif re.search(self.t1Pattern, line):
            if toolForLine != "T1":  # Tool change
                if not line.startswith("T1"):
                    # output += "T1 ; forced T1 \n"  # Line is not T1 so we need to add T0 before this line to initiate tool change
                    line = line.replace(" T1", "")
                    comment = comment + " removed T1 from the middle"  # Remove tool change
                    toolForLine = "T1"
                else:
                    self.selectedTool = "T1"
                    toolForLine = self.selectedTool
            else:  # No tool changes
                if line.startswith("T1"):  # This is solitary T1 - so remove it
                    comment = comment + "T1"
                    self.selectedTool = "T1"
                    toolForLine = self.selectedTool
                else:
                    line = line.replace("T1 ", "")
                    comment = comment + " removed T1 from the middle (no tool change)"  # Remove T1 in the middle of the command as no tool change

        if toolForLine == "T1" and ("M103" in line or "M104" in line or "M109" in line):
            hasS = re.search(self.sTemperaturePattern, line)
            hasT = re.search(self.tTemperaturePattern, line)

            # There is 'Sxxx' in the line and second tool is selected and line doesn't contain both
            if hasS and not hasT:
                line = line.replace("S", "T")  # Replace "Sxxx" with "Txxx"

        if line.startswith("M109 "):
            line = line +"\n" +"M109 \n" 

        if self.roboxCloseValve:
            if re.search(self.retractPattern, line):  # There is 'E-xxx" in the line - add closing valve
                if toolForLine == "T1":
                    line = line.replace("E", "B0 E")  # Close valve and use second extruder
                elif toolForLine == "T0":
                    line = line.replace("E", "B0 E")  # Close valve
            if re.search(self.forwardPattern, line):  # There is 'Exxx' in the line - add opening valve
                if toolForLine == "T1":
                    line = line.replace("E", "B1 E")  # Open valve and use second extruder
                elif toolForLine == "T0":
                    line = line.replace("E", "B1 E")  # Open valve

        else:  # No close valve handling needed
            if toolForLine == "T0":  # We are using second tool - so we need second extruder as well
                if re.search(self.forwardPattern, line) or re.search(self.retractPattern, line):
                    line = line.replace("E", "B1 E")
            else:
                if re.search(self.forwardPattern, line) or re.search(self.retractPattern, line):
                    line = line.replace("E", "B1 E")

        if comment != "":
            self.output += line + " ;" + comment + "\n"
        else:
            self.output += line + "\n"		