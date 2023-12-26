#!/bin/bash

# Source variables
source azure-deploy-config

# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to check each VM
    for ((i=100; i<=counter; i++)); do
        uniqueVmName="${vmName}-${i}"

        # Check VM status
        vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

        # If VM is running, retrieve and print IP
        if [[ $vmStatus ]]; then
            ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
            echo "VM: $uniqueVmName IP: $ip"
        fi
    done
else
    echo "No running VMs found."
fi
