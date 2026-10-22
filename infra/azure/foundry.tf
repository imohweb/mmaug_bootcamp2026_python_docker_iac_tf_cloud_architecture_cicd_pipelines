locals {
  foundry_name = "${var.prefix}-foundry"
  # Name kept from the earlier lab so existing projects are updated in place, not replaced.
  foundry_project_name               = "launchpad"
  foundry_project_endpoint           = "https://${local.foundry_name}.services.ai.azure.com/api/projects/${local.foundry_project_name}"
  openai_endpoint                    = "https://${local.foundry_name}.openai.azure.com/"
  azure_ai_developer_role_id         = "64702f94-c441-49e6-a78b-ef80e0188fee"
  azure_ai_developer_role_definition = "/subscriptions/${data.azurerm_client_config.deployer.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.azure_ai_developer_role_id}"
}

data "azurerm_client_config" "deployer" {}

resource "azapi_resource" "foundry" {
  count     = var.enable_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name      = local.foundry_name
  parent_id = data.azurerm_resource_group.demo.id
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
  name      = local.foundry_project_name
  parent_id = azapi_resource.foundry[0].id
  location  = var.foundry_location
  identity {
    type = "SystemAssigned"
  }
  body = {
    properties = {
      displayName = "MMAUG Support Agent"
      description = "Drafts customer support replies for human specialist approval"
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
  # Cognitive Services rejects concurrent child-resource updates on the account.
  depends_on = [azapi_resource.project]
}

resource "azurerm_role_assignment" "web_agent" {
  count              = var.enable_foundry ? 1 : 0
  scope              = azapi_resource.project[0].id
  role_definition_id = local.azure_ai_developer_role_definition
  principal_id       = module.backend.principal_id
}

resource "azurerm_role_assignment" "web_model" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = module.backend.principal_id
}

resource "azurerm_role_assignment" "project_model" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azapi_resource.project[0].output.identity.principalId
}

resource "azurerm_role_assignment" "agent_deployer" {
  count              = var.enable_foundry ? 1 : 0
  scope              = azapi_resource.foundry[0].id
  role_definition_id = local.azure_ai_developer_role_definition
  principal_id       = data.azurerm_client_config.deployer.object_id
}

# Agents use a data-plane API, not an ARM child resource supported by this configuration.
resource "terraform_data" "knowledge_setup" {
  count = var.enable_foundry ? 1 : 0
  triggers_replace = [
    local.search_endpoint, azapi_resource.project[0].id,
    filesha256("${path.module}/../../support-agent/backend/setup_knowledge_index.py"),
    sha256(join("", [for f in sort(fileset(local.knowledge_dir, "*.md")) : filesha256("${local.knowledge_dir}/${f}")])),
  ]
  provisioner "local-exec" {
    interpreter = [var.agent_python_executable, abspath("${path.module}/../../support-agent/backend/setup_knowledge_index.py"), "--knowledge-dir"]
    command     = local.knowledge_dir
    environment = local.knowledge_setup_environment
  }
  depends_on = [
    module.storage, azurerm_cognitive_deployment.model,
    azurerm_role_assignment.search_blob_reader,
    azurerm_role_assignment.search_model_user,
    azurerm_role_assignment.project_search_reader,
    azurerm_role_assignment.search_deployer,
    azurerm_role_assignment.search_deployer_reader,
    azurerm_role_assignment.agent_deployer,
  ]
}

resource "terraform_data" "agent" {
  count = var.enable_foundry ? 1 : 0
  input = {
    endpoint          = local.foundry_project_endpoint
    name              = var.foundry_agent_name
    model             = var.model_deployment_name
    instructions      = var.foundry_agent_instructions
    python_executable = var.agent_python_executable
    script_path       = abspath("${path.module}/../../support-agent/backend/manage_agent.py")
  }
  triggers_replace = [
    local.foundry_project_endpoint, var.foundry_agent_name,
    var.model_deployment_name, var.foundry_agent_instructions,
    filesha256("${path.module}/../../support-agent/backend/manage_agent.py"),
    terraform_data.knowledge_setup[0].id,
  ]
  provisioner "local-exec" {
    interpreter = [self.input.python_executable, self.input.script_path]
    command     = "create"
    environment = {
      FOUNDRY_PROJECT_ENDPOINT       = self.input.endpoint
      FOUNDRY_AGENT_NAME             = self.input.name
      AZURE_OPENAI_DEPLOYMENT        = self.input.model
      FOUNDRY_AGENT_INSTRUCTIONS     = self.input.instructions
      FOUNDRY_SEARCH_ENDPOINT        = local.search_endpoint
      FOUNDRY_KNOWLEDGE_BASE_NAME    = local.knowledge_base_name
      FOUNDRY_SEARCH_CONNECTION_NAME = local.search_connection_name
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
    terraform_data.knowledge_setup,
  ]
}
