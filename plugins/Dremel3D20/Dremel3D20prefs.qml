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

    minimumWidth: Math.max(380 * screenScaleFactor,360)
    minimumHeight: Math.max(200 * screenScaleFactor,180)
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


    ColumnLayout {
      id: col1
      anchors.fill: parent
      anchors.margins: margin

        ColumnLayout {
          id: rowLayout
          Layout.fillWidth: true

          width: Math.round(parent.width)
          height: Math.round(parent.height)
          CheckBox {
              id: screenshotCB
              property int renderType: Text.NativeRendering
              text: "Select Screenshot Manually"
              checked: checkBooleanVals(UM.Preferences.getValue("Dremel3D20/select_screenshot"))
              onClicked: manager.setSelectScreenshot(checked)
              ToolTip.timeout: 5000
              ToolTip.visible: hovered
              ToolTip.text: "Check this box to allow you when saving a g3drem file to\nmanually select a screenshot from an image stored on your\nhard drive"
          } //end CheckBox

          CheckBox {
            id: installCB
            property int renderType: Text.NativeRendering
            text: "Are Dremel 3D20 Printer File Installed? "
            ToolTip.timeout: 5000
            ToolTip.visible: hovered
            ToolTip.text: "Uncheck this checkbox to uninstall the Dremel 3D20 printer files\nCheck it to install the files."
            checked: checkInstallStatus(UM.Preferences.getValue("Dremel3D20/install_status"))
            onClicked: manager.changePluginInstallStatus(checked)
          } //end CheckBox
        } // end columnlayout

        RowLayout {
            id: buttonRow
            width: Math.round(parent.width)
            anchors.bottom: parent.bottom
            Button
            {
                id: button1
                property int renderType: Text.NativeRendering
                text: qsTr("Open plugin website")
                onClicked: manager.openPluginWebsite()
            }

            Button
            {
                id: button
                UM.I18nCatalog
                {
                    id: catalog1
                    name: "cura"
                }
                property int renderType: Text.NativeRendering
                text: catalog1.i18nc("@action:button", "Report Issue")
                onClicked: manager.reportIssue()
            }

            Button
            {
                id: helpButton
                UM.I18nCatalog
                {
                    id: catalog
                    name: "cura"
                }
                property int renderType: Text.NativeRendering
                text: catalog.i18nc("@action:button", "Help")
                onClicked: manager.showHelp()
            }
        } // end RowLayout

    } // end ColumnLayout
}
