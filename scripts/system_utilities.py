import subprocess
import zmq
import json
import yaml
from multiprocessing import Process, Value, Queue
import shlex

system_cameras = None

def setup_cameras(cameras):
    global system_cameras
    system_cameras = cameras

def get_traffic_info():
    try:
        ifconfig_info = subprocess.check_output(['ifconfig','eth0'], stderr=subprocess.STDOUT)

        rx_off = ifconfig_info.find("RX bytes:") + len("RX bytes:")
        tx_off = ifconfig_info.find("TX bytes:") + len("TX bytes:")
        rx_len = ifconfig_info[rx_off:].find(" ")
        tx_len = ifconfig_info[tx_off:].find(" ")

        rx = int(ifconfig_info[rx_off:rx_off + rx_len])
        tx = int(ifconfig_info[tx_off:tx_off + tx_len])
    
        return (rx, tx)
    except:
        return (-1, -1)

"""
Responsible for handling reboot and poweroff requests
"""
def power_control_listener():
    port = "5554"
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect ("tcp://localhost:%s" % port)

    topicfilter = "system"
    socket.setsockopt(zmq.SUBSCRIBE, topicfilter)
    print "STARTING POWER CONTROL LISTENING"

    while True:
        string = socket.recv_unicode()
        print "GOT A MESSAGE!!!!!!!!"
        topic, _, messagedata = string.partition(' ')
        if messagedata == "shutdown":
            subprocess.call(['poweroff'])
        if messagedata == "restart":
            subprocess.call(['reboot'])

def run_camera_control():
    print system_cameras
    sysproc = Process(target=camera_control_listener, args=(system_cameras,))
    sysproc.daemon = True
    sysproc.start()


"""
Responsible for handling camera control requests
"""
def camera_control_listener(camera_info):
    print camera_info
    cameras = yaml.load(file('/home/odroid/ocupus/config/ocupus.yml', 'r'))['cameras']

    port = "5554"
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect ("tcp://localhost:%s" % port)

    topicfilter = "cameraControl"
    socket.setsockopt(zmq.SUBSCRIBE, topicfilter)
    print "STARTING POWER CONTROL LISTENING"

    while True:
        string = socket.recv_unicode()

        topic, _, messagedata = string.partition(' ')

        # Need to fix the json->python serialization happening in peercon
        messagedata = messagedata.replace("u'","'")
        messagedata = messagedata.replace("'",'"')

        control = json.loads(messagedata)

        name = control['camera']

        v4l2args = [a['v4l2settings-off'] for a in cameras if a['name'] == name][0]

        args = shlex.split("v4l2-ctl -d " + camera_info[name].device + " " + v4l2args)
        proc = subprocess.call(args)
