variable "name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "sku" {
  type = string
}
variable "registry_url" {
  type = string
}
variable "image_name" {
  type = string
}
variable "ai_settings" {
  type        = map(string)
  default     = {}
  description = "Non-secret Foundry and model configuration."
}
