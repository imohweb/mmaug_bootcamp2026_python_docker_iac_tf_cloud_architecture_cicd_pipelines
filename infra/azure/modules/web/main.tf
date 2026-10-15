terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

resource "azurerm_service_plan" "app" {
  name                = "${var.name}-plan"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = var.sku
}

resource "azurerm_linux_web_app" "app" {
  name                                           = var.name
  resource_group_name                            = var.resource_group_name
  location                                       = var.location
  service_plan_id                                = azurerm_service_plan.app.id
  https_only                                     = true
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  identity {
    type = "SystemAssigned"
  }
  site_config {
    always_on                               = true
    minimum_tls_version                     = "1.2"
    health_check_path                       = "/health"
    container_registry_use_managed_identity = true
    application_stack {
      docker_image_name   = var.image_name
      docker_registry_url = var.registry_url
    }
  }
  app_settings = merge({
    WEBSITES_PORT = "8000"
    APP_MESSAGE   = "Hello from Azure App Service!"
  }, var.ai_settings)
  lifecycle {
    # Pipelines own image releases; Terraform owns the surrounding infrastructure.
    ignore_changes = [
      site_config[0].application_stack[0].docker_image_name,
      app_settings["AI_DEMO_API_TOKEN"],
    ]
  }
}
