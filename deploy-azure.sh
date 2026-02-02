#!/bin/bash

# Azure Container Apps Deployment Script for Tournament Allocator
# This script automates the deployment of the Tournament Allocator application to Azure Container Apps

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Tournament Allocator Deployment${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Configuration - Edit these values as needed
RESOURCE_GROUP="${RESOURCE_GROUP:-tournament-allocator-rg}"
LOCATION="${LOCATION:-eastus}"
ENVIRONMENT="${ENVIRONMENT:-tournament-allocator-env}"
APP_NAME="${APP_NAME:-tournament-allocator}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Environment: $ENVIRONMENT"
echo "  App Name: $APP_NAME"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed.${NC}"
    echo "Please install it from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged in to Azure. Please log in...${NC}"
    az login
fi

# Display current subscription
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
echo -e "${GREEN}✓${NC} Using subscription: $SUBSCRIPTION_NAME"
echo ""

# Confirm before proceeding
read -p "Do you want to proceed with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Step 1: Creating Resource Group...${NC}"
if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Resource group already exists"
else
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    echo -e "${GREEN}✓${NC} Resource group created"
fi

echo ""
echo -e "${YELLOW}Step 2: Creating Container Apps Environment...${NC}"
if az containerapp env show --name "$ENVIRONMENT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Environment already exists"
else
    az containerapp env create \
        --name "$ENVIRONMENT" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION"
    echo -e "${GREEN}✓${NC} Environment created"
fi

echo ""
echo -e "${YELLOW}Step 3: Deploying Application...${NC}"
echo "This may take several minutes as the container is built and deployed..."

FQDN=$(az containerapp up \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENVIRONMENT" \
    --source . \
    --target-port 8080 \
    --ingress external \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

echo ""
echo -e "${GREEN}✓${NC} Deployment completed successfully!"
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Deployment Summary${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "Application URL: ${GREEN}https://$FQDN${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App: $APP_NAME"
echo ""
echo "To view logs, run:"
echo "  az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "To update the app after code changes, run this script again or use:"
echo "  az containerapp up --name $APP_NAME --resource-group $RESOURCE_GROUP --source ."
echo ""
echo -e "${GREEN}✓${NC} Your tournament allocator is now live!"
