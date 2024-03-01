#!/bin/bash
source env/bin/activate
current_date_time=$(date +"%b-%d-%H")

for i in $(seq 1 $1)
do
   echo launching $i
   nohup python3 main.py >& "$(hostname).$i.$current_date_time" &
   sleep 20
done
