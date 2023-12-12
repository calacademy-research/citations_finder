#!/bin/bash

# Variables
source azure-deploy-config

# Shutdown VM
az vm deallocate \
  --resource-group $resourceGroupName \
  --name $vmName
