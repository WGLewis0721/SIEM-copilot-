# Palo Alto Networks Firewall — Troubleshooting Guide

**Version:** 1.8  
**Last Updated:** 2024-12  
**Owner:** Network Security Team

---

## Common Issues and Resolutions

### Issue 1: Missing Logs in OpenSearch

**Symptoms:**
- OpenSearch index `cwl-*` shows no data for the last hour
- RAG Agent reports 0 log events

**Troubleshooting Steps:**

1. **Verify CloudWatch Logs delivery:**
   ```bash
   aws logs describe-log-groups --log-group-name-prefix /paloalto --region us-gov-west-1
   aws logs describe-log-streams --log-group-name /paloalto/traffic --max-items 5
   ```

2. **Check OpenSearch subscription filter:**
   ```bash
   aws logs describe-subscription-filters --log-group-name /paloalto/traffic
   ```

3. **Verify firewall syslog configuration:**
   - Navigate to Device → Server Profiles → Syslog
   - Confirm CloudWatch Logs agent is receiving data

4. **Check OpenSearch cluster health:**
   ```
   GET /_cluster/health
   GET /_cat/indices/cwl-*
   ```

### Issue 2: High Number of Default-Deny Events

**Symptoms:**
- Large volume of `action:DENY` with `rule:default-deny` in logs
- AI analysis flagging as potential threat

**Assessment Process:**

1. Identify top source IPs:
   ```json
   GET /cwl-*/_search
   {
     "aggs": { "top_src": { "terms": { "field": "srcip.keyword", "size": 10 } } },
     "query": { "term": { "rule.keyword": "default-deny" } }
   }
   ```

2. Check if traffic is expected (legitimate misconfiguration) or malicious

3. If legitimate: Create appropriate allow rule following change process
4. If malicious: Add to threat feed and investigate source

### Issue 3: Firewall CPU > 90%

**Immediate Actions:**
1. Check for traffic flood: `action:ALLOW` volume spike
2. Check threat log for active attack signatures
3. Enable DoS protection profiles if not already active
4. Contact firewall admin team for capacity assessment

### Issue 4: Admin Authentication Failures

**5+ failures in 10 minutes = brute force indicator:**

1. Capture source IP and timestamp from auth logs
2. Check if IP is on threat feed
3. If internal: Check for compromised admin workstation
4. If external: Verify geo-blocking is active for admin interfaces
5. Consider temporary MFA enforcement

---

## Log Field Reference

| Field | Description | Example Values |
|-------|-------------|---------------|
| `action` | Traffic action | ALLOW, DENY, DROP |
| `srcip` | Source IP address | 192.168.1.100 |
| `dstip` | Destination IP | 10.0.0.1 |
| `dport` | Destination port | 443, 80, 22 |
| `proto` | Protocol | tcp, udp, icmp |
| `rule` | Matching rule name | allow-https-out |
| `app` | Application detected | ssl, web-browsing |
| `category` | URL category | business, malware |
| `severity` | Threat severity | critical, high, medium, low |
| `threat/content-name` | Threat signature name | Microsoft-SMB-Exploit |
| `@timestamp` | Event timestamp (UTC) | 2024-12-15T12:00:00Z |

---

## Contact Information

- **Network Security Team:** netsec@agency.gov
- **SOC Hotline:** ext. 7700 (24/7)
- **Palo Alto TAC:** 1-866-898-9087
- **Escalation:** soc-lead@agency.gov
