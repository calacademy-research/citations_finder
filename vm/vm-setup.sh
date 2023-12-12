#!/bin/bash
export ANSIBLE_NOCOWS=1

# Check if IP address is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <IP_ADDRESS>"
    exit 1
fi

IP_ADDRESS=$1

# Run ansible playbook
ansible-playbook -i "$IP_ADDRESS," vm-setup-playbook.yml
