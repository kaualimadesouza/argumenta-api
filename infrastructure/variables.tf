variable "stage" {
  description = "Deployment stage (dev or prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.stage)
    error_message = "stage must be \"dev\" or \"prod\"."
  }
}

variable "image_uri" {
  description = "Pre-built ECR image URI (tagged with the commit SHA); built and pushed by the pipeline's Build and Push job, not by terraform."
  type        = string
}

variable "argumenta_anthropic_api_key" {
  type      = string
  sensitive = true
}

variable "argumenta_google_client_id" {
  type      = string
  sensitive = true
}

variable "argumenta_google_client_secret" {
  type      = string
  sensitive = true
}

variable "argumenta_database_url" {
  type      = string
  sensitive = true
}

variable "argumenta_google_api_key" {
  description = "Gemini API key (Google AI Studio), used when argumenta_llm_vendor is \"google\""
  type        = string
  sensitive   = true
  default     = ""
}

variable "argumenta_llm_vendor" {
  description = "Which vendor answers evaluation and reaction calls: anthropic | openai | google"
  type        = string
  default     = "anthropic"
}

variable "argumenta_evaluation_model" {
  description = "Model name for the graded correction; must match argumenta_llm_vendor"
  type        = string
  default     = "claude-sonnet-5"
}

variable "argumenta_reaction_model" {
  description = "Model name for the character reaction; must match argumenta_llm_vendor unless reaction_llm_vendor overrides it"
  type        = string
  default     = "claude-sonnet-5"
}

variable "argumenta_jwt_secret" {
  type      = string
  sensitive = true
}
