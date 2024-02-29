#!/bin/bash
az account get-access-token --output none || az login
source azure-deploy-config
export ANSIBLE_NOCOWS=1
export ANSIBLE_HOST_KEY_CHECKING=False

adminUsername=$(yq e '.azure_username' vm_passwords.yml)
adminPassword=$(yq e '.azure_password' vm_passwords.yml)

# Initialize counter in running-vms.txt
if [ ! -f running-vms.txt ]; then
    echo "100" > running-vms.txt
fi

# Read and increment counter
counter=$(<running-vms.txt)
echo $((counter+1)) > running-vms.txt

# Unique VM name based on counter
uniqueVmName="${vmName}-${counter}"

# Check VM status
vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

# If VM is running, retrieve and print IP, then exit
if [[ $vmStatus ]]; then
    ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
    echo Already running: $ip
    exit 0
fi

# Create resource group
az group create --name $resourceGroupName --location $location > /dev/null

# Create VM
az vm create \
  --resource-group $resourceGroupName \
  --name $uniqueVmName \
  --size $vmSize \
  --image $image \
  --admin-username $adminUsername \
  --admin-password $adminPassword \
  --ssh-key-value "$(cat ~/.ssh/id_rsa.pub)" \
  --storage-sku Standard_LRS \
  --os-disk-size-gb $diskSizeGB > /dev/null

az vm start --name $uniqueVmName --resource-group $resourceGroupName > /dev/null

echo "VM STARTED SUCCESSFULLY"

vmStatus=$(az vm get-instance-view --name $uniqueVmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)
if [[ $vmStatus ]]; then

    IP_ADDRESS=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)



    # configure ansible
    echo "VM is running. IP: $IP_ADDRESS"
    echo "Running playbook on VM: $uniqueVmName IP: $IP_ADDRESS"
    ansible-playbook -i "$IP_ADDRESS," vm-setup-playbook.yml

    # optional - set up reverse tunnel for database connection
    echo "Setting up SSH tunnel for VM: $uniqueVmName IP: $IP_ADDRESS"
    command="ssh -o StrictHostKeyChecking=no -fN -R 3326:localhost:3326 $adminUsername@$IP_ADDRESS"
    # Execute nested SSH command to set up the tunnel from collectionsdb to the VM
    ssh -o StrictHostKeyChecking=no -t admin@collectionsdb.calacademy.org $command

    echo "Tunnel established for $uniqueVmName to collectionsdb... now running container"

    # Run Docker container
    instances=2
    for ((i=1; i<=$instances; i++)); do
        ssh -o StrictHostKeyChecking=no $adminUsername@$IP_ADDRESS "sudo docker run -d --network host \
          -v /opt/citations_finder/config.ini:/app/config.ini \
          -v /opt/citations_finder/vm:/app/vm \
          -v /opt/citations_finder/pdf:/app/pdf \
          -v /opt/citations_finder/journals.tsv:/app/journals.tsv\
          --ulimit nproc=65535 \
          --ulimit nofile=65535 \
          --name app$i citations_finder"
        sleep 90
    done
else
    echo "VM $uniqueVmName is not running or IP address could not be retrieved."
    exit 1
fi


