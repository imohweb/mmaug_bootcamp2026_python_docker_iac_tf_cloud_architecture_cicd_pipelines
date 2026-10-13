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
