#!/bin/bash

# Source variables
source azure-deploy-config

# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to stop each VM
    for ((i=100; i<counter; i++)); do
        uniqueVmName="${vmName}-${i}"
        echo "Stopping VM: $uniqueVmName"

        # Shutdown VM
        az vm deallocate --resource-group $resourceGroupName --name $uniqueVmName
    done
    rm running-vms.txt
else
    echo "No running VMs found."
fi
