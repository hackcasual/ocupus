#!/usr/bin/env python2

import cv2
import numpy as np
import logging
import nt_client
import os

""" 
If we're running in the ocupus environment, stub out the GUI functions, override camera selection
"""
if 'OCUPUS_CAMERA_DEV' in os.environ:
    which_dev = os.environ['OCUPUS_CAMERA_DEV']
    dev_id = int(which_dev[len("video"):])

    cap = cv2.VideoCapture(dev_id)

    def __getOcupusCap(*args, **kwargs):
        return cap

    def __ignoreFunction(*args, **kwargs):
        pass

    cv2.VideoCapture = __getOcupusCap

    cv2.imshow = __ignoreFunction
    cv2.waitKey = __ignoreFunction

