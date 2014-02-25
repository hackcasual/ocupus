#!/usr/bin/python

import requests
import threading
import urllib
import urllib2
import zmq
import time
import sys
from multiprocessing import Process, Value, Queue
import json

import system_utilities

class Message:
    def __init__(self, type, data):
        self.type = type
        self.data = data

    def __repr__(self):
        return str(self.type) + ":" + self.data


def to_remote_server(port, my_id, peer_id):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)

    while True:
        # Wait for next request from client
        message = socket.recv()
        if peer_id.value > 0:
            send_message(my_id, peer_id.value, message)
        socket.send("ACK")

def from_remote_server(port, message_queue):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)

    time.sleep(1)
    while True:
        message = json.loads(message_queue.get().data)
        socket.send_unicode("%s %s" % (message['topic'], message['message']))

def hanging_get(my_id, messages, initial_peer_id):
    remote_sender = None
    remote_peer_id = Value("i", initial_peer_id)
    remote_sender = Process(target=to_remote_server, args=(5550,my_id,remote_peer_id)).start()

    while True:
        r = requests.get('http://localhost:8888/wait?peer_id=' + str(my_id))
        if r.status_code == 200:        

            if int(r.headers['pragma']) == my_id:
                connected = r.text.split("\n")
                for l in connected:
                    info = l.strip().split(",")

                    if len(info) == 3 and info[0] == "receiver" and info[2] == '1':
                        remote_peer_id.value = int(info[1])
            else:
                messages.put(Message(int(r.headers['pragma']), r.text))

def send_message(my_id, peer_id, message):
    data = message
    req = urllib2.Request("http://localhost:8888/message?peer_id=" + str(my_id) + "&to=" + str(peer_id), data)
    response = urllib2.urlopen(req)
    the_page = response.read()
    response.close()

def setup():
    r = requests.get('http://localhost:8888/sign_in?ocupus_orchestrator')

    peers = dict()

    connected = r.text.split("\n")

    my_info = connected[0].split(",")
    my_id = int(my_info[1])

    messages = Queue()

    initial_peer_id = -1

    for l in connected[1:]:
        info = l.split(",")
        if len(info) > 1:
            if info[0] == "receiver":
                initial_peer_id = int(info[1])

    t = threading.Thread(target=hanging_get, args = (my_id, messages, initial_peer_id))
    t.daemon = True
    t.start()
    print "Started hanging get thread"    
    p = Process(target=from_remote_server, args=(5554,messages))
    p.daemon = True
    p.start()

    sysproc = Process(target=system_utilities.power_control_listener)
    sysproc.daemon = True
    sysproc.start()

    print "Started xmq process"

def monitor_system_requests():
    context = zmq.Context()

    socket = context.socket(zmq.REQ)
    socket.connect ("tcp://localhost:%s" % "5550")

    while True:
        time.sleep(1)
        traffic_stats = system_utilities.get_traffic_info()
        socket.send ('{"type":"nettraff","rx":%d,"tx":%d}' % (traffic_stats[0], traffic_stats[1]))
        socket.recv()




if __name__ == "__main__":
    setup()
    monitor_system_requests()
