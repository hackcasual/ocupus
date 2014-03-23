Work in progress....

apt-get install hasciicam guvcview v4l2loopback-utils python-pip libav-tools

# /lib/modules/3.4.75/modules.dep:extra/v4l2loopback.ko

/lib/modules/3.4.75/extra/v4l2loopback.ko
install s5p firmware

r58 openvpn config

# depmod -ae

pip install flask-bootstrap

Set up virutal ethernet interface
Disable avahi
Automatic logging upload to memory stick
Fix routes


modprobe v4l2loopback devices=4 card_label="Forward Stream","Forward Process","Rear Stream", "Rear Process"


sudo ./peerconnection_client --server localhost --port 8888 --videodevice /dev/video0 --clientname='Camera1'

gst-launch -v v4l2src device=/dev/video0 ! "video/x-raw-yuv,width=320,height=240,framerate=30/1,format=(fourcc)YUYV" ! v4l2sink device=/dev/video1

rc.local

echo ondemand > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 
echo 10 > /dev/b.L_operator
