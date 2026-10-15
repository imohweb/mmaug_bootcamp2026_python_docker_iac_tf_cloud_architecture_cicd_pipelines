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

variable "enable_foundry" {
  type        = bool
  default     = false
  description = "Opt in to paid Foundry/model resources and SDK-based agent provisioning."
}

variable "foundry_location" {
  type        = string
  default     = "eastus2"
  description = "Verify Foundry Agent Service support and chosen model/version/SKU quota here."
}

variable "model_name" {
  type    = string
  default = "gpt-4.1-mini"
}

variable "model_version" {
  type    = string
  default = "2025-04-14"
}

variable "model_deployment_name" {
  type    = string
  default = "demo-model"
}

variable "model_sku" {
  type    = string
  default = "GlobalStandard"
}

variable "model_capacity" {
  type        = number
  default     = 10
  description = "Capacity units depend on model/SKU; check quota, availability and cost before apply."
  validation {
    condition     = var.model_capacity >= 1 && floor(var.model_capacity) == var.model_capacity
    error_message = "Model capacity must be a positive integer."
  }
}

variable "foundry_agent_name" {
  type        = string
  default     = "mmaug-launchpad-tutor"
  description = "Dedicated lab-owned agent; Terraform destroy deletes this agent and its versions."
}

variable "foundry_agent_instructions" {
  type    = string
  default = "You are the MMAUG tutor. Explain Python, Docker, Terraform and Azure to beginners. Keep answers short and never request credentials."
}

variable "agent_python_executable" {
  type        = string
  default     = "python3"
  description = "Python with launchpad-lab/requirements.txt installed, used by the Terraform agent bridge."
}
