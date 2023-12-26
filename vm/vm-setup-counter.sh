#!/bin/bash
export ANSIBLE_NOCOWS=1
source azure-deploy-config

# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to run playbook on each VM
    for ((i=100; i<=counter; i++)); do
        uniqueVmName="${vmName}-${i}"

        # Check VM status
        vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

        # If VM is running, retrieve IP and run playbook
        if [[ $vmStatus ]]; then
            IP_ADDRESS=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
            echo "Running playbook on VM: $uniqueVmName IP: $IP_ADDRESS"
            ansible-playbook -i "$IP_ADDRESS," vm-setup-playbook.yml
        fi
    done
else
    echo "No running VMs found."
fi
