#####################################################################
# make_release.py
#####################################################################
#  python script to make a .curaplugin file for drag/drop
#  installation into cura as well as making the necessary zip file for
#  uploading to contribute.ultimaker.com for release in the cura marketplace
#
# Written by Tim Schoenmackers
#
# This source is released under the terms of the LGPLv3 or higher.
# The full text of the LGPLv3 License can be found here:
# https://github.com/timmehtimmeh/Cura-Dremel-3D20-Plugin/blob/master/LICENSE
#
#
# Requirements:
#  This tool calls the wkhtmltopdf tool (64 bit) to make the pdf documentation
#    Download the tool from: https://wkhtmltopdf.org/downloads.html and set
#    the WKHTMLTOPDF_DIR appropriately below
#
#  Additionally this tool requires python 3 and the grip package
#    (pip install grip)
#####################################################################
import os
import shutil
import zipfile
import json
import subprocess

with open('../plugins/DremelPrinterPlugin/plugin.json') as json_file:
    plugin_json = json.load(json_file)

RELEASE_DIR = os.path.abspath('../RELEASE/DremelPrinterPlugin')
CURA_PACKAGE_FILE = os.path.abspath(f'../RELEASE/Cura-Dremel-Plugin-{plugin_json["version"]}.curapackage')
ULTIMAKER_ZIP = os.path.abspath('../RELEASE/DremelPrinterPlugin.zip')
PLUGIN_DIR = os.path.join(RELEASE_DIR, 'files/plugins/DremelPrinterPlugin')
WKHTMLTOPDF_DIR = '"c:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe"'  # Note the quotes around the path

################################
## Step 1
## cleanup & make directories
################################

if(os.path.exists(RELEASE_DIR)):
    shutil.rmtree(RELEASE_DIR)

# delete existing files
for item in ['../README.html',
            '../README.pdf',
            os.path.join(RELEASE_DIR,'files/plugins/DremelPrinterPlugin/DremelPrinterPlugin.zip'),
            CURA_PACKAGE_FILE]:
    print('Checking '+ os.path.abspath(item))
    if os.path.exists(os.path.abspath(item)):
        #print('Deleting ' + os.path.abspath(item))
        os.remove(os.path.abspath(item))

# make new dirs
if not os.path.exists(RELEASE_DIR):
    os.makedirs(RELEASE_DIR)

dirs = [RELEASE_DIR,
        os.path.join(RELEASE_DIR,'files'),
        os.path.join(RELEASE_DIR,'files/plugins'),
        os.path.join(RELEASE_DIR,'files/plugins/DremelPrinterPlugin')
        ]
for item in dirs:
    if not os.path.exists(item):
        os.makedirs(item)

################################
## Step 2
## copy the dremel printer definitions,
## materials, the platform stl file,
## and the quality files
################################
copyList = ['../resources/definitions/Dremel3D20.def.json',
           '../resources/definitions/Dremel3D40.def.json',
           '../resources/definitions/Dremel3D45.def.json',
           '../resources/extruders/dremel_3d20_extruder_0.def.json',
           '../resources/extruders/Dremel_3D40_extruder_0.def.json',
           '../resources/extruders/Dremel_3D45_extruder_0.def.json',
           '../resources/materials/dremel_pla.xml.fdm_material',
           '../resources/meshes/dremel_3D20_platform.stl',
           '../resources/meshes/Dremel_3D40_platform.stl',
           '../resources/meshes/Dremel_3D45_platform.stl',
           '../resources/materials/dremel_eco_abs.xml.fdm_material',
           '../resources/materials/dremel_nylon.xml.fdm_material',
           '../resources/materials/dremel_petg.xml.fdm_material',
           '../resources/materials/dremel_silk.xml.fdm_material',
           '../resources/materials/dremel_tpu.xml.fdm_material']
for item in copyList:
    shutil.copy2(os.path.abspath(item),PLUGIN_DIR)

shutil.copytree(os.path.abspath('../resources/quality/dremel_3d20'),
                os.path.join(PLUGIN_DIR,'dremel_3d20'))

shutil.copytree(os.path.abspath('../resources/quality/Dremel3D40'),
                os.path.join(PLUGIN_DIR,'Dremel3D40'))

shutil.copytree(os.path.abspath('../resources/quality/Dremel3D45'),
                os.path.join(PLUGIN_DIR,'Dremel3D45'))

################################
## Step 3
## zip the files copied above
################################
internal_zip_file_name = os.path.join(PLUGIN_DIR,'DremelPrinterPlugin.zip')
z = zipfile.ZipFile(internal_zip_file_name,'w', zipfile.ZIP_DEFLATED)
zipList = [os.path.join(PLUGIN_DIR,'Dremel3D20.def.json'),
           os.path.join(PLUGIN_DIR,'dremel_3d20_extruder_0.def.json'),
           os.path.join(PLUGIN_DIR,'dremel_pla.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'dremel_3D20_platform.stl'),
           os.path.join(PLUGIN_DIR,'Dremel3D40.def.json'),
           os.path.join(PLUGIN_DIR,'Dremel_3D40_extruder_0.def.json'),
           os.path.join(PLUGIN_DIR,'Dremel_3D40_platform.stl'),
           os.path.join(PLUGIN_DIR,'Dremel3D45.def.json'),
           os.path.join(PLUGIN_DIR,'Dremel_3D45_extruder_0.def.json'),
           os.path.join(PLUGIN_DIR,'dremel_eco_abs.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'dremel_nylon.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'dremel_petg.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'dremel_silk.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'dremel_tpu.xml.fdm_material'),
           os.path.join(PLUGIN_DIR,'Dremel_3D45_platform.stl')]
for item in zipList:
    z.write(item,os.path.basename(item));
path = os.path.join(PLUGIN_DIR,'dremel_3d20')
for root, dirs, files in os.walk(path):
    for file in files:
        z.write(os.path.join(PLUGIN_DIR,'dremel_3d20', file),os.path.join('dremel_3d20',file))
path = os.path.join(PLUGIN_DIR,'Dremel3D40')
for root, dirs, files in os.walk(path):
    for file in files:
        z.write(os.path.join(PLUGIN_DIR,'Dremel3D40', file),os.path.join('Dremel3D40',file))
path = os.path.join(PLUGIN_DIR,'Dremel3D45')
for root, dirs, files in os.walk(path):
    for file in files:
        z.write(os.path.join(PLUGIN_DIR,'Dremel3D45', file),os.path.join('Dremel3D45',file))
################################
## Step 4
## now delete the files that were copied in Step 2
################################
for item in zipList:
    if os.path.exists(os.path.abspath(item)):
        #print('Deleting ' + os.path.abspath(item))
        os.remove(os.path.abspath(item))

shutil.rmtree(os.path.join(PLUGIN_DIR,'dremel_3d20'))
shutil.rmtree(os.path.join(PLUGIN_DIR,'Dremel3D40'))
shutil.rmtree(os.path.join(PLUGIN_DIR,'Dremel3D45'))
################################
## Step 5
## Create the README.pdf file from the markdown
################################
currDir = os.getcwd()
os.chdir('..')
subprocess.run(['python', '-m', 'grip', 'README.md', '--export', 'README.html'])

# Convert HTML to PDF with specified margins using subprocess for better handling
pdf_command = [
    WKHTMLTOPDF_DIR.strip('"'),  # Remove quotes for subprocess list
    '--enable-local-file-access',
    '--page-size', 'A4',
    '-B', '20', '-L', '20', '-R', '20', '-T', '20',
    'README.html',
    os.path.join(PLUGIN_DIR, 'README.pdf')
]
subprocess.run(pdf_command)

# Copy the generated PDF back to the original directory, if it exists
pdf_path = os.path.join(PLUGIN_DIR, 'README.pdf')
if os.path.exists(pdf_path):
    shutil.copy2(pdf_path, '.')
else:
    print(f"Error: The file {pdf_path} was not found.")

os.chdir(currDir)

################################
## Step 6
## Copy the remaining plugin files
################################
src_dir=os.path.abspath('../plugins/DremelPrinterPlugin')
src_files = os.listdir(src_dir)
for file_name in src_files:
    full_file_name = os.path.join(src_dir, file_name)
    if os.path.isfile(full_file_name):
        shutil.copy2(full_file_name, PLUGIN_DIR)

################################
## Step 7
## Copy required files to the release directory
################################
remaining_files = [os.path.abspath('../LICENSE'),
                   os.path.abspath('../docs/icon.png'),
                   os.path.abspath('../resources/package.json')]

for file in remaining_files:
    shutil.copy2(file, RELEASE_DIR)

################################
## Step 8
## Zip up the plugin for release
################################
z = zipfile.ZipFile(CURA_PACKAGE_FILE,'w', zipfile.ZIP_DEFLATED)
for root, dirs, files in os.walk(RELEASE_DIR):
    for file in files:
        z.write(os.path.join(root,file),os.path.join(root,file).replace(RELEASE_DIR, ""))


################################
## Step 9
## Make the ultimaker zip file for upload to contribute.ultimaker.com
################################
shutil.copy2(os.path.abspath('../LICENSE'), PLUGIN_DIR)

z = zipfile.ZipFile(ULTIMAKER_ZIP,'w', zipfile.ZIP_DEFLATED)
for root, dirs, files in os.walk(PLUGIN_DIR):
    for file in files:
        print(os.path.join(root,file))
        z.write(os.path.join(root,file),os.path.join(root,file).replace(PLUGIN_DIR, "DremelPrinterPlugin"))


################################
## Step 10
## Cleanup the files and directories
################################
shutil.rmtree(RELEASE_DIR)
