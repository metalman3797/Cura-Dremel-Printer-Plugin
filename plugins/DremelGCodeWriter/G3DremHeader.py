import struct

class G3DremHeader:
    #initializes to expect an 80x60 thumbnail
    def __init__(self):
        self.startText = "g3drem 1.0      "      # 16 byte char array
        self.thumbnailStartLoc = int("0x3A", 16) #  4 byte unsigned int
        self.imageStartLoc = int("0x38B0", 16)   #  4 byte unsigned int
        self.gcodeStartLoc = int("0x38B0", 16)   #  4 byte unsigned int
        self.numSeconds = 0                      #  4 byte unsigned int
        self.rightMaterialInMM = 0               #  4 byte unsigned int
        self.leftMaterialInMM = 0                #  4 byte unsigned int
        self.informationFlags = 1                #  2 byte unsigned int
        self.heightPerLayer = 0                  #  2 byte unsigned int
        self.infillPercentage = 20               #  2 byte unsigned int
        self.numShells = 3                       #  2 byte unsigned int
        self.printSpeed = 100                    #  2 byte unsigned int
        self.bedTemperature = 0                  #  2 byte unsigned int
        self.rightExtruderTemp = 220             #  2 byte unsigned int
        self.leftExtruderTemp = 0                #  2 byte unsigned int
        self.rightMaterialType = 1               #  1 byte unsigned int
        self.leftMaterialType = int("0xff", 16)  #  1 byte unsigned int
        self.thumbBmpByteArray = bytearray(80*60*3+54)

    def setEstimatedTime(self, seconds):
        self.numSeconds = seconds

    def setMaterialLen(self, rightMM, leftMM=0):
        self.rightMaterialInMM = rightMM
        self.leftMaterialInMM = leftMM

    def setLayerHeight(self, height):
        self.heightPerLayer = height

    def setInfillPct(self, infillPercent):
        self.infillPercentage = infillPercent

    def setNumShells(self, shells):
        self.numShells = shells

    def setPrintSpeed(self, speed):
        self.printSpeed = speed

    def setExtruderTemp(self, rightTemp, leftTemp=0):
        self.rightExtruderTemp = rightTemp
        self.leftExtruderTemp = leftTemp

    def setThumbnailBitmap(self, bytearray):
        if bytearray is not None:
            self.thumbBmpByteArray = bytearray
            self.imageStartLoc = 58 + len(bytearray)
            self.gcodeStartLoc = 58 + len(bytearray)

    def writeHeader(self, stream):
        if stream is None:
            return False

        if stream.write(self.startText.encode()) != 16:
            return False

        if stream.write(struct.pack('<LLLLLL',self.thumbnailStartLoc,
                                self.imageStartLoc, self.gcodeStartLoc,
                                self.numSeconds, self.rightMaterialInMM,
                                self.leftMaterialInMM)) != 24:
            return False

        if stream.write(struct.pack('<HHHHHHHH',self.informationFlags,
                                self.heightPerLayer,self.infillPercentage,
                                self.numShells, self.printSpeed,
                                self.bedTemperature,self.rightExtruderTemp,
                                self.leftExtruderTemp)) != 16:
            return False

        if stream.write(struct.pack('<BB', self.rightMaterialType,
                                 self.leftMaterialType)) != 2:
            return False

        # write the thumbnail bitmap
        if stream.write(self.thumbBmpByteArray) != len(self.thumbBmpByteArray):
            return False

        return True
