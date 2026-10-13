terraform {
  required_version = ">= 1.5, < 2.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
  }
}

provider "azurerm" {
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  features {}
}

variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "westeurope"
}

resource "azurerm_resource_group" "imported" {
  name     = "mmaug-import-demo-rg"
  location = var.location
}
