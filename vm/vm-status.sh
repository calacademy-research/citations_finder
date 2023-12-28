#!/bin/bash

# Source variables
source azure-deploy-config
echo "All active VMs in the resource group '$resourceGroupName':"
az vm list --resource-group citations-group --show-details --query "[].{Name:name, Status:powerState, PublicIP:network.publicIpAddresses[0].ipAddress}" -o table

runningDockerCount=0
disabledDockerCount=0
# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to check each VM
    for ((i=100; i<counter; i++)); do
        uniqueVmName="${vmName}-${i}"
        runningDockerCount=0
        disabledDockerCount=0
        disabledDockers=""
        vmStatus=null
        ip=null

        # Check VM status
        vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

        # If VM is running, process Docker containers
        if [[ $vmStatus ]]; then
            # Get the IP of the VM
            ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
        fi
        if [[ $ip ]]; then
            sshCommand="ssh -o StrictHostKeyChecking=no $ip"

            sshOutput=$(timeout 40s $sshCommand "sudo docker ps -a --format '{{.Names}}:{{.Status}}'")
            if [ $? -ne 0 ]; then
                echo "   SSH command timed out or failed for VM: $uniqueVmName"
#                vmInsights=$(az monitor metrics list --resource $uniqueVmName --resource-type "Microsoft.Compute/virtualMachines" --resource-group $resourceGroupName --metric "Percentage CPU" --output table)
#                echo "   VM Insights: $vmInsights"
                continue
            fi

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
