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
from process_wrangler import ManagedProcess

phandles = []

d = datetime.datetime.now()
TS_BASE = d.isoformat("T").replace(":","")


def signal_handler(signal, frame):
    print("Ending due to sigint")
    for p in phandles:
        p.kill()

    ManagedProcess.system_shutdown()
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
        self.process_device = None
        self.process_command = None
        self.v4l2_ctl = None
        self.should_record = False
        self.network_port = 5800

        # If a camera supports mjpeg while recording, we don't do any extra encoding
        self.mjpeg_gstpipe = ""
    def __repr__(self):
        return str(self.name) + ": " + str(self.device)
    def gstCommandLine(self):
        capabilities_ex = ""
        tee_chunks = ""


        base_pipe = ['gst-launch-1.0 v4l2src device=%(device)s',
                     '\'%(capabilities)s\'%(capabilities_ex)s']


        # Tee off a recording stream
        if self.should_record:
            capabilities_ex += " ! queue ! tee name=record"
            filename = "/storage/videos/" + self.name + "-" + TS_BASE + ".mkv"
            tee_chunks += " record. ! queue ! h264parse ! matroskamux ! filesink location={}".format(filename)

        capabilities_ex += " ! omxh264dec ! nvvidconv ! video/x-raw,width=640,height=360"

        if self.process_command:
            capabilities_ex += " ! queue ! tee name=process"
            tee_chunks += " process. ! queue ! v4l2sink sync=false device=/dev/{}".format(self.process_device)

        capabilities_ex += " ! omxh264enc target-bitrate=1000000 ! rtph264pay name=pay0 pt=96 config-interval=1 ! udpsink host=224.1.1.1 auto-multicast=true port={}".format(self.network_port)

        return (" ! ".join(base_pipe)) %\
                {'device': self.device,
                'capabilities': self.capabilities,
                'capabilities_ex': capabilities_ex,
                'network_port':str(self.network_port)} + tee_chunks


config = yaml.load(file('/etc/ocupus.yml', 'r'))

time.sleep(0.25)

system_devices = get_video_devices()

ports = dict()

for sd in system_devices:
    ports[system_devices[sd].port_connection] = "/dev/" + sd

cameras = dict()

cur_port = 0

for x in config['cameras']:
    name = x['name']
    cam = Camera()
    cam.name = name

    cam.port = x.get('port')

    cam.capabilities = x.get('capabilities')
    cam.v4l2_ctl = x.get('v4l2settings')
    cam.process_command = x.get('processor')
    cam.should_record = x.get('record', False)
    cam.network_port = 5800 + cur_port
    cur_port += 1

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

subprocess.check_call(["modprobe", "v4l2loopback", "devices=%d" % len(cameras)])
try:
    subprocess.check_call(["mount", "/dev/sda1", "/storage"])
except:
    pass

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
    cameras[c].process_device = v4l2loopback_devices.pop()

    print("======================= Connecting camera %s gstreamer =======================" % cameras[c].name)
    print(cameras[c].gstCommandLine())
    ManagedProcess(cameras[c].gstCommandLine(), "gstreamer", cameras[c].name, True).start()
    time.sleep(0.5)


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
#ManagedProcess("python /home/odroid/ocupus/flask/app.py", "servers", "flask", True).start()
#time.sleep(0.1)

# Fire up the video vacuum
#ManagedProcess("python /home/odroid/ocupus/scripts/video_compactor.py", "utilities", "video_compactor", True).start()

#system_utilities.run_camera_control()
peerconnection_client.monitor_system_requests()
