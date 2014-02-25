import subprocess
import zmq

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