output "name" {
  value = data.azurerm_storage_account.data.name
}
output "id" {
  value = data.azurerm_storage_account.data.id
}
output "blob_endpoint" {
  value = data.azurerm_storage_account.data.primary_blob_endpoint
}
output "tickets_container" {
  value = data.azurerm_storage_container.tickets.name
}
output "knowledge_container" {
  value = data.azurerm_storage_container.knowledge.name
}
output "knowledge_blobs" {
  value = sort(keys(azurerm_storage_blob.knowledge))
}
