@echo off
setlocal enabledelayedexpansion


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: User should change the path below to point to the Cura-Dremel-3D20-Plugin
:: directory that they downloaded
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

set DOWNLOADED_PLUGIN_DIR=C:\Users\timsc\Documents\Cura-Dremel-3D20-Plugin


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: User should change the path below to point to the path containing Cura.exe
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

set CURA_EXE_DIR=C:\Program Files\Ultimaker Cura 3.2




::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: Don't modify anything below this line
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
if exist "%CURA_EXE_DIR%\Cura.exe" (
    ECHO "Cura Directory Set correctly...installing plugin" 
    if not exist "%CURA_EXE_DIR%\Plugins\DremelGCodeWriter\" (
	    mkdir "%CURA_EXE_DIR%\Plugins\DremelGCodeWriter\"
    )
    xcopy /s /y "%DOWNLOADED_PLUGIN_DIR%\plugins\DremelGCodeWriter" "%CURA_EXE_DIR%\Plugins\DremelGCodeWriter" 
    xcopy /s /y "%DOWNLOADED_PLUGIN_DIR%\resources\definitions" "%CURA_EXE_DIR%\resources\definitions" 
    xcopy /s /y "%DOWNLOADED_PLUGIN_DIR%\resources\materials" "%CURA_EXE_DIR%\resources\materials"
    xcopy /s /y "%DOWNLOADED_PLUGIN_DIR%\resources\meshes" "%CURA_EXE_DIR%\resources\meshes"
    if !ERRORLEVEL! GEQ 1 (
        ECHO ***Error copying some files - please check the console
	GOTO End
    ) else (
	ECHO ***Plugin Successfully Installed!
    )
) else (
    ECHO "Cura Directory not set correctly."
    GOTO End
)

:End
@echo Now exiting installer.
pause