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
from PyQt5.QtCore import pyqtSignal, QThread, pyqtSlot, QTimer, QUrl, QSize

from enum import Enum

from time import time, sleep

from UM.Logger import Logger
from UM.Message import Message

class CameraGrabThreadState(Enum):
    ERRORED = -1
    DISCONNECTED = 0
    STOPPING = 1
    STARTING = 2
    CONNECTING = 3
    CONNECTED = 4
    GRABBING = 5

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

    threadState = CameraGrabThreadState.DISCONNECTED

    ipAddr = None
    _checkConnectionTimer = None
    last_image_grabbed_time = None

    MAX_TIME_TIMEOUT = 5.0 #seconds

    def setWindow(self,window):
        self.window = window

    def setIPAddress(self, ip: str):
        self.ipAddr = ip

    def stopThread(self):
        self.threadState = CameraGrabThreadState.STOPPING
        self._checkConnectionTimer = None

    # TODO - make this more robust - 
    def startThread(self):
        self.stopThread()
        self.connectedState = CameraGrabThreadState.DISCONNECTED
        # timer
        if self._checkConnectionTimer is None:
            self._checkConnectionTimer = QTimer()
            self._checkConnectionTimer.start(1000)
            self.last_image_grabbed_time = None
            self._checkConnectionTimer.timeout.connect(self._checkConnection)
        self.start()

    def isRunning(self):
        return self.connectedState >= CameraGrabThreadState.STARTING

    def isCurrentlyGrabbing(self):
        if self.connectedState>=CameraGrabThreadState.CONNECTED \
           and self.last_image_grabbed_time is not None\
           and (time()-self.last_image_grabbed_time <= self.MAX_TIME_TIMEOUT):
            return True
        return False

    def _checkConnection(self):
        # if we're running, not connecting, have grabbed an image and the last image was more than 5 seconds ago then stop the thread
        if self.connectedState>=CameraGrabThreadState.CONNECTED \
           and self.last_image_grabbed_time is not None\
           and (time()-self.last_image_grabbed_time > self.MAX_TIME_TIMEOUT):
            self.stopThread()
            Logger.log("i", "Camera Grab Thread did not receive data before timeout")

    def run(self):
        # if we're already running just return
        if self.connectedState >= CameraGrabThreadState.STARTING:
            Logger.log("w", "Camera Grab Thread is already running")
            return

        # if the IP address hasn't been set, return
        if self.ipAddr is None:
            Logger.log("w", "Camera Grab Thread cannot start - No IP address")
            return

        Logger.log("i", "Starting Camera Grab Thread")
        self.connectedState = CameraGrabThreadState.STARTING

        port = "10123"
        stream_url = 'http://'+self.ipAddr+':'+port+'/?action=stream'
        try:
            Logger.log("i", "Connecting to camera stream")
            stream = urllib.request.urlopen(stream_url, timeout=self.MAX_TIME_TIMEOUT)
            threadState = CameraGrabThreadState.CONNECTED
        except:
            self.connectedState = CameraGrabThreadState.DISCONNECTED
            Logger.log("i", "Dremel Plugin could not connect to Dremel Camera at ip address "+self.ipAddr)
            return
        Logger.log("i", "Connected to camera stream")

        self.last_image_grabbed_time = None
        streamBufferBytes =  bytes()
        img = QImage()
        self.connectedState = CameraGrabThreadState.GRABBING

        while self.connectedState > CameraGrabThreadState.STOPPING:
            try:
                # try to read the image data from the stream adding the newly read data to a buffer
                streamBufferBytes += stream.read(1024)
            except:
                # if there was a timeout reading the stream then set the state to disconnected & return
                self.connectedState = CameraGrabThreadState.DISCONNECTED
                return

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
                    self.last_image_grabbed_time = time()
                    self.updateImage.emit(img)

            # if the buffer gets too big (5 MB) then reset the thread
            if len(streamBufferBytes) > 5000000:
                Logger.log("i", "Camera grab thread buffer too big - restarting")
                self.stopThread()  # sets a flag to stop the thread
                self.startThread() # starts a new thread
                return             # returns from this thread

        Logger.log("i", "Dremel Plugin Camera Grab Thread is done")
        self.connectedState = CameraGrabThreadState.DISCONNECTED

class CameraViewWindow(QWidget):
    cameraGrabThread = None
    IpAddress = None
    label = None
    openCameraStreamWebsiteButton = None
    _checkConnectionTimer = None
    labelSize = QSize(640,480)
    connectionAttempt = 0

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.title = "Dremel Camera Stream"
        self.setWindowTitle(self.title)
        self.label = QLabel(self)
        self.label.setScaledContents(True)
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
        # if the thread is created, and not running then change the label and try to start the thread again
        if self.cameraGrabThread is not None and not self.cameraGrabThread.isRunning():
            self.label.resize(640, 120)
            self.openCameraStreamWebsiteButton.visible = True
            self.openCameraStreamWebsiteButton.resize(300,30)
            self.label.setText("Disconnected due to timeout...retyring connection")

            Logger.log("i", "CameraViewWindow: Camera Grab Thread is disconnected due to timeout...retyring")
            self.StartCameraGrabbing()
        elif self.cameraGrabThread is not None and self.cameraGrabThread.isCurrentlyGrabbing():
            self.connectionAttempt = 0

    # catches the close event and stops the camera grabbing thread
    def closeEvent(self, evnt):
        Logger.log("i", "Dremel camera window received close event")
        self.StopCameraGrabbing()

    def resizeEvent(self,sizeEvent):
        #Logger.log("i", "Dremel camera window received resize event")
        self.windowSize = sizeEvent.size()
        self.label.resize(self.windowSize)

    def StartCameraGrabbing(self):
        self.connectionAttempt += 1
        self.label.setText("Connecting...Attempt # "+str(self.connectionAttempt))
        self.openCameraStreamWebsiteButton.resize(300,30)
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

    # slot to get the image from the camera grab thread
    @pyqtSlot(QImage)
    def setImage(self, image):
        if image is not None:
            self.label.resize(self.windowSize)
            self.openCameraStreamWebsiteButton.resize(0,0)
            try:
                self.label.setPixmap(QPixmap.fromImage(image))
            except:
                self.label.setText("There was a problem with the image")
        else:
            self.label.resize(640, 120)
            self.openCameraStreamWebsiteButton.resize(300,30)
            self.label.setText("Connecting...")

    @pyqtSlot()
    def openCameraStreamWebsite(self):
        if  self.IpAddress is not None:
            url = QUrl("http://"+self.IpAddress+":10123/?action=stream", QUrl.TolerantMode)
            if not QDesktopServices.openUrl(url):
                message = Message("Could not open http://"+self.IpAddress+":10123/?action=stream")
                message.show()
        else:
            message = Message("Camera IP address not set - please open Dremel Printer Plugin preferences")
            message.show()
        return

