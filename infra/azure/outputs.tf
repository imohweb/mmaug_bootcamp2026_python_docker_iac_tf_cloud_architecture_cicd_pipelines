output "resource_group_name" {
  value = azurerm_resource_group.demo.name
}

output "acr_name" {
  value = azurerm_container_registry.app.name
}

output "acr_login_server" {
  value = azurerm_container_registry.app.login_server
}

output "web_app_name" {
  value = module.web.name
}

output "web_app_url" {
  value = module.web.url
}

output "vm_name" {
  value = module.vm.name
}

output "vm_public_ip" {
  value = module.vm.public_ip
}

output "foundry_project_endpoint" {
  value = var.enable_foundry ? local.foundry_project_endpoint : null
}

output "azure_openai_endpoint" {
  value = var.enable_foundry ? local.openai_endpoint : null
}

output "azure_openai_deployment" {
  value = var.enable_foundry ? azurerm_cognitive_deployment.model[0].name : null
}

output "foundry_agent_name" {
  value      = var.enable_foundry ? var.foundry_agent_name : null
  depends_on = [terraform_data.agent]
}
