#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import datetime
import threading
from enum import Enum, auto
import cv2
import uuid
import time
import numpy as np

import nanocamera as nano
# jetracerが独占しているので使えない
# import Jetson.GPIO as GPIO

from jetracer_model import prepare_torch
from jetracer_model import result_torch

from jetracer.nvidia_racecar import NvidiaRacecar

from utils import preprocess

intrMsg = "go"
STEERING_GAIN = 0.75
STEERING_BIAS = 0.00
STEERING_LIM = 0.65

THROTTLE_GAIN = 0.75
THROTTLE_BIAS = 0.0
THROTTLE_FWLIM = 0.5
THROTTLE_BKLIM = -0.3

# 状態状態遷移用変数
class runsq(Enum):
    INIT = auto()
    PRE = auto()
    GOPAUSE = auto()
    GO = auto()

runst = runsq.INIT

car = NvidiaRacecar()
throttleflg = True

def init():
    print("#---- init system ----#")
    cameraL, cameraR = init_nanocam(224,224,120,2)
    return cameraL, cameraR 



def init_nanocam(imgwd, imghg, fpsc, angle):
    # Left Camera
    cameraL = nano.Camera(device_id=0, flip=angle, width=imgwd, height=imghg, fps=fpsc)
    # Right Camera
    cameraR = nano.Camera(device_id=1, flip=angle, width=imgwd, height=imghg, fps=fpsc)
    return cameraL, cameraR

def runWaitandCountDown():
    OKng = input("RUN OK/ng >>")
    if OKng != "OK":
        return
    print("!!!! COUNT DOWN !!!!")
    print("3...")
    time.sleep(1)
    print("2..")
    time.sleep(1)
    print("1.")
    time.sleep(1)
    print("!!!! START !!!!")


def prepare(cameraL, cameraR):
    global car
    print("#---- prepare system ----#")
    print("## camera test")
    imgL = cameraL.read()
    imgR = cameraR.read()
    s_uuid = str(uuid.uuid1())
    # filename = filepath + '%d_%d_%s.jpg' % (0, 0, s_uuid))
    filenameMx = './nanocam_test/%d_%d_%s.jpg' % (0, 0, s_uuid)
    filenameL = './nanocam_test/%d_%d_%s.jpg' % (0, 0, s_uuid)
    filenameR = './nanocam_test/%d_%d_%s.jpg' % (0, 0, s_uuid)
    cv2.imwrite(filenameL, imgL)
    cv2.imwrite(filenameR, imgR)
    imgMx = cv2.addWeighted(src1 = imgL, alpha=0.5, src2 = imgR, beta = 0.5, gamma = 0)
    cv2.imwrite(filenameMx, imgMx)
    print("## car test")
    print("!!!! CAR WILL MOVE !!!!")
    print("car zeroing")
    car.steering = 0.0 
    car.throttle = 0.0
    okng = input("OK/ng>>")
    if okng == "OK":
        print("car zeroing")
        car.steering = 0.0 
        car.throttle = 0.0
        print("Left")
        car.steering = 0.65
        time.sleep(1)

        print("Right")
        car.steering = -0.65
        time.sleep(1)

        car.steering = 0.0 

        print("FORWARD")
        car.throttle = 0.3
        time.sleep(0.2)
        car.throttle = 0.0
        
        print("BREAK")
        car.throttle = -0.5
        time.sleep(0.2)
        car.throttle = 0.0

        print("BACKWARD")
        car.throttle = -0.3
        time.sleep(0.2)
        car.throttle = 0.0
    else:
        print("skip...")


    print("## model prepaer")
    model = prepare_torch()
    return model
####


####
def autorun(cameraL, cameraR, model, recpath, recintv):
    global STEERING_GAIN
    global STEERING_BIAS
    global STEERING_LIM
    global THROTTLE_GAIN
    global THROTTLE_BIAS
    global THROTTLE_FWLIM
    global THROTTLE_BKLIM
    global intrMsg

    
    s_uuid = str(uuid.uuid1())
    dt_now = datetime.datetime.now()
    datestr = str(dt_now.strftime('%Y_%m_%d_%H:%M:%S'))
    cnt = 0    
    while intrMsg != "QUIT":
        car.steering = 0.0
        car.throttle = 0.0
        while intrMsg != "PAUSE":
            # zaku
            img = cameraR.read()

            # gundam
            #imgL = cameraL.read()
            #imgR = cameraR.read()
            #img = cv2.addWeighted(src1 = imgL, alpha=0.5, src2 = imgR, beta = 0.5, gamma = 0)

            imgh = preprocess(img).half()
            output = model(imgh).detach().cpu().numpy().flatten()

            x = float(output[0])* STEERING_GAIN + STEERING_BIAS 
            if x < (STEERING_LIM * -1):
                x = STEERING_LIM * -1
            if STEERING_LIM < x:
                x = STEERING_LIM
            
            y = float(output[1]) * THROTTLE_GAIN + THROTTLE_BIAS
            if y < THROTTLE_BKLIM:
                y = THROTTLE_BKLIM
            if THROTTLE_FWLIM < y:
                y = THROTTLE_FWLIM
            car.steering = x
            car.throttle = y
            cnt = cnt + 1
            if (cnt % recintv) == 0:
                recfile = recpath + '%s_%d_%d_%d_%s.jpg' % (datestr,cnt, int(x * 100), int(y * 100), s_uuid)
                cv2.imwrite(recfile, img)
    car.steering = 0.0
    car.throttle = 0.0
    print("# auto run end...")

def commander():
    global STEERING_GAIN
    global STEERING_BIAS
    global STEERING_LIM
    global THROTTLE_GAIN
    global THROTTLE_BIAS
    global THROTTLE_FWLIM
    global THROTTLE_BKLIM
    global intrMsg
    while intrMsg != "QUIT":
        cmd = input("Pause?(yes/no)>>")
        if cmd == "yes":
            intrMsg = "PAUSE"
            cmd = input("input command(gain/start/quit)>>")
            if cmd == "gain":
                # STEERING GAIN setting 
                ver = input("STEERING_GAIN = " +str(STEERING_GAIN)+ "(float/\"keep\")>>")
                if ver != "keep":
                    STEERING_GAIN = float(ver)
                    print("STEERING_GAIN was updated to " +str(STEERING_GAIN))

                # STEERING BIAS setting 
                ver = input("STEERING_BIAS = " +str(STEERING_BIAS)+ "(float/\"keep\")>>")
                if ver != "keep":
                    STEERING_BIAS = float(ver)
                    print("STEERING_GAIN was updated to " +str(STEERING_BIAS))

                # THROTTLE_GAIN setting 
                ver = input("THROTTLE_GAIN = " +str(THROTTLE_GAIN)+ "(float/\"keep\")>>")
                if ver != "keep":
                    THROTTLE_GAIN = float(ver)
                    print("STEERING_GAIN was updated to " +str(THROTTLE_GAIN))
                # THROTTLE_BIAS setting 
                ver = input("THROTTLE_BIAS = " +str(THROTTLE_BIAS)+ "(float/\"keep\")>>")
                if ver != "keep":
                    THROTTLE_BIAS = float(ver)
                    print("THROTTLE_BIAS was updated to " +str(THROTTLE_BIAS))

                print("STEERING_GAIN =" +str(STEERING_GAIN))
                print("STEERING_BIAS =" +str(STEERING_BIAS))
                print("THROTTLE_GAIN =" +str(THROTTLE_GAIN))
                print("THROTTLE_BIAS =" +str(THROTTLE_BIAS))
            elif cmd == "start":
                intrMsg = "GO"
            elif cmd == "quit":
                intrMsg = "QUIT"
    print("commander end...")

def execute():
    global intrMsg
    # init
    cameraL, cameraR = init()

    # model prepare
    model = prepare(cameraL, cameraR)

    # wait user go
    runWaitandCountDown()

    # run and command wait
    intrMsg = "GO"
    thrdAutoRun = threading.Thread(target=autorun, args=(cameraL, cameraR, model, "./autorunrec/", 20))
    thrdCommander = threading.Thread(target=commander)
    thrdCommander.start()
    thrdAutoRun.start() 
    thrdCommander.join()
    thrdAutoRun.join()
    del cameraR
    del cameraL
    print("# ---- END ----")

if __name__ == '__main__':
    # global runst
    execute()