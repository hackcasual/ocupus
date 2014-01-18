# ocupus - The Vision Coprocessor
ocupus was developed out of a need to provide useful tools to FIRST Robotics teams using on-robot vision processors. It is currently in pre-release state.

#### Disclaimers

 * ocupus is not supported by anyone, especially FIRST. Contact me and I will do my best to help, but please understand this is still very rough

## History
ocupus was developed initially by FRC team 3574 to address the following issues that came up during the 2013 season:
 
 * Computer vision approaches are challenging, and in some circumstances it maybe more valuable for the driver to see camera feed
 * Even if the CV system is working well, it's still really nice for a driver to be able to see the camera feed
 * Supporting multiple USB cameras is challenging if there isn't a deterministic way to identify the device
 * Vision coprocessor configuration was challenging in the pits and on the field

## Planned Features

 * Realtime feed streaming with WebRTC
 * Camera splitting allowing simultaneous recording, streaming, and processing of the same camera
 * Support multiple camera identification and configuration via USB ids and physical port connections
 * Online PythonCV interface
 * Network Tables integration
 * VLC and web-based configuration via Android Tablet (adb bridging for wired connectivity)

### Current State

 * `libjingle` based headless `peerconnection_client` and `peerconnection_server` are available for ARMv7-neon systems
 * Single stream WebRTC HTML page for Chrome
 * Tested streams over OpenVPN connection

## Architecture

ocupus is a set of scripts and binaries that run on Ubuntu.

### Dependencies

Package | Purpose 
--- | ---
openvpn | network tunneling to abide by R58
v4l2loopback | creates virtual v4l2 compatible devices
gstreamer | routes video from the USB device to multiple loopback devices for streaming, processing, and recording
flask | HTTP server for watching video streams, online code editing, and configuration


#### WebRTC

Robot to DS streaming to date has been using MJPEG. However MJPEG suffers from large stream sizes due to not using interframe prediction. The limit of 7mbit/s from R58b is easily hit even with small images and low framerates. From the [FMS white paper](http://www.usfirst.org/sites/default/files/uploadedFiles/Robotics_Programs/FRC/Game_and_Season__Info/2013/FMSWhitePaper_RevA.pdf) a 320x240 image at 30% quality and 30fps consumes 3.7mbit/s. In testing, a similar quality WebRTC stream at the same frame rate and resolution takes less than 10% of that, at ~280kbit/s.

[ocupus at 320x240@30 256kbps](https://raw2.github.com/hackcasual/ocupus/master/static/ocupus.png "Example")

#### OpenVPN

Due to networking restrictions, driver station to robot communication is limited to only a few ports, as per R58. By default, ocupus will use port 1180:TCP to serve OpenVPN clients, on the network 172.17.0.0/24. In the future, dropping OpenVPN would be much better. As WebRTC can use UDP, the extra overhead of tunneling it over TCP is not ideal. Over an open wireless network a dropped packet would only show up as graphical artifiacts on the receiving end. However by forcing it through TCP, a dropped packet will add latency to the stream.

#### v4l2loopback

This is likely the most challenging part of delivering a simple system. v4l2loopback is delivered as a DKMS package, and as such requires the current running kernel's source to build. Most ARM Ubuntu distributions don't package their kernel the same way x86 systems do, so often times this module can't be installed via `apt-get` without first manually setting up the source. Once full system images that include ocupus are available, this module can be precompiled, but until then there may be a need to provide pre-compiled versions for the most common systems.

## Supported Hardware
### Notably Not Supported
 * Raspberry PI A or B

The Raspberry PI suffers from 3 major issues
 1. CPU is slow and single core
 2. RAM bus slow
 3. No hardware float or SIMD (neon) support

In particular the neon support is considered mandatory for ocupus, as it represents the most commonly available acceleration for video.

### Development Hardware
Currently, primary development is done on Hardkernel's ODroid-XU
