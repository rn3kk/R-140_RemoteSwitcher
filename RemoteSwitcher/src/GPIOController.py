import json
import time
from enum import Enum

import RPi.GPIO as GPIO
from threading import Thread

__metaclass__ = type

PINS_BMZ = "pinsBmz"
PINS_OUTPUT = "pinsOutput"
PINS_INPUT = "pinsInput"
NAME = "name"
GPIO_NUMBER = "gpioNumber"
AUTO_OFF = "auto_off"
STATE = "state"
TYPE = "type"
REQUEST = "request"
GET_GPIO_STATE = "getGpioState"
CHANGE_GPIO_STATE = "changeGpioState"
CHANGE_BMZ = "changeBmz"
BMZ_NUMBER = "bmzNumber"
REQUEST_RESULT = "result"
TRUE = "true"
FALSE = "false"
BMZ = "bmz"

class PinType(Enum):
    INPUT = 1
    OUTPUT = 2

class Pin:  # Base class for output pin
    __pinName = None
    _pinNumber = None
    _pinState = None
    __pinType = None

    def __init__(self, pinName, pinNumber, pinType):
        self.__pinName = pinName
        self._pinNumber = pinNumber
        self.__pinType = pinType

    def getPinName(self):
        return self.__pinName

    def getPinNumber(self):
        return self._pinNumber

    def getPinState(self):
        return self._pinState

    def getPinType(self):
        if self.__pinType == PinType.INPUT:
            return 0
        if self.__pinType == PinType.OUTPUT:
            return 1


class InputPin(Pin):

    def __init__(self, pinName, pinNumber):
       print('InputPin ', pinName, 'number ', pinNumber)
       super(InputPin, self).__init__(pinName, pinNumber, PinType.INPUT)
       GPIO.setmode(GPIO.BCM)
       GPIO.setup(int(pinNumber), GPIO.IN)

    def updatePinState(self):
        self._pinState = 1
        self._pinState = GPIO.input(int(self._pinNumber))

class OutputPin(Pin):

    __autoOffTime = 0
    __timeLeft = 0

    def __init__(self, pinName, pinNumber, autoOffTime=0, pinState=False):
        print('OutputPin ', pinName, 'number ', pinNumber, "autoOffTime", autoOffTime)
        super(OutputPin, self).__init__(pinName, pinNumber, PinType.OUTPUT)
        self.__autoOffTime = autoOffTime
        #GPIO.setmode(GPIO.BCM)
        #GPIO.setup(int(pinNumber), GPIO.OUT)
        self.setPinNewState(pinState)

    def setPinNewState(self, state):
        self._pinState = state
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(int(self._pinNumber), GPIO.OUT)
            GPIO.output(int(self._pinNumber), bool(state))
            self.__timeLeft = 1
            print('New statete for OutputPin ', self.getPinName(), 'number ', self.getPinNumber(), 'sate ', self.getPinState() )
        except Exception:
            print('Error: output pin state NOT changed')

    def updateAutoOffstate(self, checkInterval):
        if self.__autoOffTime == 0:
            return
        if self.__timeLeft == 0:
            return
        if self.__timeLeft >= self.__autoOffTime:
            try:
                GPIO.setup(int(self._pinNumber), GPIO.OUT)
                GPIO.output(int(self._pinNumber), not bool(self.getPinState()))
                self.__timeLeft = 0
                print('Auto change state OutputPin ', self.getPinName(), 'number ', self.getPinNumber(), 'sate ',
                      self.getPinState())
                self.__timeLeft = 0
            except Exception:
                print('Error updateAutoOffstate: output pin state NOT changed')
        else:
            self.__timeLeft += checkInterval
            print('Auto change state OutputPin ', self.getPinName(), 'number ', self.getPinNumber(), 'sate ',
                  self.getPinState(), 'time ', self.__timeLeft)

class GPIOController(Thread):
    __instance = None
    __outputPinsList = None
    __inputPinsList = None
    __bmz = None

    @staticmethod
    def getInstance():
        if GPIOController.__instance == None:
            GPIOController.__instance = GPIOController()
        return GPIOController.__instance

    def __init__(self):
        Thread.__init__(self)
        print("Load pins from file ../res/pins")
        self.__outputPinsList = list()
        self.__inputPinsList = list()
        filePins = open("../res/pins")
        data = filePins.read()
        filePins.close()
        jsonPins = json.loads(data)

        outputPinsList = jsonPins[PINS_OUTPUT]

        # load bmz pins
        bmzPin0 = None
        bmzPin1 = None
        bmzPin2 = None
        bmzPin3 = None
        for pin in outputPinsList:  # load output pins
            name = pin.get(NAME)
            gpio_number = pin.get(GPIO_NUMBER)
            autoOff = pin.get(AUTO_OFF)
            if autoOff is None:
                autoOff = 0
            state = pin.get(STATE)
            type = pin.get(TYPE)
            if type == "bmz":
                if name == "bit1":
                    bmzPin0 = OutputPin(name, gpio_number, autoOff, state)
                if name == "bit2":
                    bmzPin1 = OutputPin(name, gpio_number, autoOff, state)
                if name == "bit3":
                    bmzPin2 = OutputPin(name, gpio_number, autoOff, state)
                if name == "bit4":
                    bmzPin3 = OutputPin(name, gpio_number, autoOff, state)
            else:
                self.__outputPinsList.append(OutputPin(name, gpio_number, autoOff, state))

        if not (bmzPin0 is None) and not (bmzPin1 is None) and not (bmzPin2 is None) and not (bmzPin3 is None):
            self.__bmz = Bmz(bmzPin0, bmzPin1, bmzPin2, bmzPin3)

        inputPinsList = jsonPins[PINS_INPUT]
        for pin in inputPinsList:  # load input pins
            name = pin.get(NAME)
            gpio_number = pin.get(GPIO_NUMBER)
            type = pin.get(TYPE)
            self.__inputPinsList.append(InputPin(name, gpio_number))

    def run(self):
        timeSleepInterval = 1
        while True:
            time.sleep(timeSleepInterval)
            for pin in self.__inputPinsList:
                pin.updatePinState()
            for p in self.__outputPinsList:
                pin.updateAutoOffstate(timeSleepInterval)
        GPIO.cleanup()

    def getGpioState(self):
        input, output = [], []
        for outputPin in self.__outputPinsList:
            str = {NAME: outputPin.getPinName(), STATE: outputPin.getPinState(), TYPE: outputPin.getPinType()}
            output.append(str)
        output.append(self.__bmz.toOutputPin())
        for inputPin in self.__inputPinsList:
            str = {NAME: inputPin.getPinName(), STATE: inputPin.getPinState(), TYPE: inputPin.getPinType()}
            input.append(str)
        response = {}
        response[TYPE] = GET_GPIO_STATE
        response[REQUEST_RESULT] = TRUE
        response[PINS_OUTPUT] = output
        response[PINS_INPUT] = input
        response = json.dumps(response)
        return response

    def changePinState(self, pinName):
        for pin in self.__outputPinsList:
            if pin.getPinName() == pinName:
                pin.setPinNewState(not pin.getPinState())
        response = {}
        response[TYPE] = CHANGE_GPIO_STATE
        response[REQUEST_RESULT] = TRUE
        response = json.dumps(response)
        return response

    def changeBmz(self, bmzNumber):
        if (self.__bmz is None):
            result = FALSE
        else:
            result = TRUE
            self.__bmz.setActiveBMZ(int(bmzNumber))
        response = {}
        response[TYPE] = CHANGE_BMZ
        response[REQUEST_RESULT] = result
        response = json.dumps(response)
        return response

    def setPinToState(self, gpioPin, state):
        return 0




class Bmz:
    __pin0 = None
    __pin1 = None
    __pin2 = None
    __pin3 = None


    def __init__(self, pin0, pin1, pin2, pin3):
        self.__pin0 = pin0
        self.__pin1 = pin1
        self.__pin2 = pin2
        self.__pin3 = pin3

    def setActiveBMZ(self, activeBMZ):
        bitfield = list(bin(activeBMZ))[2:]

        for x in range(4-len(bitfield)):
          bitfield = [0] + bitfield

        self.__pin0.setPinNewState(bitfield[0])
        self.__pin1.setPinNewState(bitfield[1])
        self.__pin2.setPinNewState(bitfield[2])
        self.__pin3.setPinNewState(bitfield[3])

    def toOutputPin(self):
        bmzNum = 0
        bmzNum = (bmzNum << 1) | int(self.__pin0.getPinState())
        bmzNum = (bmzNum << 1) | int(self.__pin1.getPinState())
        bmzNum = (bmzNum << 1) | int(self.__pin2.getPinState())
        bmzNum = (bmzNum << 1) | int(self.__pin3.getPinState())

        str = {NAME: BMZ, STATE: bmzNum, TYPE: 1}
        return str