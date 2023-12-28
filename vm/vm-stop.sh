#!/bin/bash

# Source variables and configurations
source azure-deploy-config

# Function to shut down a single VM
shutdown_vm() {
    local vm_number=$1
    uniqueVmName="${vmName}-${vm_number}"
    echo "Deallocating and deleting VM: $uniqueVmName"

    # Replace this with the command or method to get the VM's IP or hostname
    IP_ADDRESS=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)

    echo "Found host: $IP_ADDRESS ... purge keys"
    # Remove the VM's SSH key from known_hosts
    if [ ! -z "$IP_ADDRESS" ]; then
        echo "Removing SSH key for $IP_ADDRESS from known_hosts..."
        ssh-keygen -f "/Users/joe/.ssh/known_hosts" -R "$IP_ADDRESS"
    fi

    # clean it up on admin@collectionsdb, too
    cleanup_command="ssh-keygen -f ~/.ssh/known_hosts -R $IP_ADDRESS"
    ssh -t admin@collectionsdb.calacademy.org "$cleanup_command"

    # Deallocate VM
    az vm deallocate --resource-group $resourceGroupName --name $uniqueVmName

    # Delete VM
    az vm delete --resource-group $resourceGroupName --name $uniqueVmName --yes

    # List and delete associated disks
    disks=$(az disk list --resource-group $resourceGroupName --query "[?contains(name, '$uniqueVmName')].name" -o tsv)
    for disk in $disks; do
        echo "Deleting disk: $disk"
        az disk delete --resource-group $resourceGroupName --name $disk --yes --no-wait
    done
}

# Initialize Azure CLI session
az account get-access-token --output none || az login

# Check if an argument is provided
if [ $# -eq 1 ]; then
    # Shut down the specific VM
    shutdown_vm $1
else
    # Check if running-vms.txt exists and is not empty
    if [ -s running-vms.txt ]; then
        # Read the current counter
        counter=$(<running-vms.txt)

        # Loop to deallocate each VM and delete their disks
        for ((i=100; i<counter; i++)); do
            shutdown_vm $i
        done

        # Reset the counter in running-vms.txt
        echo "100" > running-vms.txt
    else
        echo "No running VMs found."
    fi
fi
