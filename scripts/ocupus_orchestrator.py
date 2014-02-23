#!/usr/bin/python

import time
import ConfigParser, os
from v4l2sniffer import get_video_devices
import subprocess
import os
import shlex
import signal
import sys
import datetime

BIN_DIR='/home/odroid/ocupus/bin/armv7-neon/'

phandles = []

def signal_handler(signal, frame):
    print("Ending due to sigint")
    for p in phandles:
        p.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Fire up the server
proc = subprocess.Popen([BIN_DIR + 'peerconnection_server'])
phandles.append(proc)
time.sleep(0.1)

proc = subprocess.Popen(["python","/home/odroid/ocupus/flask/app.py"])
phandles.append(proc)
time.sleep(0.1)

class Camera:
    def __init__(self):
        self.name = None
        self.port = None
        self.capabilities = "video/x-raw-yuv,width=320,height=240"
        self.device = None
        self.webrtc_device = None
        self.process_device = None
        self.process_command = None
        self.v4l2_ctl = None
        self.should_record = False
    def __repr__(self):
        return str(self.name) + ": " + str(self.device)
    def gstCommandLine(self):
        if not self.should_record:
            return (" ! ".join(['gst-launch-0.10 v4l2src device=%(device)s',
                '%(capabilities)s', 
                'tee name=t', 
                'queue2', 
                'v4l2sink sync=false device=/dev/%(webrtc_device)s t.',
                'queue2',  
                'v4l2sink sync=false device=/dev/%(process_device)s'])) %\
                    {'device': self.device, 
                    'capabilities': self.capabilities,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device}
        else:
            d = datetime.datetime.now()
            ts = d.isoformat("T")
            filename = self.name + "-" + ts + ".webm"
            return (" ! ".join(['gst-launch-0.10 v4l2src device=%(device)s',
                '%(capabilities)s', 
                'tee name=t', 
                'queue2',
                'tee name=writer', 
                'queue2',                 
                'v4l2sink sync=false device=/dev/%(webrtc_device)s t.',
                'queue2',  
                'v4l2sink sync=false device=/dev/%(process_device)s writer.',
                'ffmpegcolorspace', 
                'vp8enc', 
                'webmmux name=mux', 
                'filesink location=%(filename)s', 
                'mux.'])) %\
                    {'device': self.device, 
                    'capabilities': self.capabilities,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device,
                    'filename': filename}


config = ConfigParser.ConfigParser()
config.read(['/home/odroid/ocupus/config/ocupus.cfg'])

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

        options = config.options(x)

        if 'capabilities' in options:
            cam.capabilities = config.get(x, 'capabilities')
        if 'v4l2settings' in options:
            cam.v4l2_ctl = config.get(x, 'v4l2settings')
        if 'processor' in options:
            cam.process_command = config.get(x, 'processor')
        if 'record' in options:
            cam.should_record = True

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

        cam.name += "::" + str(cam.port)
        cameras[cam.name] = cam

try:
    subprocess.check_call(["rmmod", "v4l2loopback"])
except:
    pass

current_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

subprocess.check_call(["modprobe", "v4l2loopback", "devices=%d" % (len(cameras) * 2)])


time.sleep(3)
v4l2loopback_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

v4l2loopback_devices.difference_update(current_devices)

# Configure the camers
for c in [z for z in cameras if cameras[z].v4l2_ctl]:
    print("======================= Setting v4l2 controls for %s =======================" % cameras[c].name)

    args = shlex.split("v4l2-ctl -d " + cameras[c].device + " " + cameras[c].v4l2_ctl)
    proc = subprocess.call(args)


# Set up the camers for splitting
for c in cameras:
    cameras[c].webrtc_device = v4l2loopback_devices.pop()
    cameras[c].process_device = v4l2loopback_devices.pop()
    print("======================= Connecting camera %s gstreamer =======================" % cameras[c].name)


    
    args = shlex.split(cameras[c].gstCommandLine())

    proc = subprocess.Popen(args)
    phandles.append(proc)
    # Hopefully this will give time to properly sync up the log statement above
    time.sleep(0.100)

# Spawn the clients
for c in cameras:
    print("======================= Connecting camera %s to peerconnection =======================" % cameras[c].name)

    args = shlex.split(BIN_DIR+'peerconnection_client' + 
    	' --server localhost --port 8888 --clientname "' + cameras[c].name + 
    	'" --videodevice /dev/' + cameras[c].webrtc_device)
    proc = subprocess.Popen(args)
    phandles.append(proc)
    time.sleep(0.100)

# Start subprocessors
for c in [z for z in cameras if cameras[z].process_command]:
    print("======================= Connecting camera %s to processor =======================" % cameras[c].name)

    processor_env = os.environ.copy()
    
    processor_env["OCUPUS_CAMERA_DEV"] = cameras[c].process_device
    args = shlex.split(cameras[c].process_command)
    proc = subprocess.Popen(args, env=processor_env)
    phandles.append(proc)
    time.sleep(0.100)


while True:
    time.sleep(5)

