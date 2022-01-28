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

    minimumWidth: Math.floor(UM.Theme.getSize("toolbox_action_button").width * 2.5+3*UM.Theme.getSize("default_margin").width)
    minimumHeight: Math.floor(Math.max(120 * screenScaleFactor,120))
    title: "Robox Plugin Preferences"

    function checkBooleanVals(val) {
        if(val == "True") {
            return true
        } else if(val == undefined || val == "False" ) {
            return false
        } else {
            return val
        }
    }

    function checkInstallStatus(prefVal) {
        if(prefVal == "installed") {
            return true
        } else if(val == "uninstalled" || val == undefined ) {
            return false
        } else {
            return val
        }
    }


    ColumnLayout {
        id: colLayout
        anchors.fill: parent
        anchors.margins: margin

        Row {
            id: buttonRow
            spacing: UM.Theme.getSize("default_margin").width
            width: Math.round(parent.width)

            Button
            {
                id: button1
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
} // end UM.Dialog
