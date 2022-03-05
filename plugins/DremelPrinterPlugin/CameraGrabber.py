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
from PyQt5.QtCore import pyqtSignal, QThread, pyqtSlot, QTimer, QUrl, QSize, Qt
from enum import Enum

from time import time, sleep
from UM.Logger import Logger
from UM.Message import Message

class ConnectedState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    # for comparing
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

class CameraGrabThreadState(Enum):
    ERRORED = -2
    STOPPING = -1  
    STOPPED = 0
    STARTING = 1
    GRABBING = 2

    # for comparing
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

class CameraGrabThread(QThread):
    updateImage = pyqtSignal(QImage)

    connectedState = ConnectedState.DISCONNECTED
    grabbingState = CameraGrabThreadState.STOPPED
    last_image_grabbed_time = None
    connectionAttempt = 0
    stream = None
    ipAddr = None

    MAX_TIME_TIMEOUT = 5.0 #seconds

    def setIPAddress(self, ip: str):
        if self.ipAddr is not None and self.ipAddr == ip:
            Logger.log("i", "Camera Grab Thread - IP addresses are the same")
            return
        self.ipAddr = ip
        self.connectedState = ConnectedState.DISCONNECTED
        self.grabbingState = CameraGrabThreadState.STOPPED
        self.stream = None
        Logger.log("i", "Camera Grab Thread - IP Address set to "+ip)

    def stop(self):
        self.grabbingState = CameraGrabThreadState.STOPPING

    def isConnected(self):
        return self.connectedState == ConnectedState.CONNECTED
    
    def isStopping(self):
        return self.grabbingState == CameraGrabThreadState.STOPPING

    def isGrabbing(self):
        return self.grabbingState >= CameraGrabThreadState.STARTING
    
    def getConnectionAttemptNumber(self):
        return self.connectionAttempt

    # loops until the IP address is connected to
    def connect(self):
        while self.connectedState == ConnectedState.DISCONNECTED and self.grabbingState != CameraGrabThreadState.STOPPING:
            self.connectionAttempt +=1
            Logger.log("i", "Camera Grab Thread: Camera Disconnected...connection attempt: "+str(self.connectionAttempt))
            port = "10123"
            stream_url = 'http://'+self.ipAddr+':'+port+'/?action=stream'
            try:
                self.stream = urllib.request.urlopen(stream_url, timeout=self.MAX_TIME_TIMEOUT)
                self.connectedState = ConnectedState.CONNECTED
                Logger.log("i", "Camera Grab Thread: Connected to camera stream at: "+stream_url)
                return True
            except:
                self.connectedState = ConnectedState.DISCONNECTED
                Logger.log("i", "Dremel Plugin could not connect to Dremel Camera at ip address "+self.ipAddr)
                return False

    def grabFrames(self):
        self.last_image_grabbed_time = None
        streamBufferBytes =  bytes()
        img = QImage()

        # grab
        while self.connectedState != ConnectedState.DISCONNECTED and self.grabbingState != CameraGrabThreadState.STOPPING:
            try:
                # try to read the image data from the stream adding the newly read data to a buffer
                streamBufferBytes += self.stream.read(1024)
            except:
                # if there was a timeout reading the stream then set the state to disconnected & return
                self.connectedState = ConnectedState.DISCONNECTED
                continue

            # look for the starting and ending markers of the mjpeg
            imgStart = streamBufferBytes.find(b'\xff\xd8')
            imgEnd = streamBufferBytes.find(b'\xff\xd9')
            # if we found them
            if imgStart != -1 and imgEnd != -1:
                # section out the jpg bytes
                jpg = streamBufferBytes[imgStart:imgEnd+2]

                #  and remove those jpg bytes from the stored buffer
                streamBufferBytes = streamBufferBytes[imgEnd+2:]

                # if we can successfully load this data into a jpg then emit a signal
                # which will cause the window to refresh the image
                if(img.loadFromData(jpg, "JPG")):
                    self.connectionAttempt = 0
                    self.grabbingState = CameraGrabThreadState.GRABBING
                    self.last_image_grabbed_time = time()
                    self.updateImage.emit(img)

            # if the buffer gets too big (5 MB) then reset the thread
            if len(streamBufferBytes) > 5000000:
                Logger.log("i", "Camera grab thread buffer too big - restarting")
                self.connectedState = ConnectedState.DISCONNECTED
                self.grabbingState = CameraGrabThreadState.STOPPED
        Logger.log("i", "Returning from Camera Grab Loop")

    def run(self):
        Logger.log("i", "Starting Camera Grab Thread")

         # if the IP address hasn't been set, return
        if self.ipAddr is None:
            Logger.log("w", "Camera Grab Thread cannot start - No IP address")
            return

        self.grabbingState = CameraGrabThreadState.STARTING

        # loop while we're not stopping and try to connect & grab frames
        while self.grabbingState != CameraGrabThreadState.STOPPING:

            # if we haven't received an image in a while then we're disconnected and stopped
            if self.last_image_grabbed_time is not None and (time()-self.last_image_grabbed_time > self.MAX_TIME_TIMEOUT):
                self.connectedState = ConnectedState.DISCONNECTED
                self.grabbingState = CameraGrabThreadState.STOPPED

            if not self.connect():
                continue

            self.grabFrames()

        Logger.log("i", "Dremel Plugin Camera Grab Thread is done")

class CameraViewWindow(QWidget):
    cameraGrabThread = None
    IpAddress = None
    label = None
    openCameraStreamWebsiteButton = None
    _checkConnectionTimer = None
    labelSize = QSize(640,480)

    isRunning = False

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.title = "Dremel Camera Stream"
        self.setWindowTitle(self.title)
        self.label = QLabel(self)
        self.label.setScaledContents(False)
        self.label.setAlignment(Qt.AlignCenter)
        self.openCameraStreamWebsiteButton = QPushButton(self)
        self.openCameraStreamWebsiteButton.visible = False
        self.openCameraStreamWebsiteButton.resize(0,0)
        self.openCameraStreamWebsiteButton.setText("Open Camera Stream in Web Browser")
        self.openCameraStreamWebsiteButton.clicked.connect(self.openCameraStreamWebsite)
        # create a label
        self.windowSize = QSize(640,480)
        self.label.resize(self.windowSize)
        self.label.setText("Connecting...")

    def _checkConnection(self):
        # if the thread is created, and not running then change the label
        if self.cameraGrabThread is not None and not self.cameraGrabThread.isConnected():
            self.label.resize(640, 120)
            self.openCameraStreamWebsiteButton.visible = True
            self.openCameraStreamWebsiteButton.resize(300,30)
            self.label.setText("Connecting...Attempt # "+str(self.cameraGrabThread.getConnectionAttemptNumber()))

    # catches the close event and stops the camera grabbing thread
    def closeEvent(self, evnt):
        Logger.log("i", "Dremel camera window received close event")
        self.StopCameraGrabbing()

    def resizeEvent(self,sizeEvent):
        #Logger.log("i", "Dremel camera window received resize event")
        self.windowSize = sizeEvent.size()
        self.label.resize(self.windowSize)

    def StartCameraGrabbing(self):
        self.openCameraStreamWebsiteButton.resize(300,30)
        if self.cameraGrabThread is None:
            self.cameraGrabThread = CameraGrabThread(self)
        self.cameraGrabThread.setIPAddress(self.IpAddress)
        self.cameraGrabThread.updateImage.connect(self.setImage)
        self.cameraGrabThread.start()
        self.label.setText("Connecting To Dremel Camera")
        if self._checkConnectionTimer is None:
            self._checkConnectionTimer = QTimer()
            self._checkConnectionTimer.timeout.connect(self._checkConnection)
            self._checkConnectionTimer.start(1000)

        self.show()

    def IsGrabbing(self):
        if self.cameraGrabThread is not None:
            return self.cameraGrabThread.isGrabbing()
        return False

    def StopCameraGrabbing(self):
        Logger.log("i", "Stopping Camera Grab Thread")
        if self.cameraGrabThread is not None:
            self.cameraGrabThread.stop()
        if self._checkConnectionTimer is not None:
            self._checkConnectionTimer.stop()
            self._checkConnectionTimer = None
    
    def setIpAddress(self,ip: str):
        self.IpAddress = ip
        if self.cameraGrabThread is not None:
            Logger.log("i", "Dremel Camera UI setting IP address")
            self.cameraGrabThread.setIPAddress(self.IpAddress)

    # slot to get the image from the camera grab thread
    @pyqtSlot(QImage)
    def setImage(self, image):
        if image is not None:
            self.label.resize(self.windowSize)
            self.openCameraStreamWebsiteButton.resize(0,0)
            try:
                w = self.label.width()
                h = self.label.height()
                self.label.setPixmap(QPixmap.fromImage(image).scaled(w,h,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            except:
                self.label.setText("There was a problem with the image")
        else:
            self.label.resize(640, 120)
            self.openCameraStreamWebsiteButton.resize(300,30)
            self.label.setText("Connecting...")

    @pyqtSlot()
    def openCameraStreamWebsite(self):
        if  self.IpAddress is not None:
            url = QUrl("http://"+self.IpAddress+":10123/stream.html", QUrl.TolerantMode)
            if not QDesktopServices.openUrl(url):
                message = Message("Could not open http://"+self.IpAddress+":10123/?action=stream")
                message.show()
        else:
            message = Message("Camera IP address not set - please open Dremel Printer Plugin preferences")
            message.show()
        return