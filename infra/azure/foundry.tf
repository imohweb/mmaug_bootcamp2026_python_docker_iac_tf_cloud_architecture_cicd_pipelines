locals {
  foundry_name             = "${var.prefix}-foundry"
  foundry_project_endpoint = "https://${local.foundry_name}.services.ai.azure.com/api/projects/launchpad"
  openai_endpoint          = "https://${local.foundry_name}.openai.azure.com/"
}

data "azurerm_client_config" "deployer" {}

resource "azapi_resource" "foundry" {
  count     = var.enable_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name      = local.foundry_name
  parent_id = azurerm_resource_group.demo.id
  location  = var.foundry_location
  identity {
    type = "SystemAssigned"
  }
  body = {
    kind = "AIServices"
    sku  = { name = "S0" }
    properties = {
      allowProjectManagement = true
      customSubDomainName    = local.foundry_name
      disableLocalAuth       = true
      publicNetworkAccess    = "Enabled"
    }
  }
}

resource "azapi_resource" "project" {
  count     = var.enable_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name      = "launchpad"
  parent_id = azapi_resource.foundry[0].id
  location  = var.foundry_location
  identity {
    type = "SystemAssigned"
  }
  body = {
    properties = {
      displayName = "MMAUG Launchpad"
      description = "Optional instructor-led prompt-agent demo"
    }
  }
  response_export_values = ["identity.principalId"]
}

resource "azurerm_cognitive_deployment" "model" {
  count                = var.enable_foundry ? 1 : 0
  name                 = var.model_deployment_name
  cognitive_account_id = azapi_resource.foundry[0].id
  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }
  sku {
    name     = var.model_sku
    capacity = var.model_capacity
  }
}

resource "azurerm_role_assignment" "web_agent" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.project[0].id
  role_definition_name = "Azure AI User"
  principal_id         = module.web.principal_id
}

resource "azurerm_role_assignment" "web_model" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = module.web.principal_id
}

resource "azurerm_role_assignment" "project_model" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azapi_resource.project[0].output.identity.principalId
}

resource "azurerm_role_assignment" "agent_deployer" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Azure AI User"
  principal_id         = data.azurerm_client_config.deployer.object_id
}

# Agents use a data-plane API, not an ARM child resource supported by this configuration.
resource "terraform_data" "agent" {
  count = var.enable_foundry ? 1 : 0
  input = {
    endpoint          = local.foundry_project_endpoint
    name              = var.foundry_agent_name
    model             = var.model_deployment_name
    instructions      = var.foundry_agent_instructions
    python_executable = var.agent_python_executable
    script_path       = abspath("${path.module}/../../launchpad-lab/manage_agent.py")
  }
  triggers_replace = [
    local.foundry_project_endpoint, var.foundry_agent_name,
    var.model_deployment_name, var.foundry_agent_instructions,
    filesha256("${path.module}/../../launchpad-lab/manage_agent.py"),
  ]
  provisioner "local-exec" {
    interpreter = [self.input.python_executable, self.input.script_path]
    command     = "create"
    environment = {
      FOUNDRY_PROJECT_ENDPOINT   = self.input.endpoint
      FOUNDRY_AGENT_NAME         = self.input.name
      AZURE_OPENAI_DEPLOYMENT    = self.input.model
      FOUNDRY_AGENT_INSTRUCTIONS = self.input.instructions
    }
  }
  provisioner "local-exec" {
    when        = destroy
    interpreter = [self.input.python_executable, self.input.script_path]
    command     = "delete"
    environment = {
      FOUNDRY_PROJECT_ENDPOINT = self.input.endpoint
      FOUNDRY_AGENT_NAME       = self.input.name
    }
  }
  depends_on = [
    azurerm_cognitive_deployment.model,
    azurerm_role_assignment.agent_deployer,
    azurerm_role_assignment.project_model,
  ]
}
