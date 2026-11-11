# -*- coding: utf-8 -*-
import os
from subprocess import Popen, PIPE, call

from modules import cbpi, app
from modules.core.hardware import SensorPassive
import json
import os, re, threading, time
from flask import Blueprint, render_template, request
from modules.core.props import Property

blueprint = Blueprint('one_wire', __name__)

temp = 22

# Use the unpatched Thread and sleep so sensor reads happen in real OS threads
# and don't block eventlet's cooperative event loop.
try:
    from eventlet.patcher import original as _orig
    _Thread = _orig('threading').Thread
    _sleep = _orig('time').sleep
except (ImportError, AttributeError):
    _Thread = threading.Thread
    _sleep = time.sleep


def getSensors():
    try:
        arr = []
        for dirname in os.listdir('/sys/bus/w1/devices'):
            if (dirname.startswith("28") or dirname.startswith("10")):
                cbpi.app.logger.info("Device %s Found (Family: 28/10, Thermometer on GPIO4 (w1))" % dirname)
                arr.append(dirname)
        return arr
    except:
        return []


class myThread(_Thread):

    value = 0

    def __init__(self, sensor_name):
        _Thread.__init__(self)
        self.daemon = True
        self.value = 0
        self.sensor_name = sensor_name
        self.runnig = True

    def shutdown(self):
        pass

    def stop(self):
        self.runnig = False

    def run(self):
        while self.runnig:
            try:
                if self.sensor_name is None:
                    _sleep(4)
                    continue
                sensor_path = '/sys/bus/w1/devices/w1_bus_master1/%s/w1_slave' % self.sensor_name
                # This read blocks for ~750 ms (DS18B20 conversion time).
                # Running in a real OS thread keeps the eventlet event loop responsive.
                with open(sensor_path, 'r') as content_file:
                    content = content_file.read()
                if content.split('\n')[0].split(' ')[11] == "YES":
                    self.value = float(content.split("=")[-1]) / 1000
            except Exception as e:
                try:
                    app.logger.error("1-wire read error for %s: %s", self.sensor_name, e)
                except Exception:
                    pass
            _sleep(4)


@cbpi.sensor
class ONE_WIRE_SENSOR(SensorPassive):

    sensor_name = Property.Select("Sensor", getSensors(), description="The OneWire sensor address.")
    offset = Property.Number("Offset", True, 0, description="Offset which is added to the received sensor data. Positive and negative values are both allowed.")

    def init(self):

        self.t = myThread(self.sensor_name)

        def shudown():
            shudown.cb.shutdown()
        shudown.cb = self.t

        self.t.start()

    def stop(self):
        try:
            self.t.stop()
        except:
            pass

    def read(self):
        if self.get_config_parameter("unit", "C") == "C":
            self.data_received(round(self.t.value + self.offset_value(), 2))
        else:
            self.data_received(round(9.0 / 5.0 * self.t.value + 32 + self.offset_value(), 2))

    @cbpi.try_catch(0)
    def offset_value(self):
        return float(self.offset)

    @classmethod
    def init_global(self):
        try:
            call(["modprobe", "w1-gpio"])
            call(["modprobe", "w1-therm"])
        except Exception as e:
            pass


@blueprint.route('/<int:t>', methods=['GET'])
def set_temp(t):
    global temp
    temp = t
    return ('', 204)


@cbpi.initalizer()
def init(cbpi):
    cbpi.app.register_blueprint(blueprint, url_prefix='/api/one_wire')
