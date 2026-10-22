locals {
  tags = {
    purpose = "mmaug-beginner-demo"
    app     = "support-agent"
  }
  knowledge_dir = abspath("${path.module}/../../support-agent/knowledge")
}

data "azurerm_resource_group" "demo" {
  name = var.resource_group_name
}

resource "azurerm_service_plan" "app" {
  name                = "${var.prefix}-plan"
  resource_group_name = data.azurerm_resource_group.demo.name
  location            = data.azurerm_resource_group.demo.location
  os_type             = "Linux"
  sku_name            = var.app_service_sku
}

resource "azurerm_container_registry" "app" {
  name                 = "${var.prefix}acr"
  resource_group_name  = data.azurerm_resource_group.demo.name
  location             = data.azurerm_resource_group.demo.location
  sku                  = "Basic"
  admin_enabled        = false
  role_assignment_mode = "LegacyRegistryPermissions"
}

module "backend" {
  source              = "./modules/web"
  name                = "${var.prefix}-backend"
  resource_group_name = data.azurerm_resource_group.demo.name
  location            = data.azurerm_resource_group.demo.location
  service_plan_id     = azurerm_service_plan.app.id
  registry_url        = "https://${azurerm_container_registry.app.login_server}"
  image_name          = "support-agent-backend:${var.image_tag}"
  app_settings = merge({
    STORAGE_ACCOUNT_URL = trimsuffix(module.storage.blob_endpoint, "/")
    TICKETS_CONTAINER   = module.storage.tickets_container
    KNOWLEDGE_CONTAINER = module.storage.knowledge_container
    AI_MODE             = var.enable_foundry ? var.ai_mode : "off"
    }, var.enable_foundry ? {
    FOUNDRY_PROJECT_ENDPOINT = local.foundry_project_endpoint
    FOUNDRY_AGENT_NAME       = var.foundry_agent_name
    FOUNDRY_SEARCH_ENDPOINT  = local.search_endpoint
    AZURE_OPENAI_ENDPOINT    = local.openai_endpoint
    AZURE_OPENAI_DEPLOYMENT  = var.model_deployment_name
    AZURE_OPENAI_API_VERSION = "2024-10-21"
  } : {})
}

module "frontend" {
  source              = "./modules/web"
  name                = "${var.prefix}-frontend"
  resource_group_name = data.azurerm_resource_group.demo.name
  location            = data.azurerm_resource_group.demo.location
  service_plan_id     = azurerm_service_plan.app.id
  registry_url        = "https://${azurerm_container_registry.app.login_server}"
  image_name          = "support-agent-frontend:${var.image_tag}"
  app_settings        = { BACKEND_ORIGIN = module.backend.url }
}

module "storage" {
  source                = "./modules/storage"
  name                  = var.storage_account_name
  resource_group_name   = data.azurerm_resource_group.demo.name
  location              = data.azurerm_resource_group.demo.location
  knowledge_dir         = local.knowledge_dir
  app_principal_id      = module.backend.principal_id
  knowledge_container   = var.knowledge_container_name
  tickets_container     = var.tickets_container_name
  deployer_principal_id = data.azurerm_client_config.deployer.object_id
  tags                  = local.tags
}

resource "azurerm_role_assignment" "backend_pull" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = module.backend.principal_id
}

resource "azurerm_role_assignment" "frontend_pull" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = module.frontend.principal_id
}
