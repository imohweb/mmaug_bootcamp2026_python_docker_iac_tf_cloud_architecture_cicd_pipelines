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
  description = "Localhost port used to reach the support agent."
  validation {
    condition = (
      var.host_port >= 1024 && var.host_port <= 65535 &&
      floor(var.host_port) == var.host_port
    )
    error_message = "Choose an integer port from 1024 through 65535."
  }
}

variable "specialist_token" {
  type        = string
  sensitive   = true
  description = "Shared specialist console token (32+ characters). Supply it through TF_VAR_specialist_token; never commit it."
  validation {
    condition     = length(var.specialist_token) >= 32
    error_message = "The specialist token must be at least 32 characters."
  }
}

# Build the image first: docker build -t mmaug-support-agent:1.0 .. (from this folder).
resource "docker_image" "support_agent" {
  name         = "mmaug-support-agent:1.0"
  keep_locally = true
}

# Named volume so tickets survive container replacement.
resource "docker_volume" "data" {
  name = "mmaug-support-agent-data"
}

resource "docker_container" "support_agent" {
  name  = "mmaug-support-agent-iac"
  image = docker_image.support_agent.image_id
  env = [
    "AI_MODE=off",
    "SPECIALIST_API_TOKEN=${var.specialist_token}",
  ]
  ports {
    internal = 8000
    external = var.host_port
    ip       = "127.0.0.1"
  }
  volumes {
    volume_name    = docker_volume.data.name
    container_path = "/data"
  }
}

output "app_url" {
  value       = "http://127.0.0.1:${var.host_port}"
  description = "Customer portal; the specialist console is at /#/specialist."
}
