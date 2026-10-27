output "name" {
  value = azurerm_linux_web_app.app.name
}
output "url" {
  value = "https://${azurerm_linux_web_app.app.default_hostname}"
}
