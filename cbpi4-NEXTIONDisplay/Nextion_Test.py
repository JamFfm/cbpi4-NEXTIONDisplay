# !/usr/bin/env python
# -*- coding: utf-8 -*-

import serial
import time


# TERMINATOR = bytearray([0xFF, 0xFF, 0xFF])
TERMINATOR = b'\xff\xff\xff'
port = "/dev/ttyUSB0"
time.sleep(3)
ser = serial.Serial(
    port=port,
    baudrate=38400,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=0.1
    )
ser.reset_output_buffer()

timestr = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
TextLableName = "t3start"
string = timestr

# command = (b't3start.txt="hello World"') #ok
command = str.encode('%s.txt="%s"' % (TextLableName, string))  #ok
# command = str.encode("{}.txt='{}'".format(TextLableName, string))  #nicht ok
# command = str.encode('t3start.txt=\"hello6 World\"') #ok
# command = (b't3start.txt="hello World"') #ok
ser.write(command)
ser.write(TERMINATOR)
ser.write(command)
ser.write(TERMINATOR)
print(command)


