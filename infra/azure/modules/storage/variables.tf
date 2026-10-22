variable "name" {
  type        = string
  description = "Globally unique storage account name (3-24 lowercase letters and digits)."
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.name))
    error_message = "Storage account names must be 3-24 lowercase letters or digits."
  }
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "replication_type" {
  type    = string
  default = "LRS"
}
variable "tickets_container" {
  type    = string
  default = "tickets"
}
variable "knowledge_container" {
  type    = string
  default = "knowledge"
}
variable "knowledge_dir" {
  type        = string
  description = "Folder of Markdown knowledge documents uploaded to the knowledge container."
}
variable "app_principal_id" {
  type        = string
  description = "Managed identity of the web app."
}
variable "deployer_principal_id" {
  type        = string
  description = "Object ID of the identity running Terraform."
}
variable "tags" {
  type    = map(string)
  default = {}
}
