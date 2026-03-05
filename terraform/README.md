# CNAP AI SIEM Copilot — Terraform

This directory contains the Infrastructure as Code (IaC) for deploying CNAP AI SIEM Copilot on AWS GovCloud.

## Resources Created

| Resource | Description |
|----------|-------------|
| `aws_instance` | EC2 instance (g4dn.xlarge or t3.xlarge) with Ubuntu 24.04 |
| `aws_iam_role` | IAM role with least-privilege policies |
| `aws_iam_instance_profile` | Instance profile attaching the role to EC2 |
| `aws_s3_bucket` (x2) | Knowledge base bucket + backup bucket |
| `aws_security_group` | Default-deny SG with SSM-only outbound access |

## Deployment

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

terraform init
terraform plan
terraform apply
```

## Required Variables

| Variable | Description |
|----------|-------------|
| `aws_region` | AWS region (e.g., `us-gov-west-1`) |
| `vpc_id` | VPC ID for the instance |
| `subnet_id` | Private subnet ID |
| `opensearch_endpoint` | OpenSearch domain endpoint (no https://) |

See `variables.tf` for all variable definitions and defaults.
