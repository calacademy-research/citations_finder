#!/bin/bash

echo "Starting VM..."
./vm-start.sh
echo "VM started successfully."

IP=$(./vm-start.sh)
echo "IP Address of VM: $IP"

echo "Setting up VM..."
./vm-setup.sh $IP
echo "VM setup completed."

echo "Setting up PDF environment on VM..."
./vm-pdf-setup.sh $IP
echo "PDF environment setup completed."
