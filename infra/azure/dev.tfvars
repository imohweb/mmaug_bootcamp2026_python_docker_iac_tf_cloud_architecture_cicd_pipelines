# Development environment values. Placeholders only: this file is committed.
# Usage: terraform plan -var-file=dev.tfvars -out=azure.tfplan
subscription_id      = "00000000-0000-0000-0000-000000000000"
prefix               = "mmaugyourname26"
resource_group_name  = "RG-MMAUG-Bootcamp"
storage_account_name = "replacestorageaccount"
location             = "northeurope"
app_service_sku      = "B1"
image_tag            = "bootstrap"

# Paid AI drafting. Set enable_foundry = false to run on knowledge templates only.
# Verify model availability, quota and cost before applying.
enable_foundry        = true
ai_mode               = "agent"
foundry_location      = "eastus2"
model_name            = "gpt-6.1-sol"
model_version         = "2026-09-29"
model_deployment_name = "demo-model"
model_sku             = "GlobalStandard"
model_capacity        = 10
foundry_agent_name    = "mmaug-support-agent"
# Export TF_VAR_agent_python_executable as the absolute path to the prepared venv
# (support-agent/backend/.venv/bin/python).
