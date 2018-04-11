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

    minimumWidth: (UM.Theme.getSize("modal_window_minimum").width * 0.5) | 0
    minimumHeight: (UM.Theme.getSize("modal_window_minimum").height * 0.25) | 0
    width: minimumWidth
    height: minimumHeight
    title: catalog.i18nc("@label", "Dremel 3D20 Plugin Preferences")

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


    Column {
      id: col1
      CheckBox {
          id: screenshotCB
          text: qsTr("Select Screenshot Manually")
          checked: checkBooleanVals(UM.Preferences.getValue("Dremel3D20/select_screenshot"))
          onClicked: manager.setSelectScreenshot(checked)
          ToolTip.timeout: 5000
          ToolTip.visible: hovered
          ToolTip.text: "Check this box to allow you when saving a g3drem file to\nmanually select a screenshot from an image stored on your\nhard drive"

      } //end CheckBox

      CheckBox {
        id: installCB
        text: "Are Dremel 3D20 Printer File Installed? "

        ToolTip.timeout: 5000
        ToolTip.visible: hovered
        ToolTip.text: "Uncheck this checkbox to uninstall the Dremel 3D20 printer files\nCheck it to install the files."

        checked: checkInstallStatus(UM.Preferences.getValue("Dremel3D20/install_status"))
        onClicked: manager.changePluginInstallStatus(checked)
      } //end CheckBox

    } // end Column


    leftButtons: [
        Button
        {
            id: button1
            text: qsTr("Open plugin website")
            onClicked: manager.openPluginWebsite()
            anchors.left: col1.left
            anchors.bottom: col1.bottom
        }
    ]


    rightButtons: [
        Button
        {
            id: button2
            UM.I18nCatalog
            {
                id: catalog
                name: "cura"
            }

            text: catalog.i18nc("@action:button", "Close")
            onClicked: base.hide()
            anchors.right: col1.right
            anchors.bottom: col1.bottom
        }
    ]

}
