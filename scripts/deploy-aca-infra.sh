#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../.env" ]]; then
	echo "Loading .env"
	source "$script_dir/../.env"
fi

if [[ ${#BASENAME} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable BASENAME' 1>&2
  exit 6
fi

if [[ ${#LOCATION} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable LOCATION' 1>&2
  exit 6
fi

if [[ ${#SIMULATOR_MODE} -eq 0 ]]; then
  echo 'ERROR: Missing environment variable SIMULATOR_MODE' 1>&2
  exit 6
fi


RESOURCE_GROUP_NAME="aoaisim"

cat << EOF > "$script_dir/../infra/azuredeploy.parameters.json"
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "location": {
      "value": "${LOCATION}"
    },
    "baseName": {
      "value": "${BASENAME}"
    },
	"simulatorMode": {
	  "value": "${SIMULATOR_MODE}"
	},
	"simulatorApiKey": {
	  "value": "${SIMULATOR_API_KEY}"
	}
  }
}
EOF

deployment_name="deployment-${BASENAME}-${LOCATION}"
cd "$script_dir/../infra/"
echo "=="
echo "==Starting main bicep deployment ($deployment_name)"
echo "=="
output=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --template-file main.bicep \
  --name "$deployment_name" \
  --parameters azuredeploy.parameters.json \
  --output json)
echo "$output" | jq "[.properties.outputs | to_entries | .[] | {key:.key, value: .value.value}] | from_entries" > "$script_dir/../infra/output.json"
