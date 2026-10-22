variable "subscription_id" {
  type        = string
  description = "Explicit Azure subscription for this paid teaching lab."
}

variable "resource_group_name" {
  type    = string
  default = "RG-MMAUG-Bootcamp"
  validation {
    condition     = var.resource_group_name == "RG-MMAUG-Bootcamp"
    error_message = "Only existing RG-MMAUG-Bootcamp is supported."
  }
}

variable "storage_account_name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Supply the bootstrapped storage account name."
  }
}

variable "knowledge_container_name" {
  type    = string
  default = "knowledge"
}

variable "tickets_container_name" {
  type    = string
  default = "tickets"
}

variable "prefix" {
  type        = string
  description = "Globally distinctive lowercase name used for ACR, storage and the web app."
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{5,17}$", var.prefix))
    error_message = "Use 6-18 lowercase letters/digits, beginning with a letter (for example, mmaugbootcamp26). Hyphens are not allowed because the prefix is also used for the ACR name; Terraform appends acr automatically."
  }
}

variable "location" {
  type        = string
  default     = "westeurope"
  description = "Choose a region with App Service capacity in your subscription."
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
  default     = true
  description = "Deploy paid Foundry/model resources and provision the support drafting agent. When false the app uses knowledge-base templates only."
}

variable "ai_mode" {
  type        = string
  default     = "agent"
  description = "How the app drafts replies when Foundry is enabled: agent (Foundry prompt agent) or model (direct Azure OpenAI deployment)."
  validation {
    condition     = contains(["agent", "model"], var.ai_mode)
    error_message = "ai_mode must be agent or model."
  }
}

variable "foundry_location" {
  type        = string
  default     = "eastus2"
  description = "Verify Foundry Agent Service support and chosen model/version/SKU quota here."
}

variable "model_name" {
  type    = string
  default = "gpt-6.1-sol"
}

variable "model_version" {
  type    = string
  default = "2026-09-29"
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
  default     = "mmaug-support-agent"
  description = "Dedicated lab-owned agent; Terraform destroy deletes this agent and its versions."
}

variable "foundry_agent_instructions" {
  type        = string
  default     = "You are the MMAUG customer support drafting agent. Classify each customer message as billing, technical, account or general and set priority high or normal. Draft a short, polite reply grounded only in the knowledge excerpts you are given; if they do not cover the question, say a specialist will follow up. Never request passwords, card numbers or other secrets. A human specialist reviews every draft before it is sent. Reply only with JSON: {\"category\": \"...\", \"priority\": \"...\", \"reply\": \"...\"}."
  description = "Prompt-agent instructions; the app also sends its own system prompt and knowledge excerpts."
}

variable "agent_python_executable" {
  type        = string
  default     = "python3"
  description = "Python with support-agent/backend/requirements.txt installed, used by the Terraform agent bridge."
}
