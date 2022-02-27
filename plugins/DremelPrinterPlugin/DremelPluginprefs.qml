import QtQuick 2.1
import QtQuick.Controls 2.1
import QtQuick.Layouts 1.1
import QtQuick.Window 2.1
import QtQuick.Controls.Styles 1.1

import UM 1.1 as UM

UM.Dialog
{

    id: base
    property string installStatusText

    minimumWidth: Math.floor(UM.Theme.getSize("toolbox_action_button").width * 3.5 +3*UM.Theme.getSize("default_margin").width)
    minimumHeight: Math.floor(Math.max(280 * screenScaleFactor,280))
    title: "Dremel Plugin Preferences"

    function checkBooleanVals(val) {
        if(val == "True") {
            return true
        } else if(val == undefined || val == "False" ) {
            return false
        } else {
            return val
        }
    }

    function getIPAddress(val) {
        if(val == undefined)
        {
            return "XXX.XXX.XXX.XXX"
        }else
        {
            return val
        }
    }

    ColumnLayout {
        id: colLayout
        anchors.fill: parent
        anchors.margins: margin
        GroupBox {
            anchors.margins: margin
            spacing: UM.Theme.getSize("default_margin").width
            title: "General Preferences"
            width: Math.round(parent.width)
            ColumnLayout {
                height: UM.Theme.getSize("checkbox").height*2
                width: Math.round(parent.width)
                CheckBox {
                    id: screenshotCB
                    height: UM.Theme.getSize("checkbox").height
                    width: Math.round(parent.width)
                    text: "Select Screenshot Manually"
                    checked: checkBooleanVals(UM.Preferences.getValue("DremelPrinterPlugin/select_screenshot"))
                    onClicked: manager.setSelectScreenshot(checked)
                    ToolTip.timeout: 5000
                    ToolTip.visible: hovered
                    ToolTip.text: "Check this box to allow you when saving a\ng3drem file to manually select a screenshot\nfrom an image stored on your hard drive"
                } //end CheckBox

                Row {
                    id: buttonRow
                    spacing: UM.Theme.getSize("default_margin").width
                    width: Math.round(parent.width)

                    Button
                    {
                        id: openWebsiteButton
                        width: Math.floor(UM.Theme.getSize("toolbox_action_button").width * 1.25)
                        property int renderType: Text.NativeRendering
                        text: "Open plugin website"
                        onClicked: manager.openPluginWebsite()
                    } // end Button

                    Button
                    {
                        id: helpButton
                        width: Math.floor(UM.Theme.getSize("toolbox_action_button").width * 1.25)
                        property int renderType: Text.NativeRendering
                        text: "Help"
                        ToolTip.timeout: 1000
                        ToolTip.visible: hovered
                        ToolTip.text: "Open documentation"
                        onClicked: manager.showHelp()
                    } // end Button
                } // end Row
            } // end ColumnLayout
        } // end GroupBox
        GroupBox {
            width: Math.round(parent.width)
            spacing: UM.Theme.getSize("default_margin").width
            title: "Dremel 3D45 Camera"
            Row{
                Label
                {
                    text:"IP Address"
                    width: Math.floor(parent.width * 0.25)
                }
                TextField
                {
                    id: ipAddress
                    focus: true
                    text: getIPAddress(UM.Preferences.getValue("DremelPrinterPlugin/ip_address"))
                    width: Math.floor(UM.Theme.getSize("toolbox_action_button").width*1.5)
                    onAccepted: manager.SetIpAddress(text)
                    ToolTip.timeout: 1000
                    ToolTip.visible: hovered
                    ToolTip.text: "Enter the IP address of your Dremel Printer here in order to enable the camera view"
                    validator:RegExpValidator
                    {
                        regExp:/^(([01]?[0-9]?[0-9]|2([0-4][0-9]|5[0-5]))\.){3}([01]?[0-9]?[0-9]|2([0-4][0-9]|5[0-5]))$/
                    }
                }
                Button
                {
                    id: setIPButton
                    width: Math.floor(UM.Theme.getSize("toolbox_action_button").width)
                    property int renderType: Text.NativeRendering
                    text: "Set IP Address"
                    onClicked: manager.SetIpAddress(ipAddress.text)
                } // end Button
            } // end Row
        } // end GroupBox
    } // end ColumnLayout
} // end UM.Dialog
