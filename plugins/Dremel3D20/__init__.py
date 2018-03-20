# Copyright (c) 2015 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

from . import Dremel3D20

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "mesh_writer": {
            "output": [{
                "extension": "g3drem",
                "description": catalog.i18nc("@item:inlistbox", "g3drem File"),
                "mime_type": "application/x-g3drem",
                "mode": Dremel3D20.Dremel3D20.OutputMode.BinaryMode
            }]
        }
    }

def register(app):
    return { "mesh_writer": Dremel3D20.Dremel3D20(),
             "extension": Dremel3D20.Dremel3D20()}
