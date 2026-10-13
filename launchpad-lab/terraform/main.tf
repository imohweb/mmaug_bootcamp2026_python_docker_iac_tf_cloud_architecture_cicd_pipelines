terraform {
  required_version = ">= 1.5, < 2.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "host_port" {
  type        = number
  default     = 8080
  description = "Localhost port used to reach Launchpad."
  validation {
    condition = (
      var.host_port >= 1024 && var.host_port <= 65535 &&
      floor(var.host_port) == var.host_port
    )
    error_message = "Choose an integer port from 1024 through 65535."
  }
}

variable "app_message" {
  type        = string
  default     = "Hello from Terraform!"
  description = "Public demo greeting; do not put secrets here."
}

resource "docker_image" "launchpad" {
  name         = "mmaug-launchpad:1.0"
  keep_locally = true
}

resource "docker_container" "launchpad" {
  name  = "mmaug-launchpad-iac"
  image = docker_image.launchpad.image_id
  env   = ["APP_MESSAGE=${var.app_message}"]
  ports {
    internal = 8000
    external = var.host_port
    ip       = "127.0.0.1"
  }
}

output "app_url" {
  value       = "http://127.0.0.1:${var.host_port}"
  description = "Launchpad URL; verify /health after apply."
}
