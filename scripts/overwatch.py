#!/usr/bin/env python2
"""
Controls the webrtc peerconnection_client 
"""

import subprocess
import time
import threading
import shlex
from Queue import Queue

class SubprocessLogFollower (threading.Thread):
    def __init__(self, process, queue):
        threading.Thread.__init__(self)
        self.process = process
        self.queue = queue

    def run(self):
        print "Going"
        #for line in iter(self.process.stdout.readline, ''):
        #    print line
        #    self.queue.put(line)
        #print "Done"
        line = self.process.stdout.readline()
        while line != '':
            self.queue.put(line)
            line = self.process.stdout.readline()


p = subprocess.Popen(shlex.split("/home/odroid/ocupus/bin/armv7-neon/peerconnection_client"), 
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

lines = Queue()

slf = SubprocessLogFollower(p, lines)

slf.start()

startedCapture = False

while True:
    if not lines.empty():
        l = lines.get()
        #print l
        if l.find("Using Cand[") is 0 and not startedCapture:
            print l
            startedCapture = True
            parts = l.split(":")
            port = parts[6]
            subprocess.Popen(shlex.split("tcpdump -s 0 -w /tmp/testdump udp port " + port))
    else:
        time.sleep(0.01)
