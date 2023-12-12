#!/bin/bash
az account get-access-token --output none || az login

source azure-deploy-config
adminUsername=$(yq e '.azure_username' vm_passwords.yml)
adminPassword=$(yq e '.azure_password' vm_passwords.yml)


# Check VM status
vmStatus=$(az vm get-instance-view --name $vmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

#echo vm status: $vmStatus


# If VM is running, retrieve and print IP, then exit
if [[ $vmStatus ]]; then
    ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $vmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
    echo $ip
    exit 0
fi



# Create resource group
az group create --name $resourceGroupName --location $location > /dev/null


# Create VM
az vm create \
  --resource-group $resourceGroupName \
  --name $vmName \
  --size $vmSize \
  --image $image \
  --admin-username $adminUsername \
  --admin-password $adminPassword \
  --ssh-key-value "$(cat ~/.ssh/id_rsa.pub)" \
  --storage-sku Standard_LRS \
  --os-disk-size-gb $diskSizeGB > /dev/null


az vm start --name $vmName --resource-group $resourceGroupName > /dev/null

ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $vmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
echo $ip
