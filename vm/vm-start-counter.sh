#!/bin/bash
az account get-access-token --output none || az login

source azure-deploy-config
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
    echo $ip
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
  --ssh-key-value "$(cat pub-keys.txt)" \
  --storage-sku Standard_LRS \
  --os-disk-size-gb $diskSizeGB > /dev/null

az vm start --name $uniqueVmName --resource-group $resourceGroupName > /dev/null

ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $uniqueVmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
echo $ip
