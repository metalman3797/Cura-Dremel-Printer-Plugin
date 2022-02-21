####################################################################
# Dremel MJPEG camera streamer 
#
# Written by Tim Schoenmackers
#
# This plugin is released under the terms of the LGPLv3 or higher.
# The full text of the LGPLv3 License can be found here:
# https://github.com/timmehtimmeh/Cura-Dremel-Printer-Plugin/blob/master/LICENSE
####################################################################

import urllib.request

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import pyqtSignal, QThread, pyqtSlot

from UM.Logger import Logger

class CameraGrabThread(QThread):
    updateImage = pyqtSignal(QImage)
    running = False
    ipAddr = None

    def setWindow(self,window):
        self.window = window

    def setIPAddress(self, ip: str):
        self.ipAddr = ip

    def stopThread(self):
        self.running = False
    
    # TODO - make this more robust - 
    def startThread(self):
        self.stopThread()
        self.start()

    def run(self):
        # if we're already running just return
        if self.running:
            return

        # if the IP address hasn't been set, return
        if self.ipAddr is None:
            return
        Logger.log("i", "Starting Camera Grab Thread")
        self.running = True
        port = "10123"
        stream_url = 'http://'+self.ipAddr+':'+port+'/?action=stream'
        try:
            stream = urllib.request.urlopen(stream_url)
        except:
            Logger.log("i", "Dremel Plugin could not connect to Dremel Camera at ip address "+self.ipAddr)
            return
        abytes =  bytes()
        img = QImage()
        while self.running:
            abytes += stream.read(1024)
            a = abytes.find(b'\xff\xd8')
            b = abytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = abytes[a:b+2]
                abytes = abytes[b+2:]
                if(img.loadFromData(jpg, "JPG")):
                    self.updateImage.emit(img)

            if len(abytes) > 5000000:
                Logger.log("i", "Camera grab thread buffer too big - restarting")
                self.stopThread()  # stops the thread
                self.startThread()

class CameraViewWindow(QWidget):
    cameraGrabThread = None
    IpAddress = None
    label = None

    def __init__(self):
        super().__init__()
        self.title = "Dremel Camera Stream"
        self.label = QLabel(self)
        self.initUI()

    def closeEvent(self, evnt):
        Logger.log("i", "Dremel camera window received close event")
        self.StopCameraGrabbing()

    def StartCameraGrabbing(self):
        if self.cameraGrabThread is None:
            self.cameraGrabThread = CameraGrabThread(self)
        self.cameraGrabThread.setIPAddress(self.IpAddress)
        self.cameraGrabThread.updateImage.connect(self.setImage)
        self.cameraGrabThread.startThread()
        self.show()

    def StopCameraGrabbing(self):
        Logger.log("i", "Stopping Camera Grab Thread")
        if self.cameraGrabThread is not None:
            self.cameraGrabThread.stopThread()
    
    def setIpAddress(self,ip: str):
        self.IpAddress = ip
        if self.cameraGrabThread is None:
            self.cameraGrabThread = CameraGrabThread(self)
        self.cameraGrabThread.setIPAddress(self.IpAddress)

    @pyqtSlot(QImage)
    def setImage(self, image):
        self.label.setPixmap(QPixmap.fromImage(image))

    def initUI(self):
        self.setWindowTitle(self.title)
        # create a label
        
        self.label.resize(640, 480)
        self.label.setText("Connecting...")

