import struct
from enum import Enum

class MaterialType(Enum):
     ABS = int("0x00", 16)
     PLA = int("0x01", 16)
     DISSOLVABLE = int("0x02", 16)
     NONE = int("0xff", 16)

class G3DremHeader:
    #initializes to expect an 80x60 thumbnail
    def __init__(self):
        self.startText = "g3drem 1.0      "             # 16 byte char array
        self.thumbnailStartLoc = int("0x3A", 16)        #  4 byte unsigned int
        self.imageStartLoc = int("0x38B0", 16)          #  4 byte unsigned int
        self.gcodeStartLoc = int("0x38B0", 16)          #  4 byte unsigned int
        self.numSeconds = 0                             #  4 byte unsigned int
        self.rightMaterialInMM = 0                      #  4 byte unsigned int
        self.leftMaterialInMM = 0                       #  4 byte unsigned int
        self.informationFlags = 1                       #  2 byte unsigned int
        self.heightPerLayer = 0                         #  2 byte unsigned int
        self.infillPercentage = 20                      #  2 byte unsigned int
        self.numShells = 3                              #  2 byte unsigned int
        self.printSpeed = 100                           #  2 byte unsigned int
        self.bedTemperature = 0                         #  2 byte unsigned int
        self.rightExtruderTemp = 220                    #  2 byte unsigned int
        self.leftExtruderTemp = 0                       #  2 byte unsigned int
        self.rightMaterialType = MaterialType.PLA.value #  1 byte unsigned int
        self.leftMaterialType = MaterialType.NONE.value #  1 byte unsigned int
        self.thumbBmpByteArray = bytearray(80*60*3+54)

    def setEstimatedTime(self, seconds):
        self.numSeconds = seconds

    def setMaterialLen(self, rightMM, leftMM=0):
        self.rightMaterialInMM = rightMM
        self.leftMaterialInMM = leftMM

    def setMaterialType(self, rightType, leftType=MaterialType.NONE.value):
        if type(rightType) is int:
            self.rightMaterialType = rightType
        elif isinstance(rightType, Enum):
            self.rightMaterialType = rightType.value
        else:
            self.rightMaterialType = MaterialType.PLA.value

        if type(leftType) is int:
            self.leftMaterialType = leftType
        elif isinstance(leftType, Enum):
            self.leftMaterialType = leftType.value
        else:
            self.leftMaterialType = MaterialType.NONE.value

    #0x01=right extruder, 0x02=left extruder, 0x04=bed heating, 0x08=support enabled
    def setFlags(self, leftExtruderExists, heatedBed, supportEnabled):
        self.informationFlags = 0x01
        if leftExtruderExists:
            self.informationFlags |= 0x02
        if heatedBed:
            self.informationFlags |= 0x04
        if supportEnabled:
            self.informationFlags |= 0x08

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

    def setBedTemperature(self, bedTemp):
        self.bedTemperature = bedTemp

    def writeHeader(self, stream):
        if stream is None:
            return False

        # write the "g3drem 1.0" text
        if stream.write(self.startText.encode()) != 16:
            return False

        # write the four-byte unsigned integers
        if stream.write(struct.pack('<LLLLLL',self.thumbnailStartLoc,
                                self.imageStartLoc, self.gcodeStartLoc,
                                self.numSeconds, self.rightMaterialInMM,
                                self.leftMaterialInMM)) != 24:
            return False

        # write the two-byte unsigned shorts
        if stream.write(struct.pack('<HHHHHHHH',self.informationFlags,
                                self.heightPerLayer,self.infillPercentage,
                                self.numShells, self.printSpeed,
                                self.bedTemperature,self.rightExtruderTemp,
                                self.leftExtruderTemp)) != 16:
            return False

        # write the material type
        if stream.write(struct.pack('<BB', self.rightMaterialType,
                                 self.leftMaterialType)) != 2:
            return False

        # write the thumbnail bitmap
        if stream.write(self.thumbBmpByteArray) != len(self.thumbBmpByteArray):
            return False

        return True
