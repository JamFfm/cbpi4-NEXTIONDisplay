# run it with eg. Thonny on Raspi
# use this script to determine the "if conditions" to detect page, component id and event id.
# event ID (01 Press and 00 Release), I never detected 01

import serial

TERMINATOR = b'\xff\xff\xff'

port = '/dev/ttyUSB0'
ser = serial.Serial(
            port=port,
            baudrate=38400,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1
        )
ser.reset_output_buffer()

show_dez = True
show_lstrip = True
show_raw = True
DEBUG = True

while True:
    touch = ser.read_until(TERMINATOR)
    if len(touch) != 0:
        if DEBUG: print(touch)
        
        touch_btn = touch[0:1]
        if show_raw: print("isbutton ID = " + str(touch_btn))
        touch_btn = str(touch_btn)
        touch_btn = touch_btn.lstrip("'b\\x")
        touch_btn = touch_btn.rstrip("\\xff\\xff\\xff\\'")
        
        if show_lstrip: print("isbutton ID lstrip = " + str(touch_btn))

        if touch_btn == "e":  # indicates button press
            string = touch[1:2]
            if show_raw: print("Pagenumber ID = " + str(string))
            string = str(string)
            string = string.lstrip("'b\\x")
            string = string.rstrip("\\xff\\xff\\xff\\'")
            if show_lstrip: print("Pagenumber ID lstrip = " + str(string))
            string = int(string, 16)
            print("Pagenumber ID dez. = " + str(string))

            string = touch[2:3]
            if show_raw: print("Component ID = " + str(string))
            string = str(string)
            string = string.lstrip("'b\\x")
            string = string.rstrip("\\xff\\xff\\xff\\'")
            if show_lstrip: print("Component ID lstrip = " + str(string))
            string = int(string, 16)
            print("Component ID dez. = " + str(string))

            string = touch[3:4]  # event ID (0x01 Press and 0x00 Release)
            if show_raw: print("event ID = " + str(string))
            string = str(string)
            string = string.lstrip("'b\\x")
            string = string.rstrip("\\xff\\xff\\xff\\'")
            if show_lstrip: print("event ID lstrip = " + str(string))
            string = int(string, 16)
            print("event ID dez. = " + str(string))

            print("_____________________________")