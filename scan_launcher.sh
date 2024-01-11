#!/bin/bash
source env/bin/activate
current_date_time=$(date +"%b-%d-%H")

for i in $(seq 1 $1)
do
   nohup python3 main.py >& "$(hostname).$i.$current_date_time" &
   sleep 900
done
