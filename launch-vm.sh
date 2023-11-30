#!/bin/bash
az account get-access-token --output none || az login

source azure-deploy-config


# Check VM status
vmStatus=$(az vm get-instance-view --name $vmName --resource-group $resourceGroupName --query "instanceView.statuses[?code=='PowerState/running']" -o tsv 2>/dev/null)

echo vm status: $vmStatus


# If VM is running, retrieve and print IP, then exit
if [[ $vmStatus ]]; then
    ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $vmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
    echo $ip
    exit 0
fi



# Create resource group
echo "Creating group..."
az group create --name $resourceGroupName --location $location >/dev/null

echo "Creating VM..."

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
  --os-disk-size-gb $diskSizeGB

echo "starting vm if necessary..."

az vm start --name $vmName --resource-group $resourceGroupName


echo "Cloning citations finder..."

#az vm extension set \
#  --publisher Microsoft.Azure.Extensions \
#  --version 2.0 \
#  --name CustomScript \
#  --vm-name $vmName \
#  --resource-group $resourceGroupName \
#  --settings '{"commandToExecute":"git clone https://github.com/calacademy-research/citations_finder.git"}'
#TODO: use ssh for his and get the 'confirm' note removed



ip=$(az vm list-ip-addresses --resource-group $resourceGroupName --name $vmName --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
echo 'final IP:' $ip
