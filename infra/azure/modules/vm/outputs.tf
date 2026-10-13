output "name" {
  value = azurerm_linux_virtual_machine.vm.name
}
output "public_ip" {
  value = azurerm_public_ip.app.ip_address
}
output "principal_id" {
  value = azurerm_linux_virtual_machine.vm.identity[0].principal_id
}
