::::::::::::::::::::::::::::::::::
:: Step 1
:: cleanup & make directories
::::::::::::::::::::::::::::::::::
if EXIST ..\README.html (del ..\README.html)
if EXIST ..\README.pdf (del ..\README.pdf)

if NOT EXIST ..\Dremel_3D20 (mkdir ..\Dremel_3D20)
set RELEASE_DIR=..\Dremel_3D20

if NOT EXIST %RELEASE_DIR%\files (mkdir %RELEASE_DIR%\files)
if NOT EXIST %RELEASE_DIR%\files\plugins (mkdir %RELEASE_DIR%\files\plugins)
if NOT EXIST %RELEASE_DIR%\files\plugins\Dremel3D20 (mkdir %RELEASE_DIR%\files\plugins\Dremel3D20)
set PLUGIN_DIR=%RELEASE_DIR%\files\plugins\Dremel3D20
if EXIST %PLUGIN_DIR%\Dremel3D20.zip (del %PLUGIN_DIR%\Dremel3D20.zip)
if EXIST .\Cura-Dremel-3D20.curapackage (del .\Cura-Dremel-3D20.curapackage)

::::::::::::::::::::::::::::::::::
:: Step 2
:: copy the dremel printer definitions, the materials, and the quality files
::::::::::::::::::::::::::::::::::
xcopy ..\resources\definitions\Dremel3D20.def.json %PLUGIN_DIR%
xcopy ..\resources\materials\dremel_pla.xml.fdm_material %PLUGIN_DIR%
mkdir %PLUGIN_DIR%\dremel_3d20
xcopy ..\resources\quality\dremel_3d20 %PLUGIN_DIR%\dremel_3d20 /E

::::::::::::::::::::::::::::::::::
:: Step 3
:: zip the files copied above
::::::::::::::::::::::::::::::::::
7za.exe a %PLUGIN_DIR%\Dremel3D20.zip %PLUGIN_DIR%\Dremel3D20.def.json %PLUGIN_DIR%\dremel_pla.xml.fdm_material %PLUGIN_DIR%\dremel_3d20

::::::::::::::::::::::::::::::::::
:: Step 4
:: now delete the files that were copied in Step 2
::::::::::::::::::::::::::::::::::
del /f /s /q %PLUGIN_DIR%\Dremel3D20.def.json
del /f /s /q %PLUGIN_DIR%\dremel_pla.xml.fdm_material
del /f /s /q %PLUGIN_DIR%\dremel_3d20
rmdir %PLUGIN_DIR%\dremel_3d20

::::::::::::::::::::::::::::::::::
:: Step 5
:: Create the Readme pdf file
::::::::::::::::::::::::::::::::::
cd ..
if EXIST README.html (del README.html)
if EXIST README.pdf (del README.pdf)
grip README.md --export README.html
"c:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe" README.html README.pdf
cd tools
xcopy ..\README.pdf %PLUGIN_DIR%\

::::::::::::::::::::::::::::::::::
:: Step 6
:: Create the plugin
::::::::::::::::::::::::::::::::::
xcopy ..\plugins\Dremel3D20\* %PLUGIN_DIR%


::::::::::::::::::::::::::::::::::
:: Step 7
:: Copy required files to the release directory
::::::::::::::::::::::::::::::::::
xcopy ..\LICENSE %RELEASE_DIR%
xcopy ..\docs\icon.png %RELEASE_DIR%
xcopy ..\resources\package.json %RELEASE_DIR%


::::::::::::::::::::::::::::::::::
:: Step 8 - TODO: Work with cura team to get this integrated
:: Copy the platform mesh over
::::::::::::::::::::::::::::::::::
:: xcopy ..\resources\meshes\dremel_3D20_platform.stl .\Cura-Dremel-3D20-Plugin

::::::::::::::::::::::::::::::::::
:: Step 9
:: Zip up the plugin for release
::::::::::::::::::::::::::::::::::
7za.exe a .\Cura-Dremel-3D20.zip %RELEASE_DIR%\*
move .\Cura-Dremel-3D20.zip .\Cura-Dremel-3D20.curapackage

::::::::::::::::::::::::::::::::::
:: Step 10
:: Cleanup the files and directories
::::::::::::::::::::::::::::::::::
del /f /s /q %PLUGIN_DIR%\*.*
del /f /s /q  %RELEASE_DIR%
rmdir %PLUGIN_DIR%
rmdir %RELEASE_DIR%\files\plugins
rmdir %RELEASE_DIR%\files
rmdir  %RELEASE_DIR%
