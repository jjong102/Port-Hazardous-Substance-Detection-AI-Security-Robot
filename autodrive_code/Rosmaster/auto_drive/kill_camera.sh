#! /bin/bash

len1=` ps -ef|grep data_collection.py |grep -v grep| wc -l`
echo "Number of processes="$len1

if [ $len1 -eq 0 ] 
then
    echo "data_collection.py is not running "
else
    # ps -ef| grep data_collection.py| grep -v grep| awk '{print $2}'| xargs kill -9  
    camera_pid=` ps -ef| grep data_collection.py| grep -v grep| awk '{print $2}'`
    kill -9 $camera_pid
    echo "data_collection.py killed, PID:"
    echo $camera_pid
fi
sleep .1
