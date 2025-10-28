#! /bin/bash

###############################################################################
# add Additional startup programs
# start_Fan
# bash /home/jetson/Rosmaster/start_fan.sh
# auto start fan when poweron
###############################################################################


sleep 30

sudo sh -c "echo 150 > /sys/devices/pwm-fan/target_pwm"

wait
exit 0
