#!/bin/bash
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

if [ -z "$STY" ]; then exec screen -dm -S gruntScreen /bin/bash "$0"; fi
cd /home/pi/adafruit-pi-cam/

while true; do
    echo "Running Hochzeitsblitzer in 3s..."
    sleep 3
    python3 cam.py
done
