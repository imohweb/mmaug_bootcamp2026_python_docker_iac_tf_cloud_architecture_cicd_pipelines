output "resource_group_name" {
  value = data.azurerm_resource_group.demo.name
}

output "acr_name" {
  value = azurerm_container_registry.app.name
}

output "acr_login_server" {
  value = azurerm_container_registry.app.login_server
}

output "backend_web_app_name" {
  value = module.backend.name
}

output "backend_web_app_url" {
  value = module.backend.url
}

output "frontend_web_app_name" {
  value = module.frontend.name
}

output "frontend_web_app_url" {
  value = module.frontend.url
}

output "storage_account_name" {
  value = module.storage.name
}

output "storage_account_url" {
  value = trimsuffix(module.storage.blob_endpoint, "/")
}

output "knowledge_documents" {
  value = module.storage.knowledge_blobs
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
