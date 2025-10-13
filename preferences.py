from ultralytics import settings
settings.update({"sync": False}) # Disable analytics and crash reporting


from pathlib import Path
import sys, psutil, logging, time
import os, re, uuid, hashlib, platform, subprocess
from typing import List

def get_kwargs_from_cli(allowed_args=None):
    """
    Parses command line arguments and returns them as a dictionary.
    Where arguments are in the form --key=value.
    if allowed_args is provided, only those arguments will be accepted.
    If an argument is not allowed, a ValueError will be raised.
    :param allowed_args: List of allowed argument names (without the leading '--').
    :return: Dictionary of arguments. (key: str, value: str)
    """
    kwargs = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            if allowed_args is None or key.upper() in allowed_args:
                kwargs[key.upper()] = value
            else:
                raise ValueError(f"Argument '{key}' is not allowed. Allowed arguments are: {allowed_args}")

            kwargs[key.upper()] = value  # always string
    return kwargs

def get_all_ipv4s():
        """Returns dict of interface name → IPv4 address (WiFi and LAN only)."""
        ipv4s = {}
        for iface_name, iface_addrs in psutil.net_if_addrs().items():
            for addr in iface_addrs:
                if addr.family.name == "AF_INET":
                    if "loopback" not in iface_name.lower():
                        ipv4s[iface_name] = addr.address
        return ipv4s

#========================================================================
# CLI Arguments
ALLOWED_CLI_ARGS = [   
    'PREFERRED_NETWORK_INTERFACE', 
    'PREFERRED_NETWORK_IPV4',
    'BACKEND_SERVER_PORT',
    'WEBCAM_INDEX',

    'RTSP_IP_ADDRESS',
    'RTSP_ENDPOINT',
    'RTSP_USERNAME',
    'RTSP_PASSWORD',

    'RELAY_ON_DURATION_MS',

    ]

MUST_HAVE_CLI_ARGS = []
_cli_kwargs = get_kwargs_from_cli(allowed_args=ALLOWED_CLI_ARGS)
if not all(arg in _cli_kwargs for arg in MUST_HAVE_CLI_ARGS): raise ValueError(f"Missing required CLI arguments: {MUST_HAVE_CLI_ARGS}. Provided arguments: {_cli_kwargs}")

#========================================================================
#NOTE: Only one of these two should be provided as a CLI argument, raises error if both or none are provided
PREFERRED_NETWORK_INTERFACE      :str = _cli_kwargs.get('PREFERRED_NETWORK_INTERFACE', None) # Ethernet, Wi-Fi, eth0, wlan0, etc.
PREFERRED_NETWORK_IPV4           :str = _cli_kwargs.get('PREFERRED_NETWORK_IPV4', None)  # If provided, use this IP directly

if (PREFERRED_NETWORK_INTERFACE is None) and (PREFERRED_NETWORK_IPV4 is None) :
    raise ValueError("Either PREFERRED_NETWORK_INTERFACE or PREFERRED_NETWORK_IPV4 must be provided as a CLI argument.")
if (PREFERRED_NETWORK_INTERFACE is not None) and (PREFERRED_NETWORK_IPV4 is not None):
    raise ValueError("Only one of PREFERRED_NETWORK_INTERFACE or PREFERRED_NETWORK_IPV4 should be provided, not both.")
if PREFERRED_NETWORK_INTERFACE is not None:
    if PREFERRED_NETWORK_INTERFACE not in get_all_ipv4s().keys():
        raise ValueError(f"Provided PREFERRED_NETWORK_INTERFACE '{PREFERRED_NETWORK_INTERFACE}' not found in available interfaces: {list(get_all_ipv4s().keys())}")
    IPV4_ADDRESS = get_all_ipv4s()[PREFERRED_NETWORK_INTERFACE]
if PREFERRED_NETWORK_IPV4 is not None:
    if PREFERRED_NETWORK_IPV4 not in get_all_ipv4s().values():
        raise ValueError(f"Provided PREFERRED_NETWORK_IPV4 '{PREFERRED_NETWORK_IPV4}' not found in available IPv4s: {list(get_all_ipv4s().values())}")
    IPV4_ADDRESS = PREFERRED_NETWORK_IPV4

#========================================================================
BACKEND_SERVER_PORT :int = int(_cli_kwargs.get('BACKEND_SERVER_PORT', 8000))  # Port for FastAPI server

STREAM_SOURCE = "webcam"  # Options: "webcam", "rtsp_streamer"
STREAM_SOURCE_KWARGS = {
 "webcam": {     
    "webcam_index": _cli_kwargs.get("WEBCAM_INDEX", 0),  # Default to 0 if not provided
 },
 "rtsp_streamer": {
    "ipv4_address": _cli_kwargs.get("RTSP_IP_ADDRESS", "0.0.0.0"),  # Default to
    "endpoint": _cli_kwargs.get("RTSP_ENDPOINT", "/stream"),
    "username": _cli_kwargs.get("RTSP_USERNAME", "username"),
    "password": _cli_kwargs.get("RTSP_PASSWORD", "password"),
 }
}

HUMAN_PRESENCE_DETECTOR_KWARGS = {
    "model_name": "yolov8s.pt",  # Model file name
    "conf_threshold": 0.60,       # Confidence threshold for detections
    "polygon_points": [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.45, 0.45)], # Defaulted to whole frame if empty.
    "t1_threshold": 1.0,         # Time in seconds to confirm human presence (absence to presence)
    "t2_threshold": 1.0          # Time in seconds to confirm human absence  (presence to absence)
}

ARDUINO_KWARGS = {
    "baud_rate": 9600,           # Serial baud rate
}
RELAY_KWARGS = {
    "human_presence_pin": 2,    # Pin number connected to relay for human presence
    "human_presence_delay_ms": 0,  # Delay before activating relay (ms)
    "human_presence_duration_ms": _cli_kwargs.get("RELAY_ON_DURATION_MS", 2000),  # Duration to keep relay active (ms)
    "human_absence_pin": 4,   # Pin number connected to relay for human absence
    "human_absence_delay_ms": 0,   # Delay before activating relay (ms)
    "human_absence_duration_ms": _cli_kwargs.get("RELAY_ON_DURATION_MS", 2000),  # Duration to keep relay active (ms)
}
    
COOLDOWN_RANGE_PER_ITERATION = (0.00, 2)  # Range of cooldown time (in seconds) between each main loop iteration to reduce CPU usage
COOLDOWN_INCEMENT_PER_ITERATION = 0.025  # Increment cooldown by this much each iteration until max of COOLDOWN_RANGE_PER_ITERATION[1]

USE_ARDUINO = True            # Whether to use Arduino module.
SHOW_DEBUG_FRAME = False  # Whether to show debug frame with drawings.

# VALIDATION ======================
# Basic validation of preferences
if STREAM_SOURCE not in STREAM_SOURCE_KWARGS.keys():
    raise ValueError(f"Invalid STREAM_SOURCE '{STREAM_SOURCE}'. Must be one of {list(STREAM_SOURCE_KWARGS.keys())}.")

# Validate polygon points
for x, y in HUMAN_PRESENCE_DETECTOR_KWARGS["polygon_points"]:
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError(f"Polygon point ({x}, {y}) must be normalized between 0 and 1.")
    
