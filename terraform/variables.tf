# =============================================================================
# CNAP AI SIEM Copilot — Terraform Variables
# =============================================================================

# --- Required Variables ---

variable "aws_region" {
  description = "AWS region (GovCloud: us-gov-west-1 or us-gov-east-1; commercial: us-east-1 etc.)"
  type        = string
  default     = "us-gov-west-1"
}

variable "vpc_id" {
  description = "VPC ID where the EC2 instance and security groups will be created."
  type        = string
}

variable "subnet_id" {
  description = "Private subnet ID for the EC2 instance. Must be in the specified VPC."
  type        = string
}

variable "opensearch_endpoint" {
  description = "AWS OpenSearch domain endpoint (without https://). Example: vpc-my-domain.us-gov-west-1.es.amazonaws.com"
  type        = string
}

# --- Optional / Defaulted Variables ---

variable "project_name" {
  description = "Name prefix used for all resource names."
  type        = string
  default     = "cnap-ai-siem"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "instance_type" {
  description = "EC2 instance type. Use g4dn.xlarge for GPU inference, t3.xlarge for CPU-only."
  type        = string
  default     = "g4dn.xlarge"

  validation {
    condition     = contains(["g4dn.xlarge", "g4dn.2xlarge", "t3.xlarge", "t3.2xlarge", "p3.2xlarge"], var.instance_type)
    error_message = "instance_type must be one of the supported GPU or CPU instance types."
  }
}

variable "ebs_volume_size_gb" {
  description = "Size of the root EBS volume in GB. Minimum 100GB recommended for LLM models."
  type        = number
  default     = 100

  validation {
    condition     = var.ebs_volume_size_gb >= 100
    error_message = "EBS volume must be at least 100GB to accommodate LLM models."
  }
}

variable "ssh_key_name" {
  description = "Optional EC2 key pair name for emergency SSH access. Leave empty to disable SSH (SSM only)."
  type        = string
  default     = ""
}

variable "owner_tag" {
  description = "Owner tag value for AWS resources (e.g., team name or email)."
  type        = string
  default     = "cnap-security-team"
}

variable "opensearch_indices" {
  description = "Comma-separated list of OpenSearch index patterns to query."
  type        = string
  default     = "cwl-*,appgate-logs-*,security-logs-*"
}

variable "ollama_model" {
  description = "Ollama LLM model name to use for analysis."
  type        = string
  default     = "llama3.1:8b"
}

variable "ollama_embedding_model" {
  description = "Ollama embedding model name for RAG vector search."
  type        = string
  default     = "nomic-embed-text"
}

variable "rag_interval_minutes" {
  description = "Interval in minutes between RAG analysis runs."
  type        = number
  default     = 30
}

variable "time_range_hours" {
  description = "Number of hours of logs to include in each analysis window."
  type        = number
  default     = 720
}

variable "s3_backup_retention_days" {
  description = "Number of days to retain backup files in S3 before expiry."
  type        = number
  default     = 90
}

variable "enable_gpu" {
  description = "Whether to configure NVIDIA GPU support. Set false for CPU-only instances."
  type        = bool
  default     = true
}
