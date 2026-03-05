# CNAP AI SIEM Copilot — Cost Analysis

## Monthly AWS Cost Estimate (us-gov-west-1)

All prices are approximate. GovCloud prices are typically 10-15% higher than commercial regions.

### Option A: GPU Instance (Recommended for production)

| Resource | Type | Cost/Hour | Hours/Month | Monthly Cost |
|----------|------|-----------|-------------|-------------|
| EC2 g4dn.xlarge | On-Demand | $0.736 | 730 | ~$537 |
| EBS gp3 100GB | Storage | — | — | ~$8 |
| S3 Knowledge Base | ~1GB | — | — | ~$2 |
| S3 Backup (90 days) | ~5GB/month | — | — | ~$5 |
| CloudWatch Logs | ~1GB/month | — | — | ~$1 |
| SSM Session Manager | Data transfer | — | — | ~$0 |
| **Total** | | | | **~$553/mo** |

### Option B: CPU Instance (Development / lower budget)

| Resource | Type | Cost/Hour | Hours/Month | Monthly Cost |
|----------|------|-----------|-------------|-------------|
| EC2 t3.xlarge | On-Demand | $0.166 | 730 | ~$121 |
| EBS gp3 100GB | Storage | — | — | ~$8 |
| S3 (same as above) | — | — | — | ~$8 |
| **Total** | | | | **~$137/mo** |

---

## Cost Optimization Strategies

### 1. Reserved Instances / Savings Plans (Up to 40% savings)

```
GPU option with 1-year Reserved Instance: ~$322/mo (42% savings)
CPU option with 1-year Reserved Instance: ~$76/mo (44% savings)
```

### 2. Use Spot Instances (Up to 70% savings, best effort)

> ⚠️ Not recommended for production SIEM — spot instances can be interrupted

```
g4dn.xlarge spot price: ~$0.22/hr (historically)
Monthly spot estimate: ~$161/mo
```

### 3. Schedule On/Off

If the SIEM is only needed during business hours (8h/day, 5 days/week):

```
g4dn.xlarge: $0.736 × 174h = ~$128/mo
```

Use AWS Instance Scheduler or Lambda to automate this.

### 4. S3 Lifecycle Policies

Reports older than 90 days are automatically deleted (configured in Terraform).
Adjust `s3_backup_retention_days` variable to tune storage costs.

---

## Cost Monitoring

Set up AWS Budget alerts:
```bash
# Create a monthly budget alert at $600 (GPU option)
aws budgets create-budget \
  --account-id $ACCOUNT_ID \
  --budget '{"BudgetName":"CNAP-SIEM-Monthly","BudgetLimit":{"Amount":"600","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"team@agency.gov"}]}]'
```
