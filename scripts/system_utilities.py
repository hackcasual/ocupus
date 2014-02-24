import subprocess

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