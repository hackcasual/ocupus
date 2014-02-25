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
import peerconnection_client
import code
import traceback

BIN_DIR='/home/odroid/ocupus/bin/armv7-neon/'

phandles = []

def signal_handler(signal, frame):
    print("Ending due to sigint")
    for p in phandles:
        p.kill()
    sys.exit(0)


def debug(sig, frame):
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d={'_frame':frame}         # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    i = code.InteractiveConsole(d)
    message  = "Signal recieved : entering python shell.\nTraceback:\n"
    message += ''.join(traceback.format_stack(frame))
    i.interact(message)


signal.signal(signal.SIGUSR1, debug)  # Register handler

signal.signal(signal.SIGINT, signal_handler)


class Camera:
    def __init__(self):
        self.name = None
        self.port = None
        self.capabilities = "video/x-raw-yuv,width=320,height=240"
        self.device = None
        self.webrtc_device = None
        self.process_device = None
        self.process_command = None
        self.recording_device = None
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
            return (" ! ".join(['gst-launch-0.10 v4l2src device=%(device)s',
                '%(capabilities)s', 
                'tee name=t', 
                'queue2',
                'tee name=writer', 
                'queue2',                 
                'v4l2sink sync=false device=/dev/%(webrtc_device)s t.',
                'queue2',  
                'v4l2sink sync=false device=/dev/%(process_device)s writer.',
                'queue2',
                'v4l2sink sync=false device=/dev/%(recording_device)s'])) %\
                    {'device': self.device, 
                    'capabilities': self.capabilities,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device,
                    'recording_device': self.recording_device}


config = ConfigParser.ConfigParser()
config.read(['/home/odroid/ocupus/config/ocupus.cfg'])

# Fire up the server
proc = subprocess.Popen([BIN_DIR + 'peerconnection_server'])
phandles.append(proc)
time.sleep(0.1)

# Launch our ZMQ adapter for the peerconnection client
peerconnection_client.setup()

time.sleep(0.25)

system_devices = get_video_devices()

ports = dict()

for sd in system_devices:
    ports[system_devices[sd].port_connection] = "/dev/" + sd

cameras = dict()

recording_devices = 0

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
            recording_devices += 1

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

subprocess.check_call(["modprobe", "v4l2loopback", "devices=%d" % (len(cameras) * 2 + recording_devices)])

# This is voodoo and should be removed when sufficient testing can be done
time.sleep(1)
v4l2loopback_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

v4l2loopback_devices.difference_update(current_devices)

# Configure the cameras
for c in [z for z in cameras if cameras[z].v4l2_ctl]:
    print("======================= Setting v4l2 controls for %s =======================" % cameras[c].name)

    args = shlex.split("v4l2-ctl -d " + cameras[c].device + " " + cameras[c].v4l2_ctl)
    proc = subprocess.call(args)


# Set up the cameras for splitting
for c in cameras:
    cameras[c].webrtc_device = v4l2loopback_devices.pop()
    cameras[c].process_device = v4l2loopback_devices.pop()
    if cameras[c].should_record:
        cameras[c].recording_device = v4l2loopback_devices.pop()

    print("======================= Connecting camera %s gstreamer =======================" % cameras[c].name)

    print cameras[c].gstCommandLine()
    
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

# Start flask after we've got the processors and local clients online
proc = subprocess.Popen(["python","/home/odroid/ocupus/flask/app.py"])
phandles.append(proc)
time.sleep(0.1)

# Start subprocessors
for c in [z for z in cameras if cameras[z].should_record]:
    d = datetime.datetime.now()
    ts = d.isoformat("T")
    filename = "/home/odroid/Videos/" + cameras[c].name + "-" + ts + ".webm"

    print("======================= Recording %s to %s =======================" % (cameras[c].name, filename))
    args = shlex.split(
        "avconv -v error -f video4linux2 -i /dev/%(recording_device)s -cpu-used -5 -c:v libvpx -b:v 2048k %(filename)s" %\
        {"recording_device":cameras[c].recording_device,
         "filename":filename})
    proc = subprocess.Popen(args)
    phandles.append(proc)
    time.sleep(0.100)

peerconnection_client.monitor_system_requests()
