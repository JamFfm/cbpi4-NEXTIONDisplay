# cbpi4-NEXTIONDisplay

![](https://img.shields.io/badge/CBPi%20addin-functionable_for_cbpi4-green.svg)  ![](https://img.shields.io/github/license/JamFfm/NEXTIONDisplay.svg?style=flat) ![](https://img.shields.io/github/last-commit/JamFfm/NEXTIONDisplay.svg?style=flat) ![](https://img.shields.io/github/release-pre/JamFfm/NEXTIONDisplay.svg?style=flat)

Use Nextion Display on a CraftbeerPi4 installation only.


# Installation

### This section is under construction!!! ###

1. Power off the display. Store the .tft file of this repository via a PC/Mac on a SD Card in a fat32 system (usually SD card max 32GB). There must be only 1 file on the card. Push the SD card in the display SD Card reader. Power on the display. Remove SD Card after installation. Again poweroff/poweron. 
Now you see the new start screen.

2. Load the NEXTIONDisplay addin from the CraftbeerPi3 addin section.

    
3. Reboot at least CBPi3

Maybe the Serial connection has to be turned off at the RASPI Settings. Reboot. Go again to the RASPI Settings. Turn on the Serial Port. Turn off the Serial console.

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/SerialConfig.jpg "Config of Serial Connection")

Maybe pyserial lib has to be installed if there is an error at import serial:

In commandbox type in: python -m pip install pyserial

4. Keep in mind that you have to access the SD Card slot and a power off/power on of the Nextion display when build in an enclosure. You need that for updates of the Nextion display. There is a stl file of a bezel in in the NEXTION Display directory (as zip). This is also available on the Nextion webside.


# What for?

This addin is designed for Craftbeerpi 4 and will display mainly the temperature of only one kettle or fermenter (not implemented) via serial connection to a color touch TFT display. 


# Advantages

- Needs only 4 Wires
- can also be connected via USB
- Dark Mode
- no loss of graphdata when changing views
- graph, stepname, kettlename, remaining time of rest, current temp, target temp in one screen
- watch up to 4 kettles at once
- easy change of gui via Nextion Editor
- bright display

Have a look:

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/HomeScreen.jpg "Example Startscreen")

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/digitmode.jpg "Example Digitscreen")

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/BrewGraph.jpg "Example Waveform")

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/BrewGraphdark.jpg "Example Waveform")

![Screens](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/Multiview.jpg "Example Multiview")


# Introduction to Nextion Displays

The Nextion displays are HMI displays which is not equal to HDMI!!
There is a Nextion editor which helps to design the Display. It is possible to build several display pages.
The amount of pages is only limited to the amount of memory.
In the Editor you can place pictures, fonts , buttons, text labels like in Visual Studio. Just way more simple. 
But powerful! From the Raspi side it is possible to place data to a special component placed on the page by the editor.
You just have to use the serial connection. To place a text in a text labels it is like t0.txt="your Text".
To close sending you have to terminate like three times x0ff.

There is the possibility to place some logic into the display. For example place a button on a page and write `page 2` at release event. The page 2 will be displayed without the help of the Raspi.

The way to work with Nextion Displays is:

1. Design the pages in the Nextion editor.

2. Open the build folder (Menu-> files) and store the .tft file of your project on a SD card.

3. Put the SD Card in the Display, power on, the project will be loaded.

4. On Raspi side use the Serial Connection at your code to post instructions to the display, and receive data from the display.
    It is touchscreen therefore it is quite helpful to use the inputs of the display in your code.

5. Be aware that all pictures and fonds have to be imported in the Editor and these have to be stored in the DISPLAY! like described in 3. You can not use pictures dynamically!! But you can change the visibility of pictures stored in the display.


You can download the Nextion Editor here:

https://nextion.itead.cc/resources/download/nextion-editor/

In this addon I use the following display:

https://www.itead.cc/nextion-nx4832t035.html

Features include: a 3.5" TFT 480x320 resistive touch screen display, 16M Flash, 3.5KByte RAM, 65k colors.


# Wiring the display

![Wireing](https://github.com/JamFfm/NEXTIONDisplay/blob/master/CBPi3Display/MMDVM-Nextion-wiring-for-programming.jpg "BrewNextionDisplay 3.5 Zoll")

For USB connection please use a USB to Serial converter like this one. 

https://de.aliexpress.com/item/32470262188.html?spm=a2g0s.9042311.0.0.51364c4dlbTYMx

Use 5V for the jumper position on the USB to Serial converter.

Nextion | USB Serial Converter| Raspi
------- | --------------------| -----
TX      | RX                  |  U
RX      | TX                  |  S
GND     | GND                 |  B
VCC     | use 5v (jumper)     |  x

# Usage

Push the buttons in the start-screen and choose the desired screen.
1. There is a screen with big digits with current temperature and the target temperature and current Kettlename.

2. There is a graph which will show the mash temperature of the past 40 min and its corresponding target temperature. 
Attention: If target temperature is not in the displayed range of the current temperature the target temperature 
is not plotted. Change this by pressing the focus button (crosshair). Name of active kettle and the name of the active 
rest is shown. At active rest the remaining time of the timer is shown.

3. Not implemented: There is a graph which will show the fermenter temperature of the past 40 min and its corresponding target temperature. Attention: If target fermenter temperature is not in the displayed range of the current temperature the target temperature is not plotted. Name of active fermenter+beername and the name of the active fermstep is shown. please use a short fermenter name. At active rest the remaining time of the fermenter-timer is shown.

4. There is a dark mode of the brew-screen and the ferm-screen (not implementedjet). In the home-screen you can change the modus by touch the "darkmode on/off" text. The digit -screen has got only one mode. 

5. There is a Multiview which displays current temperature, target temperature for up to 4 kettles. Kettlenames are listet. If the heater of the kettle is on an flame-icon appears. on active step the stepnamer and remaining time is displayed.

# Parameter

Have a look in the settings section in CraftbeerPi4 Gui.
All parameter with the Nextion "flag" will have influence.

1. NEXTION_Kettle_ID: Choose kettle (Number), NO! CBPi reboot required, default is number 1.

2. NEXTION_Fermenter_ID: Choose fermenter (Number), NO! CBPi reboot required, default is number 1. This is not used currently.

3. NEXTION_Serial_Port: Choose the Serial Port, Windows like COM1, Linux like dev/ttyS0,/dev/ttyAM0, etc. NO! CBPi reboot required
The code in the Repro uses USB Connection. You can change your connection/port here. Default is usb: /dev/ttyUSB0

4. NEXTION_bold_line: on / off
This will show the graph and targetline in bold. The parameter is used for brewing mode as well as for fermenter mode. Technically this is done by wiriting 2 lines with just 1 pixel difference. Bold has got a better appearance but is a little bit more slow.

# Known problems


1. Due to the fact that wave is only working with integer the wavevalues have to be rounded. So sometimes the graph is not precise. Error should be around 0.1°C/F.

2. With Raspi 3b I got some Problems to connect to a serial port. Raspi could only read the Nextion but not write to it. 
I assume the serial of bluetooth needs to be captured. I did not want to kill bluetooth though I do not use it in my installation. I used the serial via USB Port.

4. Fermentation ist not supported because it is not realised in the main software.



**Help is welcome**


# Fixed Problems
1. Due to the fact time is a thread this one is not stopped by ''strg c'' in command window of raspi.

# Support

Report issues either in this Git section or at Facebook at the [Craftbeerpi group](https://www.facebook.com/groups/craftbeerpi/)

