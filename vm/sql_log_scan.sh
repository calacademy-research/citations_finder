#!/bin/bash

# Source variables
source azure-deploy-config
echo "All active VMs in the resource group '$resourceGroupName':"

# Check if running-vms.txt exists and is not empty
if [ -s running-vms.txt ]; then
    # Read the current counter
    counter=$(<running-vms.txt)

    # Loop to check each VM
    for ((i=100; i<counter; i++)); do
        uniqueVmName="${vmName}-${i}"
        vmStatus=null
        ip=null

        # Check VM status
        vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

        # If VM is running
        if [[ $vmStatus ]]; then
            # Get the IP of the VM
            ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
            echo "Processing VM: $uniqueVmName, IP: $ip"

            if [[ $ip ]]; then
                sshCommand="ssh -o StrictHostKeyChecking=no $ip"

                # Get the list of running Docker containers
                containerNames=$(timeout 40s $sshCommand "sudo docker ps --format '{{.Names}}'")
                if [ $? -ne 0 ]; then
                    echo "   SSH command timed out or failed for VM: $uniqueVmName"
                    continue
                fi

                # Process each Docker container
                while read -r containerName; do
                    # Copy sql.log from each container
                    $sshCommand "sudo docker cp $containerName:/app/sql.log /tmp/sql_$containerName.log" < /dev/null

                    # Download the log file to the local machine
                    scp -o StrictHostKeyChecking=no $ip:/tmp/sql_$containerName.log .

                    # Analyze the log file for the specified SQL query pattern
                    echo "Analyzing log file for container $containerName..."
                    grep -A 20 "UPDATE dois SET" "sql_$containerName.log" | 
                    grep -B 20 "File \"/app/main.py\", line 258, in <module>" | 
#                    awk '/WHERE doi/{doi=$4} /downloaded =/{downloaded=$3; print "DOI: " doi ", Downloaded: " downloaded}'
                    awk -F "'" '/WHERE doi/{doi=$(NF-1)} /downloaded =/{downloaded=$(NF-1); if (downloaded != "True") print "DOI: " doi ", Downloaded: " downloaded}'
  # Clear the log file in the container
                    $sshCommand "sudo docker exec $containerName bash -c '> /app/sql.log'" < /dev/null


                done <<< "$containerNames"
            fi
        fi
    done
else
    echo "No running VMs found."
fi
