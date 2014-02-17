#!/usr/bin/python

import time
import ConfigParser, os
from v4l2sniffer import get_video_devices
import subprocess
import os
import shlex
import signal
import sys

phandles = []

def signal_handler(signal, frame):
    print("Ending due to sigint")
    for p in phandles:
        p.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Fire up the server
proc = subprocess.Popen([os.path.expanduser('~/peerconnection_server')])
phandles.append(proc)
time.sleep(0.1)

proc = subprocess.Popen(["python","../flask/app.py"])
phandles.append(proc)
time.sleep(0.1)


class Camera:
    def __init__(self):
        self.name = None
        self.port = None
        self.capabilities = "video/x-raw,width=320,height=240,framerate=30/1"
        self.device = None
        self.webrtc_device = None
        self.process_device = None
    def __repr__(self):
        return str(self.name) + ": " + str(self.device)

config = ConfigParser.ConfigParser()
config.read([os.path.expanduser('~/ocupus.cfg')])

system_devices = get_video_devices()

ports = dict()

for sd in system_devices:
    ports[system_devices[sd].port_connection] = "/dev/" + sd

cameras = dict()

for x in config.sections():
    if x.startswith("Camera "):
        name = x[7:]
        cam = Camera()
        cam.name = name
        cam.port = config.get(x, 'port')
        cam.capabilities = config.get(x, 'capabilities')
        if cam.port in ports:
            cam.device = ports[cam.port]
            del ports[cam.port]
            cameras[cam.name] = cam

unknown_count = 0

for sd in system_devices:
    if system_devices[sd].port_connection in ports:
        cam = Camera()
        cam.name = "Unknown%d" % unknown_count
        unknown_count += 1
        cam.port = system_devices[sd].port_connection
        cam.device = ports[cam.port]
        cameras[cam.name] = cam

try:
    subprocess.check_call(["rmmod", "v4l2loopback"])
except:
    pass

current_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

subprocess.check_call(["modprobe", "v4l2loopback", "devices=%d" % (len(cameras) * 2)])

v4l2loopback_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

v4l2loopback_devices.difference_update(current_devices)

for c in cameras:
    cameras[c].webrtc_device = v4l2loopback_devices.pop()
    cameras[c].process_device = v4l2loopback_devices.pop()
    print("======================= Connecting camera %s to webrtc_dev =======================" % cameras[c].name)

    args = shlex.split('gst-launch-1.0 -v v4l2src device=' + 
        cameras[c].device + ' ! ' + cameras[c].capabilities + 
        ' ! tee name=t ! queue ! v4l2sink device=/dev/' + cameras[c].webrtc_device +
        ' t. ! queue ! v4l2sink device=/dev/' + cameras[c].process_device)
    proc = subprocess.Popen(args)
    phandles.append(proc)
    # Hopefully this will give time to properly sync up the log statement above
    time.sleep(0.100)

time.sleep(0.5)

for c in cameras:
    print("======================= Connecting camera %s to peerconnection =======================" % cameras[c].name)

    print(os.path.expanduser('~/peerconnection_client'))

    args = shlex.split(os.path.expanduser('~/peerconnection_client') + 
    	' --server localhost --port 8888 --clientname "' + cameras[c].name + 
    	'" --videodevice /dev/' + cameras[c].webrtc_device)
    proc = subprocess.Popen(args)
    phandles.append(proc)

    time.sleep(0.100)

while True:
    time.sleep(5)
