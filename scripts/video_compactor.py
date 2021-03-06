#!/usr/bin/env python2
"""
Processes the saved videos, converting to smaller format

Done with nice so should only use CPU time if its idle
"""


import glob
from datetime import datetime as dt
import re
import subprocess
import time

while True:

    subprocess.call(["mkdir","-p","/home/odroid/Videos/converted"])

    mjpeg_files = glob.glob('/home/odroid/Videos/*.mjpeg')

    if (len(mjpeg_files) > 2):
        time.sleep(10)
        continue

    least_file_time = dt.strptime("3014-03-16T214638.752173","%Y-%m-%dT%H%M%S.%f")
    least_file = None

    for f in mjpeg_files:
        mo = re.match(".*-(\d{4}-\d{2}-\d{2}T\d{6}\.\d+)\.mjpeg", f)

        if mo is not None:
            when = dt.strptime(mo.groups()[0],"%Y-%m-%dT%H%M%S.%f")
            users = subprocess.call(["fuser", "-s", f])
            if when < least_file_time and users != 0:
                least_file_time = when
                least_file = f

    if least_file:
        fn = least_file.replace("mjpeg","avi").replace("/Videos/","/Videos/converted/")

        p = subprocess.Popen('nice -n 15  avconv -y -v error -i %s -b:v 2M %s' % (least_file, fn), shell=True)
        r = p.wait()

        subprocess.check_call(["rm", least_file])

    time.sleep(10)