terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    time    = { source = "hashicorp/time" }
  }
}

# Bootstrap owns these objects: workload destroy must never delete its backend.
data "azurerm_storage_account" "data" {
  name                = var.name
  resource_group_name = var.resource_group_name
}

data "azurerm_storage_container" "tickets" {
  name               = var.tickets_container
  storage_account_id = data.azurerm_storage_account.data.id
}

data "azurerm_storage_container" "knowledge" {
  name               = var.knowledge_container
  storage_account_id = data.azurerm_storage_account.data.id
}

resource "azurerm_storage_blob" "knowledge" {
  for_each             = fileset(var.knowledge_dir, "*.md")
  name                 = each.value
  storage_container_id = data.azurerm_storage_container.knowledge.id
  type                 = "Block"
  source               = "${var.knowledge_dir}/${each.value}"
  content_md5          = filemd5("${var.knowledge_dir}/${each.value}")
  content_type         = "text/markdown; charset=utf-8"
}
