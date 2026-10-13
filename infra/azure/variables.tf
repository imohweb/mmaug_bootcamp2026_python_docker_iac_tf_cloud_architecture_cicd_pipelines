variable "subscription_id" {
  type        = string
  description = "Explicit Azure subscription for this paid teaching lab."
}

variable "prefix" {
  type        = string
  description = "Globally distinctive lowercase name used for ACR and the web app."
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{5,17}$", var.prefix))
    error_message = "Use 6-18 lowercase letters/digits, beginning with a letter."
  }
}

variable "location" {
  type        = string
  default     = "westeurope"
  description = "Choose a region with App Service and VM capacity in your subscription."
}

variable "ssh_public_key_path" {
  type        = string
  description = "Path to an existing SSH public key; never pass the private key."
}

variable "vm_size" {
  type        = string
  default     = "Standard_B2s"
  description = "Teaching VM size; capacity and quota must be checked before applying."
}

variable "app_service_sku" {
  type        = string
  default     = "B1"
  description = "Paid Linux App Service plan. Cost continues even if the app is stopped."
}

variable "image_tag" {
  type        = string
  default     = "bootstrap"
  description = "Initial image tag; delivery pipelines own later releases."
}
