variable "name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "service_plan_id" {
  type = string
}
variable "registry_url" {
  type = string
}
variable "image_name" {
  type = string
}
variable "identity_id" {
  type = string
}
variable "identity_client_id" {
  type = string
}
variable "app_settings" {
  type        = map(string)
  default     = {}
  description = "Non-secret configuration (storage endpoint, containers, AI mode, Foundry endpoints)."
}
