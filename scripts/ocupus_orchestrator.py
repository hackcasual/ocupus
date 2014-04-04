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
import yaml
import system_utilities

BIN_DIR='/home/odroid/ocupus/bin/armv7-neon/'

phandles = []

d = datetime.datetime.now()
TS_BASE = d.isoformat("T").replace(":","")


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
        self.capabilities = "video/x-raw,width=320,height=240"
        self.device = None
        self.webrtc_device = None
        self.process_device = None
        self.process_command = None
        self.v4l2_ctl = None
        self.should_record = False
        self.capture_audio = False

        # If a camera supports mjpeg while recording, we don't do any extra encoding
        self.mjpeg_gstpipe = ""
    def __repr__(self):
        return str(self.name) + ": " + str(self.device)
    def gstCommandLine(self):
        capabilities_ex = ""

        # Tee off a recording stream
        if self.should_record:
            capabilities_ex += " ! queue2 ! tee name=mjpeg"

        if self.capabilities.find("jpeg") >= 0:
            # Convert to raw format for the other systems
            capabilities_ex += " ! jpegdec ! videoconvert ! video/x-raw,format=I420"
        elif self.should_record:
            # If we're not capturing with jpeg we'll have to encode first
            self.mjpeg_gstpipe = " ! jpegenc"

        # Capture to a matroska container to capture frame timestamps
        filename = "/home/odroid/Videos/" + self.name + "-" + TS_BASE + ".mkv"

        # Common pipeline for all cameras
        base_gstreamer = " ! ".join(['gst-launch-1.0 v4l2src device=%(device)s do-timestamp=true',
            '%(capabilities)s%(capabilities_ex)s', 
            'tee name=t', 
            'queue2', 
            'v4l2sink sync=false device=/dev/%(webrtc_device)s t.',
            'queue2',  
            'v4l2sink sync=false device=/dev/%(process_device)s'])

        if not self.should_record:
            return base_gstreamer % {'device': self.device, 
                    'capabilities': self.capabilities,
                    'capabilities_ex': capabilities_ex,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device}
        elif not self.capture_audio:
            return (base_gstreamer + " ! ".join([' mjpeg.%(mjpeg_gstpipe)s',
                'queue2',
                'matroskamux',
                'filesink sync=false location=%(filename)s'])) %\
                    {'device': self.device, 
                    'capabilities': self.capabilities,
                    'capabilities_ex': capabilities_ex,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device,
                    'mjpeg_gstpipe': self.mjpeg_gstpipe,
                    'filename': filename}
        else:
            # Ugly hack for now, but on the Odroid XU it seems 
            # we'll always get a USB audio device for recording on 0,0
            return (base_gstreamer + " ! ".join([' mjpeg.%(mjpeg_gstpipe)s',
                'queue2',
                'mux. alsasrc device=hw:0,0', 
                'queue2',
                'audioconvert',
                'vorbisenc',
                'queue2',
                'mux. matroskamux name=mux',
                'filesink sync=false location=%(filename)s'])) %\
                    {'device': self.device, 
                    'capabilities': self.capabilities,
                    'capabilities_ex': capabilities_ex,
                    'webrtc_device': self.webrtc_device,
                    'process_device': self.process_device,
                    'mjpeg_gstpipe': self.mjpeg_gstpipe,
                    'filename': filename}
#mux. alsasrc device=hw:0,0 ! queue2 ! audioconvert ! vorbisenc ! queue ! mux. matroskamux name=mux !

config = yaml.load(file('/home/odroid/ocupus/config/ocupus.yml', 'r'))

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

for x in config['cameras']:
    name = x['name']
    cam = Camera()
    cam.name = name

    cam.port = x.get('port')

    cam.capabilities = x.get('capabilities')
    cam.v4l2_ctl = x.get('v4l2settings')
    cam.process_command = x.get('processor')
    cam.should_record = x.get('record', False)
    cam.capture_audio = x.get('capture_audio', False)

    if cam.port in ports:
        cam.device = ports[cam.port]
        del ports[cam.port]
        cameras[cam.name] = cam

unknown_count = 0

for sd in system_devices:
    if system_devices[sd].port_connection in ports:
        cam = Camera()
        cam.name = "Unknown"
 
        unknown_count += 1
        cam.port = system_devices[sd].port_connection
        cam.device = ports[cam.port]

        cam.name += str(cam.port)
        cameras[cam.name] = cam

try:
    subprocess.check_call(["rmmod", "v4l2loopback"])
except:
    pass

current_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

subprocess.check_call(["modprobe", "v4l2loopback", "devices=%d" % (len(cameras) * 2)])

# This is voodoo and should be removed when sufficient testing can be done
time.sleep(1)
v4l2loopback_devices = {x for x in os.listdir("/dev/") if x.startswith("video")}

v4l2loopback_devices.difference_update(current_devices)

system_utilities.setup_cameras(cameras)

# Configure the cameras
for c in [z for z in cameras if cameras[z].v4l2_ctl]:
    print("======================= Setting v4l2 controls for %s =======================" % cameras[c].name)

    args = shlex.split("v4l2-ctl -d " + cameras[c].device + " " + cameras[c].v4l2_ctl)
    proc = subprocess.call(args)


# Set up the cameras for splitting
for c in cameras:
    cameras[c].webrtc_device = v4l2loopback_devices.pop()
    cameras[c].process_device = v4l2loopback_devices.pop()

    print("======================= Connecting camera %s gstreamer =======================" % cameras[c].name)

    print cameras[c].gstCommandLine()
    
    args = shlex.split(cameras[c].gstCommandLine())

    proc = subprocess.Popen(args)
    phandles.append(proc)
    # Hopefully this will give time to properly sync up the log statement above
    time.sleep(2.0)

# Spawn the clients
for c in cameras:
    print("======================= Connecting camera %s to peerconnection =======================" % cameras[c].name)

    args = shlex.split(BIN_DIR+'peerconnection_client' + 
        ' --server localhost --port 8888 --clientname "' + cameras[c].name + 
        '" --videodevice /dev/' + cameras[c].webrtc_device)
    proc = subprocess.Popen(args)
    phandles.append(proc)
    time.sleep(2.0)

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

# Fire up the video vacuum
proc = subprocess.Popen(["python","/home/odroid/ocupus/scripts/video_compactor.py"])
phandles.append(proc)
system_utilities.run_camera_control()
peerconnection_client.monitor_system_requests()
