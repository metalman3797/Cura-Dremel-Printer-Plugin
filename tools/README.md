# How to make a release (Windows)

Install [wkhtmltopdf](https://wkhtmltopdf.org/downloads.html) to `c:/Program Files/wkhtmltopdf/`

 Install the python grip package with `python3 -m pip install grip`

Run the make_release.py script by typing

`python make_release.py`

A RELEASE directory will be created one level up, which will contain a `.curapackage` file and a zip file.
- The zip file is used to submit the plugin to ultimaker
- The .curapackage can be used for standalone installs (please be aware that installing the same version over itself will not upgrade the plugin's files.)

**Note:** wkhtmltopdf is used to create a pdf of the main README that is included in the release.  The plugin accesses the pdf via the `Extensions->Dremel Printer Plugin->Help` menu.  If wkhtmltopdf is not installed then the help menu item will attempt to use the system to open a nonexistant file.