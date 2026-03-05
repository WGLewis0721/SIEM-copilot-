# =============================================================================
# CNAP AI SIEM Copilot — IAM Roles and Policies
# Uses EC2 instance profile — NO hardcoded credentials
# =============================================================================

# IAM Role for EC2 instance
resource "aws_iam_role" "siem_copilot" {
  name        = "${local.name_prefix}-role"
  description = "IAM role for CNAP AI SIEM Copilot EC2 instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Policy: OpenSearch access (full HTTP operations on the domain)
resource "aws_iam_policy" "opensearch_access" {
  name        = "${local.name_prefix}-opensearch-policy"
  description = "Allow SIEM Copilot to perform HTTP operations on OpenSearch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["es:ESHttp*"]
        Resource = "arn:${data.aws_partition.current.partition}:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/*"
      }
    ]
  })
}

# Policy: S3 knowledge base read/write
resource "aws_iam_policy" "s3_knowledge_base" {
  name        = "${local.name_prefix}-s3-knowledge-policy"
  description = "Allow SIEM Copilot to read/write the knowledge base and backup S3 buckets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          aws_s3_bucket.knowledge_base.arn,
          "${aws_s3_bucket.knowledge_base.arn}/*",
          aws_s3_bucket.backup.arn,
          "${aws_s3_bucket.backup.arn}/*",
        ]
      }
    ]
  })
}

# Policy: CloudWatch Logs (structured logging from containers)
resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${local.name_prefix}-cloudwatch-policy"
  description = "Allow SIEM Copilot to write structured logs to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups",
        ]
        Resource = "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/cnap-siem/*"
      }
    ]
  })
}

# Attach AWS-managed SSM policy for Session Manager access
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.siem_copilot.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Attach custom policies
resource "aws_iam_role_policy_attachment" "opensearch" {
  role       = aws_iam_role.siem_copilot.name
  policy_arn = aws_iam_policy.opensearch_access.arn
}

resource "aws_iam_role_policy_attachment" "s3" {
  role       = aws_iam_role.siem_copilot.name
  policy_arn = aws_iam_policy.s3_knowledge_base.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.siem_copilot.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

# Data source for partition (handles GovCloud vs commercial)
data "aws_partition" "current" {}
