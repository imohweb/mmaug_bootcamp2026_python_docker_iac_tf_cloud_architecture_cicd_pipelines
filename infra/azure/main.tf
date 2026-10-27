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

data "azurerm_user_assigned_identity" "web" {
  name                = split("/", var.web_identity_resource_id)[8]
  resource_group_name = split("/", var.web_identity_resource_id)[4]
  lifecycle {
    postcondition {
      condition     = lower(self.id) == lower(var.web_identity_resource_id)
      error_message = "The existing web identity must belong to the configured deployment subscription."
    }
  }
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
  identity_id         = data.azurerm_user_assigned_identity.web.id
  identity_client_id  = data.azurerm_user_assigned_identity.web.client_id
  app_settings = merge({
    AZURE_CLIENT_ID     = data.azurerm_user_assigned_identity.web.client_id
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
  identity_id         = data.azurerm_user_assigned_identity.web.id
  identity_client_id  = data.azurerm_user_assigned_identity.web.client_id
  app_settings        = { BACKEND_ORIGIN = module.backend.url }
}

module "storage" {
  source              = "./modules/storage"
  name                = var.storage_account_name
  resource_group_name = data.azurerm_resource_group.demo.name
  location            = data.azurerm_resource_group.demo.location
  knowledge_dir       = local.knowledge_dir
  knowledge_container = var.knowledge_container_name
  tickets_container   = var.tickets_container_name
  tags                = local.tags
}
