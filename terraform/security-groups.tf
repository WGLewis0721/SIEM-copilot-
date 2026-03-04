# =============================================================================
# CNAP AI SIEM Copilot — Security Groups
# Deny-by-default; access via SSM Session Manager only (no SSH inbound)
# =============================================================================

resource "aws_security_group" "siem_copilot" {
  name        = "${local.name_prefix}-sg"
  description = "Security group for CNAP AI SIEM Copilot — SSM-only access, no inbound SSH"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${local.name_prefix}-sg"
  }
}

# --- Outbound Rules ---

# HTTPS to AWS services (SSM, S3, ECR, CloudWatch)
resource "aws_vpc_security_group_egress_rule" "https_out" {
  security_group_id = aws_security_group.siem_copilot.id
  description       = "HTTPS outbound to AWS services and internet"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# HTTP outbound (needed for Ollama model downloads)
resource "aws_vpc_security_group_egress_rule" "http_out" {
  security_group_id = aws_security_group.siem_copilot.id
  description       = "HTTP outbound for package downloads"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

# DNS resolution
resource "aws_vpc_security_group_egress_rule" "dns_udp_out" {
  security_group_id = aws_security_group.siem_copilot.id
  description       = "DNS UDP outbound"
  ip_protocol       = "udp"
  from_port         = 53
  to_port           = 53
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "dns_tcp_out" {
  security_group_id = aws_security_group.siem_copilot.id
  description       = "DNS TCP outbound"
  ip_protocol       = "tcp"
  from_port         = 53
  to_port           = 53
  cidr_ipv4         = "0.0.0.0/0"
}

# NOTE: No inbound rules — SSM Session Manager does not require open ports.
# AWS SSM Agent on the instance initiates outbound connections to SSM endpoints.
# Users connect via SSM console or CLI without needing inbound rules.
