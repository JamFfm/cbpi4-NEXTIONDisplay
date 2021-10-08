# !/usr/bin/env python
# -*- coding: utf-8 -*-
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# NextionDisplay Version 0.1.2.0
# Build for Craftbeerpi 4
# Assembled by JamFfm
#
# sudo pip install pyserial         # install serial, unlikely you have to
#                                   # install it because usually it is already installed
# python -m serial.tools.list_ports # List all ports in command-box
# dmesg | grep tty                  # List serial Connections
# fermentation functions are not implemented yet
# time as thread


import logging
import asyncio
import time
import serial  # serial connection to the Nextion Display
import socket  # ip adr
import fcntl  # ip adr
import struct  # ip adr
import threading
import sys
import signal
from time import strftime  # Time display
from cbpi.api.config import ConfigType
from cbpi.api import *  # for logger

DEBUG = False  # toggle writing of debug information in the app.log
TERMINATOR = b'\xff\xff\xff'  # Terminator to send a command to Nextion Display
liste = []
listetarget = []
# FERMLISTE = []
# FERMLISTETARGET = []

erase = False
rewrite = False
targetfocus = "off"  # this is a button value
ser = None

max_value_old = 0  # global max_value_old
min_value_old = 0  # global min_value_old
# fmax_value_old = 0  # global fmax_value_old fermentation
# fmin_value_old = 0  # global fmin_value_old fermentation
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    logger.info('NextionDisplay - signal_handler strg-c detected, stop Timethread')
    sys.exit(0)


class Timethread (threading.Thread):

    def __init__(self, ser):
        threading.Thread.__init__(self)
        self.ser = ser
        self.running = True
        signal.signal(signal.SIGINT, signal_handler)

    def shutdown(self):
        self.running = False
        pass

    def stop(self):
        self.running = False
        pass

    def run(self):

        while self.running is True:
            try:
                delay_time = 1  # in seconds
                timestr = ((strftime("%Y-%m-%d %H:%M:%S", time.localtime())).ljust(20))
                TextLableName = "t3start"
                command = str.encode('%s.txt="%s"' % (TextLableName, timestr))
                ser.write(command)
                ser.write(TERMINATOR)
                time.sleep(delay_time)  # showing time only every second <look_time>
            except Exception as e:
                logger.info('NextionDisplay - Timethread exception  %s' % e)
                self.running = False
            pass
        pass
        logger.info('NextionDisplay - Timethread strg C pressed')


class NEXTIONDisplay(CBPiExtension):
    def __init__(self, cbpi):
        self.cbpi = cbpi
        self._task = asyncio.create_task(self.run())

    async def run(self):

        global erase
        global rewrite
        global targetfocus
        global ser

        port = await self.set_serial_port_of_raspi()
        logger.info("NextionDisplay - Serial Port of Raspi: %s" % port)
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

        kettleID = await self.set_parameter_kettleID()
        logger.info("NextionDisplay - Kettle_ID: %s" % kettleID)
        dubbleline = await self.set_parameter_dubbleline(ser)
        logger.info("NextionDisplay - dubbleline: %s" % dubbleline)
        ip = await self.set_ip()
        iptext = "IP of Raspi: %s" % ip
        logger.info("NextionDisplay - %s" % iptext)
        version = await self.get_cbpi_version()
        logger.info("nextionDisplay - CBPI version: %s" % version)

        #  for any reason the first value will be dropped so t1startfake is just fake and does nothing
        await self.NextionwriteString(ser, "t1startfake", "start")
        await self.NextionwriteString(ser, "t1start", version)

        self.displaythetime = Timethread(ser)
        self.displaythetime.daemon = False
        self.displaythetime.start()
        logger.info("NextionDisplay - time started")
        # *************************************************************************************************************
        while True:
            # this is the main code repeated constantly

            kettleID = await self.set_parameter_kettleID()
            # fermid = int(set_parameter_fermID())
            dubbleline = await self.set_parameter_dubbleline(ser)

            ip = await self.set_ip()
            iptext = "IP: %s" % ip

            await self.NextionwriteString(ser, "t2start", iptext)

            # collect all values
            all_values = await self.collect_all_values(kettleID)

            kettle_current_temp_as_string = all_values["current_temp_of_kettle_sensor_formatted_as_string"]
            current_temp_of_kettle_sensor_as_float = all_values["current_temp_of_kettle_sensor_as_float"]
            kettle_target_temp_as_string = all_values["kettle_target_temp_formatted_as_string"]
            kettle_target_temp_as_float = all_values["kettle_target_temp_as_float"]
            current_kettle_name = all_values["name_of_current_kettle"]
            current_rest_name = all_values["active_step_name"]
            remaining_time_of_current_rest = all_values["remaining_time"]
            step_duration = all_values["step_duration"]
            unit = all_values["temp_unit"]

            # pass
            await self.detect_touch(ser)

            if current_temp_of_kettle_sensor_as_float < 110.00:  # first value is 200.00 and we want to skip it
                await self.writewave(ser,
                                     current_temp_of_kettle_sensor_as_float,
                                     kettle_current_temp_as_string,
                                     kettle_target_temp_as_float,
                                     kettle_target_temp_as_string,
                                     current_kettle_name,
                                     current_rest_name,
                                     remaining_time_of_current_rest,
                                     targetfocus,
                                     erase, rewrite,
                                     dubbleline)
            pass
            rewrite = False
            erase = False
            await self.writingDigittoNextion(ser,
                                             kettle_current_temp_as_string,
                                             kettle_target_temp_as_string,
                                             current_kettle_name)

            await self.writing_multi_to_nextion(ser,
                                                unit,
                                                current_rest_name,
                                                remaining_time_of_current_rest,
                                                step_duration)

            # writefermwave(ser, fermid, dubbleline=dubbleline)

            await asyncio.sleep(1)
            pass
        pass
        # *************************************************************************************************************

    async def writewave(self, ser,
                        current_temp_of_kettle_sensor_as_float,
                        kettle_current_temp_as_string,
                        kettle_target_temp_as_float,
                        kettle_target_temp_as_string,
                        current_kettle_name,
                        current_rest_name,
                        remaining_time_of_current_rest,
                        targetfocus,
                        erase=False, rewrite=False, dubbleline=True):

        global min_value_old
        global max_value_old

        currenttemp = current_temp_of_kettle_sensor_as_float  # float is needed
        targettemp = kettle_target_temp_as_float  # float is needed
        unit = "°" + str(await self.get_cbpi_temp_unit())

        # If you change the wave with or height in Nextion Display these values have to be adjusted
        nextion_wave_with = 406  # check the values in the Nextion Editor
        nextion_wave_height = 202  # check the values in the Nextion Editor

        #   Current kettletemp in text field
        await self.NextionwriteString(ser, "CurrTempBrwTxt", kettle_current_temp_as_string)
        #   Current Kettle target temp in text field
        await self.NextionwriteString(ser, "TargTempBrwTxt", kettle_target_temp_as_string)
        #   Current Kettlename in text field
        await self.NextionwriteString(ser, "KettleNameTxt", current_kettle_name)
        #   rest name
        await self.NextionwriteString(ser, "RestNameTxt", current_rest_name)

        #   remaining time of step (if active)
        is_timer_running = await self.is_timer_running(remaining_time_of_current_rest)
        if is_timer_running is True:
            await self.NextionwriteString(ser, "remBrewTime", remaining_time_of_current_rest)
        else:
            await self.NextionwriteString(ser, "remBrewTime", "")

        #   build list of current temp values
        if erase is True:
            liste.clear()
            liste.append(currenttemp)
        elif len(liste) < nextion_wave_with:  # 406 the with of the wave object on Nextion.
            liste.append(currenttemp)
        else:
            liste.pop(0)
            liste.append(currenttemp)
            # if DEBUG: logger.info('NextionDisplay  - TempListe bigger 407:%s' % (len(liste)))
        if DEBUG: logger.info('NextionDisplay  - TempListe len(liste):%s' % (len(liste)))

        # build liste of current targettemp values len(listetarget) can be different to len(liste)
        if erase is True:
            listetarget.clear()
            listetarget.append(targettemp)
        if len(listetarget) < nextion_wave_with:  # 406 the with of the wave object on Nextion
            listetarget.append(targettemp)
        else:
            listetarget.pop(0)
            listetarget.append(targettemp)
        # if DEBUG: logger.info('NextionDisplay  - targetListe len(listetarget):%s' % (len(listetarget)))
        pass

        # min max labels for scale
        if targetfocus == "on":
            max_value_curr_temp = round(float(max(liste)) + 0.3, 1)
            min_value_curr_temp = round(float(min(liste)) - 0.3, 1)
            max_value_targ_temp = round(float(max(listetarget)) + 0.3, 1)
            min_value_targ_temp = round(float(min(listetarget)) - 0.3, 1)
            max_value = max(max_value_curr_temp, max_value_targ_temp)
            min_value = min(min_value_curr_temp, min_value_targ_temp)
        else:
            max_value = round(float(max(liste)) + 0.3, 1)
            min_value = round(float(min(liste)) - 0.3, 1)
        pass

        await self.NextionwriteString(ser, "tmax", "%s%s" % (max_value, str(unit)))
        await self.NextionwriteString(ser, "tmin", "%s%s" % (min_value, (str(unit))))
        await self.NextionwriteString(ser, "tavarage",
                                      "%s%s" % (round(((max_value + min_value) / 2), 1), (str(unit))))
        # get the scaling-factor
        offset = (max_value - min_value)
        xpixel = nextion_wave_height  # 202 the height of the wave object on Nextion
        factor = (xpixel / offset)

        # if DEBUG: logger.info('NextionDisplay  - max_value/ max_value_old %s / %s' % (max_value, max_value_old))
        # if DEBUG: logger.info('NextionDisplay  - min_value/ min_value_old %s / %s' % (min_value, min_value_old))
        # if DEBUG: logger.info('NextionDisplay  - rewrite %s' % rewrite)

        #  if max/min values changed rewrite graph from liste with new scale
        if max_value != max_value_old or min_value != min_value_old or rewrite is True:  # rewrite graph if new
            # temp values are out of current scale
            if DEBUG: logger.info('NextionDisplay  - rewrite = %s' % rewrite)
            await self.NextionwriteClear(ser, 1, 0)  # BrewTemp
            await self.NextionwriteClear(ser, 1, 1)  # BrewTemp adjust thickness of line
            await self.NextionwriteClear(ser, 1, 2)  # TargetTemp
            await self.NextionwriteClear(ser, 1, 3)  # TargetTemp adjust thickness of line
            i = 0
            await self.Nextion_ref_wave(ser, "ref_stop")
            while i < len(liste):
                if DEBUG: logger.info('NextionDisplay  - liste:%s' % (liste[i]))
                digit = round(((liste[i] - min_value) * factor), 2)
                digit2 = digit + 1  # adjust thickness of line
                digit_to_int = round(digit)
                digit2_to_int = round(digit2)
                string = str(digit_to_int)
                string2 = str(digit2_to_int)  # adjust thickness of line
                await self.NextionwriteWave(ser, 1, 0, string)
                if dubbleline: await self.NextionwriteWave(ser, 1, 1, string2)  # adjust thickness of line
                if DEBUG: logger.info('NextionDisplay  - dubbleline rewrite: %s' % dubbleline)
                #  targettemp
                # if DEBUG: logger.info('NextionDisplay  - listetarget:%s' % (listetarget[i]))
                target = round(((listetarget[i] - min_value) * factor), 2)
                target2 = target + 1
                target_to_int = round(target)
                target2_to_int = round(target2)
                tstring = str(target_to_int)
                tstring2 = str(target2_to_int)  # adjust thickness of line
                if 0 < target < xpixel:  # do not write target line if not in temp/screen range
                    await self.NextionwriteWave(ser, 1, 2, tstring)
                    if dubbleline: await self.NextionwriteWave(ser, 1, 3, tstring2)
                    if DEBUG: logger.info(
                        'NextionDisplay  - listetarget[i], target, tstring: %s, %s, %s' % (
                            listetarget[i], target, tstring))
                elif targettemp == 0.00:
                    await self.NextionwriteWave(ser, 1, 2, 0)
                    if dubbleline: await self.NextionwriteWave(ser, 1, 3, 0)
                elif xpixel < target:
                    await self.NextionwriteWave(ser, 1, 2, xpixel)
                    if dubbleline: await self.NextionwriteWave(ser, 1, 3, xpixel)
                else:
                    pass
                pass
                if DEBUG: logger.info(
                    'NextionDisplay  - liste(i), digit, string: %s, %s, %s' % (liste[i], digit, string))
                i += 1
            await self.Nextion_ref_wave(ser, "ref_star")
            # max/min values not changed write graph value by value
        else:
            digit = (round(((currenttemp - min_value) * factor), 2))
            digit2 = digit + 1  # adjust thickness of line
            digit_to_int = round(digit)
            digit2_to_int = round(digit2)
            string = str(digit_to_int)
            string2 = str(digit2_to_int)  # adjust thickness of line
            if DEBUG: logger.info(
                'NextionDisplay  - currenttemp, digit, string: %s, %s, %s' % (currenttemp, digit, string))
            await self.NextionwriteWave(ser, 1, 0, string)
            if dubbleline: await self.NextionwriteWave(ser, 1, 1, string2)  # adjust thickness of line

            # target Temp
            target = (round(((targettemp - min_value) * factor), 2))
            target2 = target + 1
            target_to_int = round(target)
            target2_to_int = round(target2)
            tstring = str(target_to_int)
            tstring2 = str(target2_to_int)  # adjust thickness of line
            if DEBUG: logger.info(
                "NextionDisplay - targettemp / Target / xpixel: %s / %s / %s" % (targettemp, target, xpixel))
            if 0 < target < xpixel:  # do not write target line if not in temp/ screen range
                await self.NextionwriteWave(ser, 1, 2, tstring)
                if dubbleline: await self.NextionwriteWave(ser, 1, 3, tstring2)  # adjust thickness of line
                if DEBUG: logger.info(
                    'NextionDisplay  - targettemp, target, tstring: %s, %s, %s' % (targettemp, target, tstring))
            elif targettemp == 0.00:
                await self.NextionwriteWave(ser, 1, 2, 0)
                if dubbleline: await self.NextionwriteWave(ser, 1, 3, 0)  # adjust thickness of line
            elif xpixel < target:
                await self.NextionwriteWave(ser, 1, 2, xpixel)
                if dubbleline: await self.NextionwriteWave(ser, 1, 3, xpixel)
                pass
        pass

        # global max_value_old
        max_value_old = max_value
        # global min_value_old
        min_value_old = min_value
        await asyncio.sleep(4.3)  # has effect on time scale of x axis makes everything slow
        return None

    async def writing_multi_to_nextion(self, ser,
                                       unit, current_rest_name, remaining_time_of_current_rest, step_duration):

        await self.NextionwriteString(ser, "unitMBrew", str(unit))
        await self.NextionwriteString(ser, "StepnameMTxt", current_rest_name)

        kettle_json_obj = self.cbpi.kettle.get_state()
        kettles = kettle_json_obj['data']
        val = 0
        i = 0

        # turn off all 4 heater status icons
        for x in range(4):
            heater_status_field_once = "heaterstatusM" + str(x + 1)
            await self.Nextionshowhideobject(ser, heater_status_field_once, "off")
        pass

        while i < len(kettles):  # there are only 4 fields in the multidisplay but if one fails and there
            # are 5 kettles it will at least show the 4 functional kettles
            try:
                kettle_id = kettles[i]["id"]
                kettle_name_field = "KettlenMTxt" + str(i + 1)
                kettle_name = (kettles[i]["name"])
                await self.NextionwriteString(ser, kettle_name_field, kettle_name)

                current_temp_field = "CurrMTemp" + str(i + 1)
                kettle_sensor_id = (kettles[i]["sensor"])
                sensor_value = self.cbpi.sensor.get_sensor_value(kettle_sensor_id).get('value')
                CurrMTemp = ("%6.2f%s" % (sensor_value, "°"))
                await self.NextionwriteString(ser, current_temp_field, CurrMTemp)

                target_temp_field = "TarTempMTxt" + str(i + 1)
                kettle_target_temp = (kettles[i]["target_temp"])
                TarTempMTxt = ("%6.2f%s" % (kettle_target_temp, "°"))
                await self.NextionwriteString(ser, target_temp_field, TarTempMTxt)

                heater_status_field = "heaterstatusM" + str(i + 1)
                kettle = self.cbpi.kettle.find_by_id(kettle_id)
                heater = self.cbpi.actor.find_by_id(kettle.heater)
                kettle_heater_status = heater.instance.state

                if kettle_heater_status is True:
                    if DEBUG: logger.info("NextionDisplay  - writing_multi_to_nextion: heater status on")
                    await self.Nextionshowhideobject(ser, heater_status_field, "on")
                else:
                    if DEBUG: logger.info("NextionDisplay  - writing_multi_to_nextion: heater status off")
                    await self.Nextionshowhideobject(ser, heater_status_field, "off")
                pass
            except Exception as e:
                if DEBUG: logger.error(e)
                if DEBUG: logger.info("NextionDisplay  - writing_multi_to_nextion: no Kettle %s found" % i)
                heater_status_field = "heaterstatusM" + str(i + 1)
                await self.Nextionshowhideobject(ser, heater_status_field, "off")
            pass
            i = i + 1
        pass

        try:
            is_timer_running = await self.is_timer_running(remaining_time_of_current_rest)

            # if timer is running show remaining time of current rest and calculate thr % if rest-time for progressbar
            if is_timer_running is True:
                await self.NextionwriteString(ser, "remBrewTime", remaining_time_of_current_rest)
                val = await self.multiprogressbarvalue(remaining_time_of_current_rest, step_duration)
            else:
                await self.NextionwriteString(ser, "remBrewTime", "")
                val = 0
        except Exception as e:
            logger.warning(e)
        pass
        # progressbar
        await self.Nextionprogressbar(ser, "RemainTimeMBar", val)

    async def writingDigittoNextion(self, ser,
                                    kettle_current_temp_as_string,
                                    kettle_target_temp_as_string,
                                    current_kettle_name):
        try:
            # current temp in text field
            await self.NextionwriteString(ser, "CurrTempTxt", kettle_current_temp_as_string)

            #   target temp in text Field
            await self.NextionwriteString(ser, "TargetTempTxt", kettle_target_temp_as_string)

            #   Current kettlename in text field
            await self.NextionwriteString(ser, "t3", current_kettle_name)
        except Exception as e:
            if DEBUG: logger.warning(e)
        pass

    async def multiprogressbarvalue(self, remaining_time_of_current_rest, step_duration):

        if DEBUG: logger.info('NextionDisplay  - remaining_time_of_current_rest: %s' % remaining_time_of_current_rest)
        if DEBUG: logger.info('NextionDisplay  - step_duration: %s' % step_duration)

        try:
            time_left = sum(
                x * int(t) for x, t in zip([3600, 60, 1], remaining_time_of_current_rest.split(":")))
            time_left = int(time_left)
            step_duration = int(step_duration)
            val = int(100 - ((time_left * 100) / (step_duration * 60)))
            if DEBUG: logger.info('NextionDisplay  - multiprogressbarvalue: %s%s' % (val, "%"))
            return val
        except Exception as e:
            if DEBUG: logger.info('NextionDisplay  - multiprogressbarvalue: no active step ' + str(e))
            return 0
        pass

    async def collect_all_values(self, kettle_ID):
        unit = "°" + str(await self.get_cbpi_temp_unit())
        kettlevalues = await self.get_kettle_values(kettle_ID)
        stepvalues = await self.get_active_step_values()

        # Kettle Target Temp
        kettle_target_temp = kettlevalues['kettle_target_temp']
        kettle_target_temp_as_float = float("%6.2f" % (float(kettle_target_temp)))  # like 24,94 or 101,94
        kettle_target_temp_formatted = ("%6.2f%s" % (float(kettle_target_temp), unit))  # like 24,94°C or 101,94°C
        kettle_target_temp_formatted_as_string = str(kettle_target_temp_formatted)

        # Kettle Current Temp
        kettle_sensor_id = kettlevalues['kettle_sensor_id']
        current_temp_of_kettle_sensor = self.cbpi.sensor.get_sensor_value(kettle_sensor_id).get('value')
        current_temp_of_kettle_sensor_as_float = float("%6.2f" % (float(current_temp_of_kettle_sensor)))
        current_temp_of_kettle_sensor_formatted = ("%6.2f%s" % (float(current_temp_of_kettle_sensor), unit))
        current_temp_of_kettle_sensor_formatted_as_string = str(current_temp_of_kettle_sensor_formatted)

        # Current Kettlename
        name_of_current_kettle = kettlevalues['kettle_name']

        # active Stepname
        active_step_name = stepvalues['active_step_name']

        # remaining time
        step_state = stepvalues['active_step_state_text']
        remaining_time = step_state.replace("Status: ", "")

        # step_duration
        step_duration = stepvalues['active_step_timer_value']

        return {'current_temp_of_kettle_sensor_formatted_as_string': current_temp_of_kettle_sensor_formatted_as_string,
                'current_temp_of_kettle_sensor_as_float': current_temp_of_kettle_sensor_as_float,
                'kettle_target_temp_formatted_as_string': kettle_target_temp_formatted_as_string,
                'kettle_target_temp_as_float': kettle_target_temp_as_float,
                'name_of_current_kettle': name_of_current_kettle,
                'active_step_name': active_step_name,
                'remaining_time': remaining_time,
                'step_duration': step_duration,
                'temp_unit': unit
                }

    async def is_timer_running(self, remaining_time_of_current_rest):
        is_timer_running = False
        try:
            if "Waiting for Target Temp" in remaining_time_of_current_rest:
                is_timer_running = False
            elif remaining_time_of_current_rest == "":
                is_timer_running = False
            elif remaining_time_of_current_rest is None:
                is_timer_running = False
            else:
                is_timer_running = True
        except Exception as e:
            logger.warning("NextionDisplay - is_timer_running exception: " + str(e))
        return is_timer_running

    async def target_temp_of_kettle_sensor(self, kettle_ID):
        kettlevalues = await self.get_kettle_values(kettle_ID)
        kettle_target_temp = kettlevalues['kettle_target_temp']
        kettle_target_temp_formatted = ("%6.2f" % float(kettle_target_temp))  # only Number without unit
        return kettle_target_temp_formatted

    #  todo not used

    async def get_ip(self, interface):
        ip_addr = 'Not connected'
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ip_addr = socket.inet_ntoa(
                fcntl.ioctl(so.fileno(), 0x8915, struct.pack('256s', bytes(interface.encode())[:15]))[20:24])
        except Exception as e:
            logger.warning('NextionDisplay - no ip found')
            if DEBUG: logger.warning(e)
            return ip_addr
        finally:
            pass
        return ip_addr

    async def set_ip(self):
        if await self.get_ip('wlan0') != 'Not connected':
            ip = await self.get_ip('wlan0')
        elif await self.get_ip('eth0') != 'Not connected':
            ip = await self.get_ip('eth0')
        elif await self.get_ip('enxb827eb488a6e') != 'Not connected':
            ip = await self.get_ip('enxb827eb488a6e')
        else:
            ip = 'Not connected'
        pass
        return ip

    async def set_time(self, ser):
        look_time = 1  # in seconds

        timestr = ((strftime("%Y-%m-%d %H:%M:%S", time.localtime())).ljust(20))
        await self.NextionwriteString(ser, "t3start", timestr)
        # if DEBUG: cbpi.app.logger.info("NextionDisplay  - thread set_time " + timestr)
        # sleep(look_time)  # showing time only every second <look_time>
        # await asyncio.sleep(1) makes code slow

    async def NextionwriteString(self, ser, TextLableName, string):
        """
        :param ser: name of the serial connection
        :param TextLableName: name of the "textlable" on the Nextion
        :param string: the "string" to write in this lable
        use like NextionwriteString(ser, "TextLabelName", "string")
        """
        command = str.encode('%s.txt="%s"' % (TextLableName, string))
        # if DEBUG: cbpi.app.logger.info('NextionDisplay  - command Txt:%s' % command)
        ser.write(command)
        ser.write(TERMINATOR)

    async def NextionwriteClear(self, ser, WaveID, channel):
        command = str.encode('cle %s,%s' % (WaveID, channel))
        # if DEBUG: cbpi.app.logger.info('NextionDisplay  - command Number:%s' % command)
        ser.write(command)
        ser.write(TERMINATOR)

    async def NextionwriteWave(self, ser, WaveID, Channnel, intValue):
        command = str.encode('add %s,%s,%s' % (WaveID, Channnel, intValue))
        # if DEBUG: cbpi.app.logger.info('NextionDisplay  - command Wave:%s' % command)
        ser.write(command)
        ser.write(TERMINATOR)

    async def Nextion_ref_wave(self, ser, stop_start):
        """
        :param ser:name of the serial connection
        :param stop_start: ether "ref_stop" or "ref_star"
        use as: ref_wave(ser, "ref_stop") or ref_wave(ser, "ref_star")
        this is like a substitude of addt Nextion function
        stops and starts refresh of wave graph
        """
        if stop_start == "ref_stop" or stop_start == "ref_star":
            command = str.encode(stop_start)  # str.encode added check it
            ser.write(command)
            ser.write(TERMINATOR)
        else:
            logger.info("NextionDisplay  - ref_wave error: stop_start not ref_stop or ref_star: %s" % stop_start)
        pass

    async def NextionwriteNumber(self, ser, NumberLableName, integer):
        command = str.encode('%s.val=%s' % (NumberLableName, integer))
        # if DEBUG: cbpi.app.logger.info('NextionDisplay  - command Number:%s' % command)
        ser.write(command)
        ser.write(TERMINATOR)

    async def Nextionprogressbar(self, ser, barname, val):
        try:
            command = str.encode("%s.val=%s" % (barname, str(val)))
            # if DEBUG: logger.info('NextionDisplay  - Nextionprogressbar command Txt:%s' % command)
            ser.write(command)
            ser.write(TERMINATOR)
        except Exception as e:
            logger.warning('NextionDisplay  - Nextionprogressbar' + str(e))
        pass

    async def Nextionshowhideobject(self, ser, objectname, onoff):
        if onoff == "on":
            onoff = 1
        elif onoff == "off":
            onoff = 0
        else:
            logger.info("NextionDisplay  - Nextionshowhideobject onoff is not on or off:  %s" % onoff)
        if onoff == 1 or onoff == 0:
            command = str.encode('vis %s,%s' % (objectname, onoff))
            ser.write(command)
            ser.write(TERMINATOR)
        pass

    async def Nextiongetpage(self, ser):
        command = str.encode('sendme')
        ser.write(command)
        ser.write(TERMINATOR)
        touch = ser.read_until(TERMINATOR)
        if len(touch) != 0:
            prefix = touch[0:1]
            pageID_touch = touch[1:2]
            logger.info("NextionDisplay  - Nextiongetpage Prefix %s Page Number:  %s" % (prefix, pageID_touch))
        pass
        # todo not Used
    async def get_cbpi_temp_unit(self):
        try:
            unit = self.cbpi.config.get("TEMP_UNIT", None)
        except Exception as e:
            logger.warning('no cbpi temp. unit found')
            logger.warning(e)
            unit = "na"
        pass
        return unit

    async def get_breweryname(self):
        try:
            brewery = self.cbpi.config.get("BREWERY_NAME", None)
        except Exception as e:
            logger.warning('NextionDisplay - no breweryname found')
            logger.warning(e)
            brewery = "no name"
        pass
        return brewery

    async def get_cbpi_version(self):
        try:
            version = self.cbpi.version
        except Exception as e:
            logger.warning('NextionDisplay - no cbpi version found')
            logger.warning(e)
            version = "no vers."
        return version

    async def get_active_step_values(self):
        try:
            step_json_obj = self.cbpi.step.get_state()
            steps = step_json_obj['steps']
            # if DEBUG: logger.info("NextionDisplay - steps: %s" % steps)

            i = 0
            result = 'no active step'
            while i < len(steps):
                if steps[i]["status"] == "A":
                    active_step_name = (steps[i]["name"])
                    active_step_status = (steps[i]["status"])
                    active_step_state_text = (steps[i]["state_text"])
                    active_step_target_temp = (steps[i]["props"]["Temp"])
                    active_step_timer_value = (steps[i]["props"]["Timer"])
                    active_step_probs = (steps[i]["props"])
                    return {'active_step_name': active_step_name,
                            'active_step_status': active_step_status,
                            'active_step_state_text': active_step_state_text,
                            'active_step_target_temp': active_step_target_temp,
                            'active_step_timer_value': active_step_timer_value,
                            'active_step_probs': active_step_probs}
                else:
                    result = {'active_step_name': 'no active step',
                              'active_step_state_text': "",
                              'active_step_timer_value': ""}
                pass
                i = i + 1
            pass
            return result

        except Exception as e:
            logger.warning(e)
            return {'active_step_name': 'error',
                    'active_step_status': 'error',
                    'active_step_state_text': 'error',
                    'active_step_target_temp': 'error',
                    'active_step_timer_value': 'error',
                    'active_step_probs': 'error'}
        pass

    async def get_kettle_values(self, kettle_id):
        try:
            kettle_json_obj = self.cbpi.kettle.get_state()
            kettles = kettle_json_obj['data']
            # if DEBUG: logger.info("kettles %s" % kettles)
            i = 0
            result = None
            while i < len(kettles):
                if kettles[i]["id"] == kettle_id:
                    kettle_id = (kettles[i]["id"])
                    kettle_name = (kettles[i]["name"])
                    kettle_heater_id = (kettles[i]["heater"])
                    kettle_sensor_id = (kettles[i]["sensor"])
                    kettle_target_temp = (kettles[i]["target_temp"])
                    return {'kettle_id': kettle_id,
                            'kettle_name': kettle_name,
                            'kettle_heater_id': kettle_heater_id,
                            'kettle_sensor_id': kettle_sensor_id,
                            'kettle_target_temp': kettle_target_temp}
                else:
                    result = 'no kettle found with id %s' % kettle_id
                pass
                i = i + 1
            pass
            return result
        except Exception as e:
            logger.warning(e)
            return {'kettle_id': 'error',
                    'kettle_name': 'error',
                    'kettle_heater_id': 'error',
                    'kettle_sensor_id': 'error',
                    'kettle_target_temp': 'error'}
        pass

    pass

    async def get_sensor_values_by_id(self, sensor_id):
        try:
            sensor_json_obj = self.cbpi.sensor.get_state()
            sensors = sensor_json_obj['data']
            # if DEBUG: logger.info("sensors %s" % sensors)
            i = 0
            while i < len(sensors):
                if sensors[i]["id"] == sensor_id:
                    sensor_type = (sensors[i]["type"])
                    sensor_name = (sensors[i]["name"])
                    # sensor_id = (sensors[i]['id'])
                    sensor_props = (sensors[i]["props"])
                    sensor_value = self.cbpi.sensor.get_sensor_value(sensor_id).get('value')
                    return {'sensor_id': sensor_id,
                            'sensor_name': sensor_name,
                            'sensor_type': sensor_type,
                            'sensor_value': sensor_value,
                            'sensor_props': sensor_props}
                else:

                    pass
                pass
                i = i + 1
            pass
        except Exception as e:
            logger.info(e)
            return {'sensor_id': 'error',
                    'sensor_name': 'error',
                    'sensor_type': 'error',
                    'sensor_value': 'error',
                    'sensor_props': 'error'}
        pass
        await asyncio.sleep(1)

    async def set_parameter_kettleID(self):
        kettle_id = self.cbpi.config.get('NEXTION_Kettle_ID', None)
        if kettle_id is None:
            try:
                await self.cbpi.config.add('NEXTION_Kettle_ID', '', ConfigType.KETTLE,
                                           'Select the kettle to be displayed in NextionDisplay. '
                                           'NO! CBPi reboot required')
                logger.info("NextionDisplay - NEXTION_Kettle_ID added to settings")
                kettle_id = self.cbpi.config.get('NEXTION_Kettle_ID', None)
                if kettle_id is None:
                    kettle_id = self.cbpi.config.get('MASH_TUN', None)
                    logger.warning('NextionDisplay - set_parameter_kettleID: no value for Kettle_ID, used MASH TUN')
                pass
            except Exception as e:
                logger.warning('NextionDisplay - set_parameter_kettleID: Unable to update config')
                logger.warning(e)
            pass
        pass
        return kettle_id

    async def set_parameter_dubbleline(self, ser):
        dubbleline = self.cbpi.config.get("NEXTION_bold_line", None)
        if dubbleline is None:
            dubbleline = "on"
            try:
                await self.cbpi.config.add("NEXTION_bold_line", "on", ConfigType.SELECT,
                                           "Turn on/off bold line in graph",
                                           [{"label": "on", "value": "on"}, {"label": "off", "value": "off"}])
                logger.info("NextionDisplay - NEXTION_bold_line added to settings")
                dubbleline = self.cbpi.config.get("NEXTION_bold_line", None)
            except Exception as e:
                logger.warning('NextionDisplay - set_parameter_dubbleline: Unable to update config')
                logger.warning(e)
            pass
        if dubbleline == "on":
            return True
        else:
            await self.NextionwriteClear(ser, 1, 1)  # BrewTemp adjust thickness of line # brew
            await self.NextionwriteClear(ser, 1, 3)  # BrewTemp adjust thickness of line # brew target

            # await self.NextionwriteClear(ser, 5, 1)  # BrewTemp adjust thickness of line # ferment
            # await self.NextionwriteClear(ser, 5, 3)  # BrewTemp adjust thickness of line # ferment target
            return False
        pass

    async def set_serial_port_of_raspi(self):
        port = self.cbpi.config.get("NEXTION_Serial_Port", None)
        if port is None:
            port = "/dev/ttyUSB0"
            try:
                await self.cbpi.config.add("NEXTION_Serial_Port", '/dev/ttyUSB0', ConfigType.STRING,
                                           "NEXTION_Serial_Port like dev/ttyS0, /dev/ttyAM0, /dev/ttyUSB0, etc. "
                                           "Reboot necessary")
                logger.info("NextionDisplay - NEXTION_Serial_Port added")
                port = self.cbpi.config.get("NEXTION_Serial_Port", None)
            except Exception as e:
                logger.warning('NextionDisplay - NEXTION_Serial_Port: Unable to update config')
                logger.warning(e)
            pass
        pass
        return port

    async def set_targetfocus(self):
        targetfocus = self.cbpi.config.get("NEXTION_Target_Focus", None)
        if targetfocus is None:
            targetfocus = "off"
            try:
                await self.cbpi.config.add("NEXTION_Target_Focus", "off", ConfigType.SELECT,
                                           "Turn on/off NEXTION_Target_Focus no Reboot necessary",
                                           [{"label": "on", "value": "on"}, {"label": "off", "value": "off"}])
                logger.info("NextionDisplay - NEXTION_Target_Focus added")
                targetfocus = self.cbpi.config.get("NEXTION_Target_focus", None)
            except Exception as e:
                logger.warning('NextionDisplay - NEXTION_Target_Focus: Unable to update config')
                logger.warning(e)
            pass
        pass
        return targetfocus

    async def detect_touch(self, ser):
        global erase
        global rewrite
        global targetfocus
        look_touch = 1  # in seconds
        touch = ser.read_until(TERMINATOR)
        if len(touch) != 0:
            istouch = touch[0:1]
            istouch = str(istouch)
            istouch = istouch.lstrip("'b\\x")
            istouch = istouch.rstrip("\\xff\\xff\\xff\\'")
            istouch = str(istouch)
            if istouch == "e":
                logger.info("NextionDisplay  - touch: A button has been pushed %s" % istouch)

                pageID_touch = touch[1:2]
                compID_touch = touch[2:3]
                event_touch = touch[3:4]

                pageID_touch = str(pageID_touch)
                pageID_touch = pageID_touch.lstrip("'b\\x")
                pageID_touch = pageID_touch.rstrip("\\xff\\xff\\xff\\'")

                compID_touch = str(compID_touch)
                compID_touch = compID_touch.lstrip("'b\\x")
                compID_touch = compID_touch.rstrip("\\xff\\xff\\xff\\'")

                event_touch = str(event_touch)
                event_touch = event_touch.lstrip("'b\\x")
                event_touch = event_touch.rstrip("\\xff\\xff\\xff\\'")

                logger.info("NextionDisplay  - page:%s, component:%s, event:%s"
                            % (pageID_touch, compID_touch, event_touch))

                if (pageID_touch == "01" or pageID_touch == "05") and compID_touch == "05":
                    logger.info("NextionDisplay  - touch: Clearbutton of Brewpage pushed")
                    erase = True
                elif pageID_touch == "00" and compID_touch == "03":
                    logger.info("NextionDisplay  - touch: Brewpage button pushed")
                    rewrite = True
                elif (pageID_touch == "01" or pageID_touch == "05") and compID_touch == "11":
                    logger.info("NextionDisplay  - touch: Focusbutton of Brewpage pushed")
                    if targetfocus == "off":
                        targetfocus = "on"
                    else:
                        targetfocus = "off"
                    pass
                elif (pageID_touch == "03" and compID_touch == "03") or (
                        pageID_touch == "06" and compID_touch == "04"):
                    logger.info("NextionDisplay  - touch: Clearbutton of Fermpage pushed")
                    # writefermwave(ser, erase=True) todo
                elif pageID_touch == "00" and compID_touch == "05":
                    logger.info("NextionDisplay  - touch: Fermpage button pushed")
                    # writefermwave(ser, erase=False, frewrite=True) todo
                else:
                    pass
            pass
            time.sleep(look_touch)  # timeout the bigger the larger the chance of missing a push
        pass

    pass


def setup(cbpi):
    cbpi.plugin.register("NEXTIONDisplay", NEXTIONDisplay)
