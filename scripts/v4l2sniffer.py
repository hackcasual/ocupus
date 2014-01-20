#!/usr/bin/python

import subprocess
import re

"""
Makes various probes of V4l2 devices, identifies them by physical USB connection
"""

class Node:
    def __init__(self, value, parent):
        self.value = value
        self.children = []
        self.parent = parent
    def __repr__(self):
        return self.value + ": " + str(self.children)

class VideoDevice:
    def __init__(self):
        self.have_usb_id = False
        self.have_port_connection = False
        self.are_video_capture = False
    def __repr__(self):
        return self.sys_fs_id + " : " + self.path
    

def output_to_tree(output):
    root = Node("[ROOT]", None)
    rt = root
    depth = 0

    for l in output.split("\n"):
        # Count the number of whitespace in front of the line
        nD = len(l) - len(l.lstrip())
        if nD > depth:
            depth = nD
            parent = root.children[-1]
            new_child = Node(l.lstrip(), parent)
            parent.children.append(new_child)
            root = parent
        elif nD == depth:
            new_child = Node(l.lstrip(), root)
            root.children.append(new_child)
        elif nD < depth:
            depth = nD
            root = root.parent
            new_child = Node(l.lstrip(), root)
            root.children.append(new_child)
    return rt

rt = output_to_tree(subprocess.check_output(["v4l2-sysfs-path","-d"]))

devices = {}
# Lookup for single pass through the usb toplogy
buses = {}

for node in rt.children:
    vid_device = ""
    if len(node.children) > 0:
        vid_device = node.children[0].value
    if node.value.startswith("Device") and vid_device.startswith("video"):
        dev = VideoDevice()
        dev.sys_fs_id = node.value[7:-1]
        dev.path = vid_device[:vid_device.find("(")]
        devices[dev.path] = dev

        try:
            dev.id_product = open("/sys/devices/" + dev.sys_fs_id + "/idProduct").readline().rstrip()
            dev.id_vendor = open("/sys/devices/" + dev.sys_fs_id + "/idVendor").readline().rstrip()
            dev.dev_num = int(open("/sys/devices/" + dev.sys_fs_id + "/devnum").readline().rstrip())
            dev.bus_num = int(open("/sys/devices/" + dev.sys_fs_id + "/busnum").readline().rstrip())            
            dev.have_usb_id = True

            if dev.bus_num not in buses:
                buses[dev.bus_num] = {}
            buses[dev.bus_num][dev.dev_num] = dev
        except:
            pass

rt = output_to_tree(subprocess.check_output(["lsusb","-t"]))

def find_ports(node, path, to_find):
    for child in node.children:
        m = re.search("Port (\d+): Dev (\d+),", child.value)
        if m != None:
            port_num = int(m.group(1))
            dev_num = int(m.group(2))

            if child.value.find("Class=Hub") > -1:
                path.append(port_num)
                find_ports(child, path, to_find)
                path.pop(-1)
            else:
                if dev_num in to_find:
                    to_find[dev_num].port_connection = "-".join([str(z) for z in path + [port_num]])
                    to_find[dev_num].have_port_connection = True

for bus in rt.children:
    bus_num = -1
    if bus.value.find("Bus") > -1:
        bus_num = int(bus.value[8:10])

    if bus_num in buses:
        find_ports(bus, [bus_num], buses[bus_num])

devices = {x:devices[x] for x in devices if devices[x].have_port_connection}

for x in devices:
    dev_info = ""
    try:
        dev_info = subprocess.check_output(['v4l2-ctl', '--all', '-d', '/dev/' + x])
    except subprocess.CalledProcessError as e:
        dev_info = e.output
    if dev_info.find("Format Video Capture:") > -1:
        devices[x].are_video_capture = True

devices = {x:devices[x] for x in devices if devices[x].are_video_capture}

for x in devices:
    print x + "," + devices[x].port_connection + "," + devices[x].id_vendor + ":" + devices[x].id_product