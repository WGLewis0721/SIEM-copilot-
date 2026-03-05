# =============================================================================
# CNAP AI SIEM Copilot — Terraform Outputs
# =============================================================================

output "instance_id" {
  description = "EC2 instance ID for SSM connection commands."
  value       = aws_instance.siem_copilot.id
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance."
  value       = aws_instance.siem_copilot.private_ip
}

output "knowledge_bucket" {
  description = "S3 bucket name for the RAG knowledge base (runbooks, SOPs)."
  value       = aws_s3_bucket.knowledge_base.bucket
}

output "backup_bucket" {
  description = "S3 bucket name for automated backups and reports."
  value       = aws_s3_bucket.backup.bucket
}

output "iam_role_arn" {
  description = "ARN of the IAM role attached to the EC2 instance."
  value       = aws_iam_role.siem_copilot.arn
}

output "security_group_id" {
  description = "Security group ID attached to the EC2 instance."
  value       = aws_security_group.siem_copilot.id
}

output "ssm_connect_cmd" {
  description = "AWS CLI command to start an SSM shell session on the instance."
  value       = "aws ssm start-session --target ${aws_instance.siem_copilot.id} --region ${var.aws_region}"
}

output "ssm_webui_cmd" {
  description = "AWS CLI command to forward Open WebUI port 8080 to localhost."
  value       = "aws ssm start-session --target ${aws_instance.siem_copilot.id} --region ${var.aws_region} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"8080\"],\"localPortNumber\":[\"8080\"]}'"
}

output "ssm_dashboard_cmd" {
  description = "AWS CLI command to forward Dashboard port 5000 to localhost."
  value       = "aws ssm start-session --target ${aws_instance.siem_copilot.id} --region ${var.aws_region} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"5000\"],\"localPortNumber\":[\"5000\"]}'"
}
