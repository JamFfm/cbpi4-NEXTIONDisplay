# run it with eg. Thonny on Raspi
# stop it with stop button in Thonny
# this is a script to determine the current page of Nextion

import serial

TERMINATOR = b'\xff\xff\xff'
EndCom = "\xff\xff\xff"

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


while True:       
    ser.write(('sendme ' + EndCom).encode('latin-1'))
    page = ser.read_until(EndCom)
    print(page)
    page = str(page)
    page = page.lstrip("b\\'f\\x")
    page = page.rstrip("\\xff\\xff\\xff\\'")
    print(page)
    print("________________________________________")
    
pass
