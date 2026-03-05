# CNAP AI SIEM Copilot — Security Considerations

## Security Design Principles

### 1. Zero Credentials in Code

**Policy:** No AWS credentials, API keys, passwords, or secrets are stored in:
- Source code files
- Docker images
- Environment variables committed to git
- Configuration files

**Implementation:**
- EC2 instance uses IAM Instance Profile (automatic credential rotation via STS)
- boto3 uses the automatic credential chain (instance profile → environment → file)
- `.env` file is listed in `.gitignore`
- `.env.example` contains only placeholder values

### 2. Zero Trust Network Access

**Policy:** No inbound ports are open on the EC2 instance.

**Implementation:**
- Security Group has zero inbound rules
- All access via AWS SSM Session Manager (port forwarding)
- SSM works through outbound HTTPS (port 443) only
- No public IP attached to the instance

### 3. Least Privilege IAM

The EC2 IAM role has only the permissions required:

```
OpenSearch: es:ESHttp* on the specific domain
S3: GetObject, PutObject, ListBucket on specific buckets only
CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents (specific log group)
SSM: AmazonSSMManagedInstanceCore (managed policy)
```

**Not granted:**
- `ec2:*` — the instance cannot manage other EC2 resources
- `iam:*` — cannot modify IAM
- `s3:*` on all buckets — restricted to specific bucket ARNs
- Cross-account access

### 4. Data Encryption

| Data | Encryption |
|------|-----------|
| S3 objects | AES-256 (SSE-S3) |
| EBS volume | AES-256 (AWS Managed Key) |
| OpenSearch | TLS 1.2+ in transit |
| Docker volumes | Protected by EBS encryption |
| Backups | AES-256 on S3 |

### 5. IMDSv2 Required

The EC2 instance is configured with `http_tokens = "required"`, enforcing IMDSv2 for all instance metadata API calls. This prevents SSRF attacks from being able to steal instance credentials.

---

## Open WebUI Security Configuration

### Authentication

- WEBUI_AUTH is set to `true` (authentication required)
- First user to register becomes admin
- After initial setup: Disable new user registration in Admin Panel
- Set strong password requirements (minimum 12 characters)

### Session Management

- Session cookie is `same-site: strict`
- Recommended session timeout: 8 hours
- Access only via SSM port forward (no internet exposure)

### Recommended Post-Deployment Hardening

1. Go to Admin Panel → Users → Change signup policy to "Admin Only"
2. Review and disable any default models not needed
3. Enable audit logging (Admin Panel → Logs)
4. Set up regular password rotation reminders

---

## Threat Model

### In Scope Threats

| Threat | Mitigation |
|--------|-----------|
| Credential theft | IAM roles (no static credentials) |
| SSRF to IMDS | IMDSv2 required |
| Container escape | Non-root containers, read-only S3 mount |
| Log tampering | S3 bucket versioning enabled |
| Unauthorized access to reports | Access only via SSM + auth |
| Network-based attack | No inbound ports, VPC-private only |

### Out of Scope (Assumed)

- Physical access to AWS infrastructure
- Compromise of AWS control plane
- Insider threat with AWS account access

---

## Compliance Notes

This system is designed for IL6 GovCloud deployment. Additional compliance requirements (FISMA, NIST 800-53, FedRAMP) should be validated with your compliance team before use in classified environments.

Key controls supported:
- **AC-2**: Account management (Open WebUI user authentication)
- **AC-6**: Least privilege (IAM minimal permissions)
- **AU-9**: Protection of audit information (S3 versioning, CloudWatch logs)
- **IA-2**: Identification and authentication (SSM + Open WebUI auth)
- **SC-8**: Transmission confidentiality (TLS everywhere)
- **SC-28**: Protection of information at rest (EBS + S3 encryption)
