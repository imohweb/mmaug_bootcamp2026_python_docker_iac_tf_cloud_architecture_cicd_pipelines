resource "azurerm_resource_group" "demo" {
  name     = "${var.prefix}-demo-rg"
  location = var.location
  tags = {
    purpose = "mmaug-beginner-demo"
  }
}

resource "azurerm_container_registry" "app" {
  name                 = "${var.prefix}acr"
  resource_group_name  = azurerm_resource_group.demo.name
  location             = azurerm_resource_group.demo.location
  sku                  = "Basic"
  admin_enabled        = false
  role_assignment_mode = "LegacyRegistryPermissions"
}

module "web" {
  source              = "./modules/web"
  name                = "${var.prefix}-web"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  sku                 = var.app_service_sku
  registry_url        = "https://${azurerm_container_registry.app.login_server}"
  image_name          = "launchpad:${var.image_tag}"
  ai_settings = var.enable_foundry ? {
    FOUNDRY_PROJECT_ENDPOINT = local.foundry_project_endpoint
    FOUNDRY_AGENT_NAME       = var.foundry_agent_name
    AZURE_OPENAI_ENDPOINT    = local.openai_endpoint
    AZURE_OPENAI_DEPLOYMENT  = var.model_deployment_name
    AZURE_OPENAI_API_VERSION = "2024-10-21"
  } : {}
}

module "vm" {
  source              = "./modules/vm"
  name                = "${var.prefix}-vm"
  resource_group_name = azurerm_resource_group.demo.name
  location            = azurerm_resource_group.demo.location
  size                = var.vm_size
  ssh_public_key      = file(pathexpand(var.ssh_public_key_path))
}

resource "azurerm_role_assignment" "web_pull" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = module.web.principal_id
}

resource "azurerm_role_assignment" "vm_pull" {
  scope                = azurerm_container_registry.app.id
  role_definition_name = "AcrPull"
  principal_id         = module.vm.principal_id
}
