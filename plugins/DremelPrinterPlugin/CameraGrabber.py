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

from PyQt5.QtGui import QImage, QPixmap, QDesktopServices
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton
from PyQt5.QtCore import pyqtSignal, QThread, pyqtSlot, QTimer, QUrl

from time import time, sleep

from UM.Logger import Logger

class CameraGrabThread(QThread):
    updateImage = pyqtSignal(QImage)

    stopRequested = False
    connecting = False
    connected = False
    running = False

    ipAddr = None
    _checkConnectionTimer = None
    last_image_grabbed_time = None

    MAX_TIME_TIMEOUT = 5 #seconds

    def setWindow(self,window):
        self.window = window

    def setIPAddress(self, ip: str):
        self.ipAddr = ip

    def stopThread(self):
        self.stopRequested = True
        self._checkConnectionTimer = None

    # TODO - make this more robust - 
    def startThread(self):
        self.stopThread()
        self.stopRequested = False
        self.connecting = False
        self.connected = False
        self.running = False
        # timer
        if self._checkConnectionTimer is None:
            self._checkConnectionTimer = QTimer()
            self._checkConnectionTimer.start(1000)
            self.last_image_grabbed_time = None
            self._checkConnectionTimer.timeout.connect(self._checkConnection)
        self.start()

    def isRunning(self):
        return self.running

    def _checkConnection(self):
        # if we're running, not connecting, have grabbed an image and the last image was more than 5 seconds ago then stop the thread
        if self.running and not self.connecting and self.last_image_grabbed_time is not None and (time()-self.last_image_grabbed_time > self.MAX_TIME_TIMEOUT):
            self.stopThread()
            Logger.log("i", "Camera Grab Thread did not receive data before timeout")

    def run(self):
        # if we're already running just return
        if self.running:
            Logger.log("w", "Camera Grab Thread is already running")
            return

        # if the IP address hasn't been set, return
        if self.ipAddr is None:
            Logger.log("w", "Camera Grab Thread cannot start - No IP address")
            return

        Logger.log("i", "Starting Camera Grab Thread")
        self.running = True
        self.connecting = True
        self.connected = False

        port = "10123"
        stream_url = 'http://'+self.ipAddr+':'+port+'/?action=stream'
        try:
            Logger.log("i", "Connecting to camera stream")
            stream = urllib.request.urlopen(stream_url, timeout=10.0)
        except:
            self.connecting = False
            self.running = False
            Logger.log("i", "Dremel Plugin could not connect to Dremel Camera at ip address "+self.ipAddr)
            return
        Logger.log("i", "Connected to camera stream")
        self.connecting = False
        self.connected = True
        self.last_image_grabbed_time = None
        abytes =  bytes()
        img = QImage()
        while not self.stopRequested:
            try:
                abytes += stream.read(1024)
            except:
                self.running = False
                return
            a = abytes.find(b'\xff\xd8')
            b = abytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = abytes[a:b+2]
                abytes = abytes[b+2:]
                if(img.loadFromData(jpg, "JPG")):
                    self.last_image_grabbed_time = time()
                    self.updateImage.emit(img)

            if len(abytes) > 5000000:
                Logger.log("i", "Camera grab thread buffer too big - restarting")
                self.stopThread()  # stops the thread
                self.startThread()

        Logger.log("i", "Dremel Plugin Camera Grab Thread is done")
        self.stopRequested=False
        self.running = False

class CameraViewWindow(QWidget):
    cameraGrabThread = None
    IpAddress = None
    label = None
    openCameraStreamWebsiteButton = None
    _checkConnectionTimer = None

    def __init__(self):
        super().__init__()
        self.title = "Dremel Camera Stream"
        self.label = QLabel(self)
        self.openCameraStreamWebsiteButton = QPushButton(self)
        self.openCameraStreamWebsiteButton.visible = False
        self.openCameraStreamWebsiteButton.resize(0,0)
        self.openCameraStreamWebsiteButton.setText("Open Camera in Browser")
        self.openCameraStreamWebsiteButton.clicked.connect(self.openCameraStreamWebsite)
        self.initUI()

    def _checkConnection(self):
        # if the thread is created, and not running then change the label and try to start the thread again
        if self.cameraGrabThread is not None and not self.cameraGrabThread.isRunning():
            self.label.resize(640, 120)
            self.openCameraStreamWebsiteButton.visible = True
            self.openCameraStreamWebsiteButton.resize(640,30)
            self.label.setText("Disconnected due to timeout...retyring connection")

            if not self.cameraGrabThread.connecting:
                Logger.log("i", "CameraViewWindow: Camera Grab Thread is disconnected due to timeout...retyring")
                self.StartCameraGrabbing()

    def closeEvent(self, evnt):
        Logger.log("i", "Dremel camera window received close event")
        self.StopCameraGrabbing()

    def StartCameraGrabbing(self):
        self.label.resize(640, 480)
        self.label.setText("Connecting...")
        self.openCameraStreamWebsiteButton.visible = False
        self.openCameraStreamWebsiteButton.resize(0,0)
        if self.cameraGrabThread is None:
            self.cameraGrabThread = CameraGrabThread(self)
        self.cameraGrabThread.setIPAddress(self.IpAddress)
        self.cameraGrabThread.updateImage.connect(self.setImage)
        self.cameraGrabThread.startThread()
        if self._checkConnectionTimer is None:
            self._checkConnectionTimer = QTimer()
            self._checkConnectionTimer.start(1000)
            self._checkConnectionTimer.timeout.connect(self._checkConnection)

        self.show()

    def IsGrabbing(self):
        if self.cameraGrabThread is not None:
            return self.cameraGrabThread.isRunning()
        return False

    def StopCameraGrabbing(self):
        Logger.log("i", "Stopping Camera Grab Thread")
        if self.cameraGrabThread is not None:
            self.cameraGrabThread.stopThread()
            self._checkConnectionTimer = None
    
    def setIpAddress(self,ip: str):
        self.IpAddress = ip
        if self.cameraGrabThread is None:
            self.cameraGrabThread = CameraGrabThread(self)
        self.cameraGrabThread.setIPAddress(self.IpAddress)

    @pyqtSlot(QImage)
    def setImage(self, image):
        if image is not None:
            self.label.setPixmap(QPixmap.fromImage(image))
        else:
            self.label.setText("Connecting...")

    def initUI(self):
        self.setWindowTitle(self.title)
        # create a label
        
        self.label.resize(640, 480)
        self.label.setText("Connecting...")
        #TODO - add a qtimer and check the connection status after a bit to change the label text
        #       to something helpful if the connection fails.

    @pyqtSlot()
    def openCameraStreamWebsite(self):
        if  self.IpAddress is not None:
            url = QUrl("http://"+self.IpAddress+":10123/?action=stream", QUrl.TolerantMode)
            if not QDesktopServices.openUrl(url):
                message = Message(catalog.i18nc("@info:status","Could not open http://"+self.IpAddress+":10123/?action=stream"))
                message.show()
        else:
            message = Message(catalog.i18nc("@info:status","Camera IP address not set - please open Dremel Printer Plugin preferences"))
            message.show()
        return

