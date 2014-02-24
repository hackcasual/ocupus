#!/usr/bin/env python2

import zmq

context = zmq.Context()

socket = context.socket(zmq.REQ)
socket.connect ("tcp://localhost:%s" % "5550")
socket.send ('{"type":"log","log":"Howdy there!"}')
