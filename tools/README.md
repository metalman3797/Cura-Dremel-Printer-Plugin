# How to make a release

Download [7zip standalone console version](https://www.7-zip.org/download.html) and extract the following three items into this tools directory

 1. 7za.exe
 2. 7za.dll
 3. 7zxa.dll

 Install [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html) to `c:/Program Files/wkhtmltopdf/`

Run the make_release.py script by typing

`python make_release.py`

A RELEASE directory will be created one level up, and a .curapackage file will be placed inside.
