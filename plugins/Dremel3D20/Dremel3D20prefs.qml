import QtQuick 2.1
import QtQuick.Controls 1.3
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
      } //end CheckBox

      CheckBox {
        id: installCB
        text: "Dremel 3D20 Printer File Installed? "
        checked: checkInstallStatus(UM.Preferences.getValue("Dremel3D20/install_status"))
        onClicked: manager.changePluginInstallStatus(checked)
      } //end CheckBox

    } // end Column


    rightButtons: [
        Button
        {
            id: button1
            text: qsTr("Open plugin website")
            onClicked: manager.openPluginWebsite()
        },

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
        }
    ]

}
