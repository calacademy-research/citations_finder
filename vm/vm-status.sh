#!/bin/bash

# Source variables
source azure-deploy-config
runningDockerCount=0
disabledDockerCount=0
# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to check each VM
    for ((i=100; i<=counter; i++)); do
        uniqueVmName="${vmName}-${i}"
        runningDockerCount=0
        disabledDockerCount=0
        disabledDockers=""

        # Check VM status
        vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

        # If VM is running, process Docker containers
        if [[ $vmStatus ]]; then
            # Get the IP of the VM
            ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
            command="sudo docker ps -a --format '{{.Names}}:{{.Status}}'"
            # SSH into the VM and get Docker container statuses
            sshOutput=$(ssh -o StrictHostKeyChecking=no $ip $command)

            # Get free RAM information
            freeRam=$(ssh -o StrictHostKeyChecking=no $ip "free -m | awk '/^Mem:/{print \$4}'" < /dev/null)

            # Process each Docker container
            while read -r line; do
                if [[ $line == *"Up"* ]]; then
                    ((runningDockerCount++))
                elif [[ $line == *"Exited"* ]]; then
                    ((disabledDockerCount++))
                    # Get the exit code
                    containerName=$(echo $line | cut -d ':' -f 1)
                    exitCode=$(ssh -o StrictHostKeyChecking=no $ip "sudo docker inspect $containerName --format='{{.State.ExitCode}}'" < /dev/null)
                    disabledDockers+="    - Disabled Docker: $containerName, Exit Code: $exitCode\n"
                fi
            done <<< "$sshOutput"

            echo "VM: $uniqueVmName IP: $ip, Running Dockers: $runningDockerCount, Disabled Dockers: $disabledDockerCount, Free RAM: ${freeRam}MB"
            echo -e "$disabledDockers"
        fi
    done
else
    echo "No running VMs found."
fi
