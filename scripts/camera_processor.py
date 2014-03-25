#!/usr/bin/env python2
import imp
import sys
sys.path.append("/home/odroid/ocupus/python/libs")
import time
import zmq
import json
import traceback

context = zmq.Context()

socket = context.socket(zmq.REQ)
socket.connect ("tcp://localhost:%s" % "5550")


try_count = 0

while try_count < 10000:
    try:
        imp.load_source('ocupus', sys.argv[1])
    except:
        try_count += 1

        socket.send (json.dumps({"type":"log", "log":traceback.format_exc()}))
        socket.recv()
        print(traceback.format_exc())

    time.sleep(2)

sys.exit(1)