#!/usr/bin/env python
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
# NextionDisplay Version 0.2.1.0
# Build for Craftbeerpi 4
# Assembled by JamFfm
# Refactored: globals removed, Timethread replaced by asyncio, writewave split up,
#             dubbleline logic extracted into helper method.
#
# sudo pip install pyserial         # install serial, unlikely you have to
#                                   # install it because usually it is already installed
# python -m serial.tools.list_ports # List all ports in command-box
# dmesg | grep tty                  # List serial Connections
# fermentation functions are not implemented yet

import logging
import asyncio
import time
import serial
import socket
import fcntl
import struct

from time import strftime
from cbpi.api.config import ConfigType
from cbpi.api import *

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
DEBUG = False
TERMINATOR = b'\xff\xff\xff'
WAVE_WIDTH = 406                # Breite des Wave-Objekts im Nextion Editor
WAVE_HEIGHT = 202               # Höhe des Wave-Objekts im Nextion Editor
SERIAL_BAUDRATE = 38400
TEMP_SKIP_THRESHOLD = 110.00    # Erster Sensorwert ist 200 — überspringen
SCALE_MARGIN = 0.3
WAVE_SLEEP = 4.3                # Effekt auf Zeitskala der X-Achse

logger = logging.getLogger(__name__)


class NEXTIONDisplay(CBPiExtension):

    def __init__(self, cbpi):
        self.cbpi = cbpi

        # --- Ehemals globale Variablen ---
        self.ser = None
        self.temp_list = []           # war: liste
        self.target_list = []         # war: listetarget
        self.erase = False
        self.rewrite = False
        self.targetfocus = "off"
        self.max_value_old = 0.0
        self.min_value_old = 0.0
        self.count = 0

        # Tasks
        self._main_task = asyncio.create_task(self.run())
        self._time_task = None

    # ======================================================================
    # Asyncio Time-Task (ersetzt Timethread)
    # ======================================================================
    async def _time_loop(self):
        """Zeigt die aktuelle Uhrzeit auf dem Display — ersetzt den alten Timethread."""
        while True:
            try:
                timestr = strftime("%Y-%m-%d %H:%M:%S", time.localtime()).ljust(20)
                await self.nextion_write_string("t3start", timestr)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("NextionDisplay - Time task cancelled")
                break
            except Exception as e:
                logger.warning("NextionDisplay - Time loop exception: %s" % e)
                await asyncio.sleep(5)

    # ======================================================================
    # Generische Serial-Kommunikation
    # ======================================================================
    def send_command_sync(self, command_str):
        """Sendet einen Befehl (String) direkt an das Nextion Display.
        Serial-Writes bei 38400 Baud blockieren nur Mikrosekunden —
        kein Executor nötig, vermeidet Thread-Overhead auf dem Raspi."""
        command = command_str.encode()
        self.ser.write(command)
        self.ser.write(TERMINATOR)

    async def send_command(self, command_str):
        """Async-Wrapper um send_command_sync (für konsistente await-Syntax)."""
        self.send_command_sync(command_str)

    # ======================================================================
    # Nextion Kommunikations-Hilfsmethoden
    # ======================================================================
    async def nextion_write_string(self, label_name, string):
        await self.send_command('%s.txt="%s"' % (label_name, string))

    async def nextion_write_clear(self, wave_id, channel):
        await self.send_command('cle %s,%s' % (wave_id, channel))

    async def nextion_write_wave(self, wave_id, channel, value):
        await self.send_command('add %s,%s,%s' % (wave_id, channel, value))

    async def nextion_ref_wave(self, stop_start):
        """stop_start: 'ref_stop' oder 'ref_star'"""
        if stop_start in ("ref_stop", "ref_star"):
            await self.send_command(stop_start)
        else:
            logger.info("NextionDisplay - ref_wave error: not ref_stop or ref_star: %s" % stop_start)

    async def nextion_write_number(self, label_name, integer):
        await self.send_command('%s.val=%s' % (label_name, integer))

    async def nextion_progressbar(self, barname, val):
        try:
            await self.send_command("%s.val=%s" % (barname, str(val)))
        except Exception as e:
            logger.warning('NextionDisplay - Nextionprogressbar: ' + str(e))

    async def nextion_show_hide_object(self, objectname, onoff):
        if onoff == "on":
            onoff = 1
        elif onoff == "off":
            onoff = 0
        else:
            logger.info("NextionDisplay - show_hide_object: onoff is not on or off: %s" % onoff)
        if onoff == 1 or onoff == 0:
            await self.send_command('vis %s,%s' % (objectname, onoff))

    async def nextion_get_page(self):
        command = str.encode('sendme')
        self.ser.write(command)
        self.ser.write(TERMINATOR)
        touch = self.ser.read_until(TERMINATOR)
        if len(touch) != 0:
            prefix = touch[0:1]
            pageID_touch = touch[1:2]
            logger.info("NextionDisplay - Nextiongetpage Prefix %s Page Number: %s" % (prefix, pageID_touch))


    # ======================================================================
    # Dubbleline-Hilfsmethode (extrahiert doppelten Code)
    # ======================================================================
    async def write_wave_with_thickness(self, wave_id, channel, value, dubbleline):
        """
        Schreibt einen Wert in den Wave-Kanal.
        Wenn dubbleline=True, wird ein zweiter Kanal (channel+1) mit value+1 geschrieben,
        um die Linie dicker erscheinen zu lassen.
        """
        await self.nextion_write_wave(wave_id, channel, str(round(value)))
        if dubbleline:
            await self.nextion_write_wave(wave_id, channel + 1, str(round(value + 1)))

    async def write_target_wave_point(self, wave_id, channel, target_value, targettemp,
                                      xpixel, dubbleline):
        """
        Schreibt einen Target-Temp-Punkt in den Wave-Graphen.
        Berücksichtigt Grenzen (0, xpixel) und targettemp==0.
        """
        if 0 < target_value < xpixel:
            await self.write_wave_with_thickness(wave_id, channel, target_value, dubbleline)
        elif targettemp == 0.00:
            await self.write_wave_with_thickness(wave_id, channel, 0, dubbleline)
        elif target_value >= xpixel:
            await self.write_wave_with_thickness(wave_id, channel, xpixel, dubbleline)

    # ======================================================================
    # writewave — aufgeteilt in Untermethoden
    # ======================================================================
    def update_temp_lists(self, currenttemp, targettemp):
        """Listen verwalten: Werte anhängen, bei erase leeren, bei Überlauf rotieren."""
        if self.erase:
            self.temp_list.clear()
            self.temp_list.append(currenttemp)
        elif len(self.temp_list) < WAVE_WIDTH:
            self.temp_list.append(currenttemp)
        else:
            self.temp_list.pop(0)
            self.temp_list.append(currenttemp)

        if self.erase:
            self.target_list.clear()
            self.target_list.append(targettemp)

        if len(self.target_list) < WAVE_WIDTH:
            self.target_list.append(targettemp)
        else:
            self.target_list.pop(0)
            self.target_list.append(targettemp)

        if DEBUG:
            logger.info('NextionDisplay - TempListe len: %s' % len(self.temp_list))

    def calculate_scale(self):
        """Min/Max/Faktor berechnen basierend auf den aktuellen Listen."""
        if self.targetfocus == "on":
            max_value_curr = round(float(max(self.temp_list)) + SCALE_MARGIN, 1)
            min_value_curr = round(float(min(self.temp_list)) - SCALE_MARGIN, 1)
            max_value_targ = round(float(max(self.target_list)) + SCALE_MARGIN, 1)
            min_value_targ = round(float(min(self.target_list)) - SCALE_MARGIN, 1)
            max_value = max(max_value_curr, max_value_targ)
            min_value = min(min_value_curr, min_value_targ)
        else:
            max_value = round(float(max(self.temp_list)) + SCALE_MARGIN, 1)
            min_value = round(float(min(self.temp_list)) - SCALE_MARGIN, 1)

        offset = max_value - min_value
        factor = WAVE_HEIGHT / offset if offset != 0 else 1

        return max_value, min_value, factor

    async def redraw_wave(self, min_value, factor, targettemp, dubbleline):
        """Komplettes Neuzeichnen des Graphen aus den gespeicherten Listen."""
        if DEBUG:
            logger.info('NextionDisplay - rewrite = %s' % self.rewrite)

        # Alle 4 Kanäle löschen
        await self.nextion_write_clear(1, 0)
        await self.nextion_write_clear(1, 1)
        await self.nextion_write_clear(1, 2)
        await self.nextion_write_clear(1, 3)

        await self.nextion_ref_wave("ref_stop")

        for i in range(len(self.temp_list)):
            # Aktuelle Temperatur
            digit = round((self.temp_list[i] - min_value) * factor, 2)
            await self.write_wave_with_thickness(1, 0, digit, dubbleline)

            if DEBUG:
                logger.info('NextionDisplay - liste[%s]: %s, digit: %s' % (i, self.temp_list[i], digit))

            # Target Temperatur
            target = round((self.target_list[i] - min_value) * factor, 2)
            await self.write_target_wave_point(1, 2, target, targettemp, WAVE_HEIGHT, dubbleline)

            if DEBUG:
                logger.info('NextionDisplay - target_list[%s]: %s, target: %s' % (i, self.target_list[i], target))

        await self.nextion_ref_wave("ref_star")

    async def append_wave_point(self, currenttemp, targettemp, min_value, factor, dubbleline):
        """Einzelnen neuen Punkt an den Graphen anhängen (kein Neuzeichnen)."""
        digit = round((currenttemp - min_value) * factor, 2)
        await self.write_wave_with_thickness(1, 0, digit, dubbleline)

        if DEBUG:
            logger.info('NextionDisplay - currenttemp: %s, digit: %s' % (currenttemp, digit))

        target = round((targettemp - min_value) * factor, 2)
        await self.write_target_wave_point(1, 2, target, targettemp, WAVE_HEIGHT, dubbleline)

        if DEBUG:
            logger.info("NextionDisplay - targettemp: %s, target: %s, xpixel: %s" % (targettemp, target, WAVE_HEIGHT))

    async def writewave(self,
                        current_temp_of_kettle_sensor_as_float,
                        kettle_current_temp_as_string,
                        kettle_target_temp_as_float,
                        kettle_target_temp_as_string,
                        current_kettle_name,
                        current_rest_name,
                        remaining_time_of_current_rest,
                        dubbleline=True):
        """Hauptmethode für Wave-Graph — orchestriert die Untermethoden."""

        currenttemp = current_temp_of_kettle_sensor_as_float
        targettemp = kettle_target_temp_as_float
        unit = "°" + str(await self.get_cbpi_temp_unit())

        # Textfelder auf der Brew-Seite aktualisieren
        await self.nextion_write_string("CurrTempBrwTxt", kettle_current_temp_as_string)
        await self.nextion_write_string("TargTempBrwTxt", kettle_target_temp_as_string)
        await self.nextion_write_string("KettleNameTxt", current_kettle_name)
        await self.nextion_write_string("RestNameTxt", current_rest_name)

        # Restzeit anzeigen
        is_timer_running = await self.is_timer_running(remaining_time_of_current_rest)
        if is_timer_running:
            await self.nextion_write_string("remBrewTime", remaining_time_of_current_rest)
        else:
            await self.nextion_write_string("remBrewTime", "")

        # 1) Listen aktualisieren
        self.update_temp_lists(currenttemp, targettemp)

        # 2) Skalierung berechnen
        max_value, min_value, factor = self.calculate_scale()

        # Min/Max/Durchschnitt Labels
        await self.nextion_write_string("tmax", "%s%s" % (max_value, unit))
        await self.nextion_write_string("tmin", "%s%s" % (min_value, unit))
        await self.nextion_write_string("tavarage", "%s%s" % (round((max_value + min_value) / 2, 1), unit))

        # 3) Graph zeichnen
        needs_redraw = (
            max_value != self.max_value_old
            or min_value != self.min_value_old
            or self.rewrite
        )

        if needs_redraw:
            await self.redraw_wave(min_value, factor, targettemp, dubbleline)
        else:
            await self.append_wave_point(currenttemp, targettemp, min_value, factor, dubbleline)

        # Alte Werte merken
        self.max_value_old = max_value
        self.min_value_old = min_value

        await asyncio.sleep(WAVE_SLEEP)


    # ======================================================================
    # Hauptloop
    # ======================================================================
    async def run(self):
        port = await self.set_serial_port_of_raspi()
        logger.info("NextionDisplay - Serial Port of Raspi: %s" % port)
        await asyncio.sleep(3)

        self.ser = serial.Serial(
            port=port,
            baudrate=SERIAL_BAUDRATE,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1
        )
        self.ser.reset_output_buffer()

        kettleID = await self.set_parameter_kettleID()
        logger.info("NextionDisplay - Kettle_ID: %s" % kettleID)

        dubbleline = await self.set_parameter_dubbleline()
        logger.info("NextionDisplay - dubbleline: %s" % dubbleline)

        version = await self.get_cbpi_version()
        logger.info("NextionDisplay - CBPI version: %s" % version)
        # Erster Wert wird vom Display verschluckt — Dummy senden
        await self.nextion_write_string("t1startfake", "start")
        await self.nextion_write_string("t1start", version)

        ip = await self.set_ip()
        iptext = "IP: %s" % ip
        logger.info("NextionDisplay - %s" % iptext)
        await self.nextion_write_string("t2start", iptext)

        # Zeit-Task starten (ersetzt Timethread)
        self._time_task = asyncio.create_task(self._time_loop())
        logger.info("NextionDisplay - time started")

        # *********************************************************************
        while True:
            try:
                kettleID = await self.set_parameter_kettleID()
                dubbleline = await self.set_parameter_dubbleline()
                self.count = self.count + 1
                logger.info("NextionDisplay - %s" % self.count)
                if self.count >= 10:         # pull ip every 10 times to save performance
                    ip = await self.set_ip()
                    iptext = "IP: %s" % ip
                    await self.nextion_write_string("t2start", iptext)
                    self.count = 0


                # Alle Werte sammeln
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

                await self.detect_touch()

                if current_temp_of_kettle_sensor_as_float < TEMP_SKIP_THRESHOLD:
                    await self.writewave(
                        current_temp_of_kettle_sensor_as_float,
                        kettle_current_temp_as_string,
                        kettle_target_temp_as_float,
                        kettle_target_temp_as_string,
                        current_kettle_name,
                        current_rest_name,
                        remaining_time_of_current_rest,
                        dubbleline)

                self.rewrite = False
                self.erase = False

                await self.writingDigittoNextion(
                    kettle_current_temp_as_string,
                    kettle_target_temp_as_string,
                    current_kettle_name)

                await self.writing_multi_to_nextion(
                    unit,
                    current_rest_name,
                    remaining_time_of_current_rest,
                    step_duration)

                await asyncio.sleep(1)

            except Exception as e:
                logger.error("NextionDisplay - Main loop error: %s" % e)
                await asyncio.sleep(5)


    # ======================================================================
    # writing_multi_to_nextion
    # ======================================================================
    async def writing_multi_to_nextion(self, unit, current_rest_name,
                                       remaining_time_of_current_rest, step_duration):
        await self.nextion_write_string("unitMBrew", str(unit))
        await self.nextion_write_string("StepnameMTxt", current_rest_name)

        kettle_json_obj = self.cbpi.kettle.get_state()
        kettles = kettle_json_obj['data']
        val = 0

        # Alle 4 Heater-Status-Icons ausschalten
        for x in range(4):
            heater_status_field_once = "heaterstatusM" + str(x + 1)
            await self.nextion_show_hide_object(heater_status_field_once, "off")

        i = 0
        while i < len(kettles):
            try:
                kettle_id = kettles[i]["id"]
                kettle_name_field = "KettlenMTxt" + str(i + 1)
                kettle_name = kettles[i]["name"]
                await self.nextion_write_string(kettle_name_field, kettle_name)

                current_temp_field = "CurrMTemp" + str(i + 1)
                kettle_sensor_id = kettles[i]["sensor"]
                sensor_value = self.cbpi.sensor.get_sensor_value(kettle_sensor_id).get('value')
                CurrMTemp = "%6.2f%s" % (sensor_value, "°")
                await self.nextion_write_string(current_temp_field, CurrMTemp)

                target_temp_field = "TarTempMTxt" + str(i + 1)
                kettle_target_temp = kettles[i]["target_temp"]
                TarTempMTxt = "%6.2f%s" % (kettle_target_temp, "°")
                await self.nextion_write_string(target_temp_field, TarTempMTxt)

                heater_status_field = "heaterstatusM" + str(i + 1)
                kettle = self.cbpi.kettle.find_by_id(kettle_id)
                heater = self.cbpi.actor.find_by_id(kettle.heater)
                kettle_heater_status = heater.instance.state

                if kettle_heater_status is True:
                    if DEBUG:
                        logger.info("NextionDisplay - writing_multi_to_nextion: heater status on")
                    await self.nextion_show_hide_object(heater_status_field, "on")
                else:
                    if DEBUG:
                        logger.info("NextionDisplay - writing_multi_to_nextion: heater status off")
                    await self.nextion_show_hide_object(heater_status_field, "off")

            except Exception as e:
                if DEBUG:
                    logger.error(e)
                    logger.info("NextionDisplay - writing_multi_to_nextion: no Kettle %s found" % i)
                heater_status_field = "heaterstatusM" + str(i + 1)
                await self.nextion_show_hide_object(heater_status_field, "off")

            i = i + 1

        try:
            is_timer_running = await self.is_timer_running(remaining_time_of_current_rest)
            if is_timer_running:
                await self.nextion_write_string("remBrewTime", remaining_time_of_current_rest)
                val = await self.multiprogressbarvalue(remaining_time_of_current_rest, step_duration)
            else:
                await self.nextion_write_string("remBrewTime", "")
                val = 0
        except Exception as e:
            logger.warning(e)

        # Progressbar
        await self.nextion_progressbar("RemainTimeMBar", val)

    # ======================================================================
    # writingDigittoNextion
    # ======================================================================
    async def writingDigittoNextion(self, kettle_current_temp_as_string,
                                    kettle_target_temp_as_string,
                                    current_kettle_name):
        try:
            await self.nextion_write_string("CurrTempTxt", kettle_current_temp_as_string)
            await self.nextion_write_string("TargetTempTxt", kettle_target_temp_as_string)
            await self.nextion_write_string("t3", current_kettle_name)
        except Exception as e:
            if DEBUG:
                logger.warning(e)

    # ======================================================================
    # multiprogressbarvalue
    # ======================================================================
    async def multiprogressbarvalue(self, remaining_time_of_current_rest, step_duration):
        if DEBUG:
            logger.info('NextionDisplay - remaining_time_of_current_rest: %s' % remaining_time_of_current_rest)
            logger.info('NextionDisplay - step_duration: %s' % step_duration)
        try:
            time_left = sum(x * int(t) for x, t in
                            zip([3600, 60, 1], remaining_time_of_current_rest.split(":")))
            time_left = int(time_left)
            step_duration = int(step_duration)
            val = int(100 - ((time_left * 100) / (step_duration * 60)))
            if DEBUG:
                logger.info('NextionDisplay - multiprogressbarvalue: %s%%' % val)
            return val
        except Exception as e:
            if DEBUG:
                logger.info('NextionDisplay - multiprogressbarvalue: no active step ' + str(e))
            return 0


    # ======================================================================
    # collect_all_values
    # ======================================================================
    async def collect_all_values(self, kettle_ID):
        unit = "°" + str(await self.get_cbpi_temp_unit())
        kettlevalues = await self.get_kettle_values(kettle_ID)
        stepvalues = await self.get_active_step_values()

        # Kettle Target Temp
        kettle_target_temp = kettlevalues['kettle_target_temp']
        kettle_target_temp_as_float = float("%6.2f" % (float(kettle_target_temp)))
        kettle_target_temp_formatted = "%6.2f%s" % (float(kettle_target_temp), unit)
        kettle_target_temp_formatted_as_string = str(kettle_target_temp_formatted)

        # Kettle Current Temp
        kettle_sensor_id = kettlevalues['kettle_sensor_id']
        current_temp_of_kettle_sensor = self.cbpi.sensor.get_sensor_value(kettle_sensor_id).get('value')
        current_temp_of_kettle_sensor_as_float = float("%6.2f" % (float(current_temp_of_kettle_sensor)))
        current_temp_of_kettle_sensor_formatted = "%6.2f%s" % (float(current_temp_of_kettle_sensor), unit)
        current_temp_of_kettle_sensor_formatted_as_string = str(current_temp_of_kettle_sensor_formatted)

        # Current Kettlename
        name_of_current_kettle = kettlevalues['kettle_name']

        # Active Stepname
        active_step_name = stepvalues['active_step_name']

        # Remaining time
        step_state = stepvalues['active_step_state_text']
        remaining_time = step_state.replace("Status: ", "")

        # Step duration
        step_duration = stepvalues['active_step_timer_value']

        return {
            'current_temp_of_kettle_sensor_formatted_as_string': current_temp_of_kettle_sensor_formatted_as_string,
            'current_temp_of_kettle_sensor_as_float': current_temp_of_kettle_sensor_as_float,
            'kettle_target_temp_formatted_as_string': kettle_target_temp_formatted_as_string,
            'kettle_target_temp_as_float': kettle_target_temp_as_float,
            'name_of_current_kettle': name_of_current_kettle,
            'active_step_name': active_step_name,
            'remaining_time': remaining_time,
            'step_duration': step_duration,
            'temp_unit': unit
        }

    # ======================================================================
    # is_timer_running
    # ======================================================================
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

    # ======================================================================
    # target_temp_of_kettle_sensor (aktuell nicht verwendet)
    # ======================================================================
    async def target_temp_of_kettle_sensor(self, kettle_ID):
        kettlevalues = await self.get_kettle_values(kettle_ID)
        kettle_target_temp = kettlevalues['kettle_target_temp']
        kettle_target_temp_formatted = "%6.2f" % float(kettle_target_temp)
        return kettle_target_temp_formatted

    # ======================================================================
    # IP-Ermittlung
    # ======================================================================
    async def get_ip(self, interface):
        ip_addr = 'Not connected'
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            ip_addr = socket.inet_ntoa(
                fcntl.ioctl(so.fileno(), 0x8915,
                            struct.pack('256s', bytes(interface.encode())[:15]))[20:24])
        except Exception as e:
            logger.warning('NextionDisplay - no ip found')
            if DEBUG:
                logger.warning(e)
            return ip_addr
        finally:
            so.close()
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
        return ip


    # ======================================================================
    # CBPI Hilfsmethoden
    # ======================================================================
    async def get_cbpi_temp_unit(self):
        try:
            unit = self.cbpi.config.get("TEMP_UNIT", None)
        except Exception as e:
            logger.warning('no cbpi temp. unit found')
            logger.warning(e)
            unit = "na"
        return unit

    async def get_breweryname(self):
        try:
            brewery = self.cbpi.config.get("BREWERY_NAME", None)
        except Exception as e:
            logger.warning('NextionDisplay - no breweryname found')
            logger.warning(e)
            brewery = "no name"
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

            i = 0
            result = 'no active step'
            while i < len(steps):
                if steps[i]["status"] == "A":
                    active_step_name = steps[i]["name"]
                    active_step_status = steps[i]["status"]
                    active_step_state_text = steps[i]["state_text"]
                    active_step_target_temp = steps[i]["props"]["Temp"]
                    active_step_timer_value = steps[i]["props"]["Timer"]
                    active_step_probs = steps[i]["props"]
                    return {
                        'active_step_name': active_step_name,
                        'active_step_status': active_step_status,
                        'active_step_state_text': active_step_state_text,
                        'active_step_target_temp': active_step_target_temp,
                        'active_step_timer_value': active_step_timer_value,
                        'active_step_probs': active_step_probs
                    }
                else:
                    result = {
                        'active_step_name': 'no active step',
                        'active_step_state_text': "",
                        'active_step_timer_value': ""
                    }
                i = i + 1
            return result

        except Exception as e:
            logger.warning(e)
            return {
                'active_step_name': 'error',
                'active_step_status': 'error',
                'active_step_state_text': 'error',
                'active_step_target_temp': 'error',
                'active_step_timer_value': 'error',
                'active_step_probs': 'error'
            }

    async def get_kettle_values(self, kettle_id):
        try:
            kettle_json_obj = self.cbpi.kettle.get_state()
            kettles = kettle_json_obj['data']
            i = 0
            result = None
            while i < len(kettles):
                if kettles[i]["id"] == kettle_id:
                    return {
                        'kettle_id': kettles[i]["id"],
                        'kettle_name': kettles[i]["name"],
                        'kettle_heater_id': kettles[i]["heater"],
                        'kettle_sensor_id': kettles[i]["sensor"],
                        'kettle_target_temp': kettles[i]["target_temp"]
                    }
                else:
                    result = 'no kettle found with id %s' % kettle_id
                i = i + 1
            return result
        except Exception as e:
            logger.warning(e)
            return {
                'kettle_id': 'error',
                'kettle_name': 'error',
                'kettle_heater_id': 'error',
                'kettle_sensor_id': 'error',
                'kettle_target_temp': 'error'
            }

    async def get_sensor_values_by_id(self, sensor_id):
        try:
            sensor_json_obj = self.cbpi.sensor.get_state()
            sensors = sensor_json_obj['data']
            i = 0
            while i < len(sensors):
                if sensors[i]["id"] == sensor_id:
                    sensor_type = sensors[i]["type"]
                    sensor_name = sensors[i]["name"]
                    sensor_props = sensors[i]["props"]
                    sensor_value = self.cbpi.sensor.get_sensor_value(sensor_id).get('value')
                    return {
                        'sensor_id': sensor_id,
                        'sensor_name': sensor_name,
                        'sensor_type': sensor_type,
                        'sensor_value': sensor_value,
                        'sensor_props': sensor_props
                    }
                i = i + 1
        except Exception as e:
            logger.info(e)
            return {
                'sensor_id': 'error',
                'sensor_name': 'error',
                'sensor_type': 'error',
                'sensor_value': 'error',
                'sensor_props': 'error'
            }
        await asyncio.sleep(1)


    # ======================================================================
    # Konfiguration / Parameter
    # ======================================================================
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
                    logger.warning(
                        'NextionDisplay - set_parameter_kettleID: no value for Kettle_ID, used MASH TUN')
            except Exception as e:
                logger.warning('NextionDisplay - set_parameter_kettleID: Unable to update config')
                logger.warning(e)
        return kettle_id

    async def set_parameter_dubbleline(self):
        dubbleline = self.cbpi.config.get("NEXTION_bold_line", None)
        if dubbleline is None:
            dubbleline = "on"
            try:
                await self.cbpi.config.add("NEXTION_bold_line", "on", ConfigType.SELECT,
                                           "Turn on/off bold line in graph",
                                           [{"label": "on", "value": "on"},
                                            {"label": "off", "value": "off"}])
                logger.info("NextionDisplay - NEXTION_bold_line added to settings")
                dubbleline = self.cbpi.config.get("NEXTION_bold_line", None)
            except Exception as e:
                logger.warning('NextionDisplay - set_parameter_dubbleline: Unable to update config')
                logger.warning(e)

        if dubbleline == "on":
            return True
        else:
            await self.nextion_write_clear(1, 1)  # BrewTemp thickness line
            await self.nextion_write_clear(1, 3)  # BrewTarget thickness line
            return False

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
        return port

    async def set_targetfocus(self):
        targetfocus = self.cbpi.config.get("NEXTION_Target_Focus", None)
        if targetfocus is None:
            targetfocus = "off"
            try:
                await self.cbpi.config.add("NEXTION_Target_Focus", "off", ConfigType.SELECT,
                                           "Turn on/off NEXTION_Target_Focus no Reboot necessary",
                                           [{"label": "on", "value": "on"},
                                            {"label": "off", "value": "off"}])
                logger.info("NextionDisplay - NEXTION_Target_Focus added")
                targetfocus = self.cbpi.config.get("NEXTION_Target_focus", None)
            except Exception as e:
                logger.warning('NextionDisplay - NEXTION_Target_Focus: Unable to update config')
                logger.warning(e)
        return targetfocus


    # ======================================================================
    # detect_touch
    # ======================================================================
    async def detect_touch(self):
        # read_until mit timeout=0.1 blockiert maximal 100ms — akzeptabel für den Raspi
        touch = self.ser.read_until(TERMINATOR)

        if len(touch) != 0:
            istouch = touch[0:1]
            istouch = str(istouch)
            istouch = istouch.lstrip("'b\\x")
            istouch = istouch.rstrip("\\xff\\xff\\xff\\'")
            istouch = str(istouch)

            if istouch == "e":
                logger.info("NextionDisplay - touch: A button has been pushed %s" % istouch)

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

                logger.info("NextionDisplay - page:%s, component:%s, event:%s"
                            % (pageID_touch, compID_touch, event_touch))

                if (pageID_touch == "01" or pageID_touch == "05") and compID_touch == "05":
                    logger.info("NextionDisplay - touch: Clearbutton of Brewpage pushed")
                    self.erase = True
                elif pageID_touch == "00" and compID_touch == "03":
                    logger.info("NextionDisplay - touch: Brewpage button pushed")
                    self.rewrite = True
                elif (pageID_touch == "01" or pageID_touch == "05") and compID_touch == "11":
                    logger.info("NextionDisplay - touch: Focusbutton of Brewpage pushed")
                    if self.targetfocus == "off":
                        self.targetfocus = "on"
                    else:
                        self.targetfocus = "off"
                elif (pageID_touch == "03" and compID_touch == "03") or \
                     (pageID_touch == "06" and compID_touch == "04"):
                    logger.info("NextionDisplay - touch: Clearbutton of Fermpage pushed")
                    # writefermwave(ser, erase=True) todo
                elif pageID_touch == "00" and compID_touch == "05":
                    logger.info("NextionDisplay - touch: Fermpage button pushed")
                    # writefermwave(ser, erase=False, frewrite=True) todo

        await asyncio.sleep(1)

    # ======================================================================
    # Shutdown
    # ======================================================================
    async def shutdown(self):
        """Aufräumen beim Beenden."""
        if self._time_task:
            self._time_task.cancel()
            await asyncio.gather(self._time_task, return_exceptions=True)

        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("NextionDisplay - Serial port closed")


def setup(cbpi):
    cbpi.plugin.register("NEXTIONDisplay", NEXTIONDisplay)
