locals {
  search_service_name    = "${var.prefix}-knowledge"
  search_endpoint        = var.enable_foundry ? "https://${azurerm_search_service.knowledge[0].name}.search.windows.net" : ""
  search_index_name      = "support-policies"
  knowledge_source_name  = "support-blob-source"
  knowledge_base_name    = "support-knowledge"
  search_connection_name = "support-knowledge-mcp"
  knowledge_storage_id   = "/subscriptions/${data.azurerm_client_config.deployer.subscription_id}/resourceGroups/${data.azurerm_resource_group.demo.name}/providers/Microsoft.Storage/storageAccounts/${var.storage_account_name}"
  knowledge_setup_environment = var.enable_foundry ? {
    FOUNDRY_SEARCH_ENDPOINT        = local.search_endpoint
    FOUNDRY_SEARCH_INDEX_NAME      = local.search_index_name
    FOUNDRY_KNOWLEDGE_SOURCE_NAME  = local.knowledge_source_name
    FOUNDRY_KNOWLEDGE_BASE_NAME    = local.knowledge_base_name
    FOUNDRY_SEARCH_CONNECTION_NAME = local.search_connection_name
    FOUNDRY_PROJECT_RESOURCE_ID    = azapi_resource.project[0].id
    AZURE_STORAGE_RESOURCE_ID      = local.knowledge_storage_id
    KNOWLEDGE_CONTAINER            = var.knowledge_container_name
    AZURE_OPENAI_ENDPOINT          = local.openai_endpoint
    AZURE_OPENAI_DEPLOYMENT        = var.model_deployment_name
    AZURE_OPENAI_MODEL_NAME        = var.model_name
  } : {}
}

resource "azurerm_search_service" "knowledge" {
  count                         = var.enable_foundry ? 1 : 0
  name                          = local.search_service_name
  resource_group_name           = data.azurerm_resource_group.demo.name
  location                      = coalesce(var.search_location, var.foundry_location)
  sku                           = "basic"
  replica_count                 = 1
  partition_count               = 1
  local_authentication_enabled  = false
  semantic_search_sku           = "free"
  public_network_access_enabled = true
  identity {
    type = "SystemAssigned"
  }
  tags = local.tags
}

output "knowledge_setup_environment" {
  description = "Non-secret environment map for the OIDC-authenticated Foundry IQ indexing bridge."
  value       = local.knowledge_setup_environment
}
