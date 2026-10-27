terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

resource "azurerm_linux_web_app" "app" {
  name                                           = var.name
  resource_group_name                            = var.resource_group_name
  location                                       = var.location
  service_plan_id                                = var.service_plan_id
  https_only                                     = true
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false
  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }
  site_config {
    always_on                                     = true
    minimum_tls_version                           = "1.2"
    health_check_path                             = "/health"
    health_check_eviction_time_in_min             = 2
    container_registry_use_managed_identity       = true
    container_registry_managed_identity_client_id = var.identity_client_id
    application_stack {
      docker_image_name   = var.image_name
      docker_registry_url = var.registry_url
    }
  }
  app_settings = merge({
    WEBSITES_PORT = "8000"
  }, var.app_settings)
  lifecycle {
    # Pipelines own image releases and the specialist token; Terraform owns the rest.
    ignore_changes = [
      site_config[0].application_stack[0].docker_image_name,
      app_settings["SPECIALIST_API_TOKEN"],
    ]
  }
}
