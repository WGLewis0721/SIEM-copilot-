# Palo Alto Networks Firewall — Security Rules SOP

**Version:** 2.1  
**Last Updated:** 2024-12  
**Owner:** Network Security Team  
**Classification:** INTERNAL USE ONLY

---

## Overview

This SOP covers standard operating procedures for managing Palo Alto Networks firewall security rules in the CNAP environment. All rule changes must follow the change management process.

---

## 1. Understanding Log Indices

Palo Alto logs are ingested into AWS OpenSearch under the index pattern `cwl-*`. Key log types:

| Log Type | Index Pattern | Description |
|----------|--------------|-------------|
| Traffic | `cwl-paloalto-traffic-*` | All allowed/denied traffic |
| Threat | `cwl-paloalto-threat-*` | IPS/antivirus detections |
| URL | `cwl-paloalto-url-*` | Web filtering events |
| Authentication | `cwl-paloalto-auth-*` | Admin login events |

---

## 2. Standard Security Rule Set

### 2.1 Zone-Based Rules

The firewall enforces the following zone hierarchy:

```
Internet (Untrust) → DMZ → Internal (Trust) → Restricted
```

| Rule Name | Source Zone | Destination | Action | Log Setting |
|-----------|------------|------------|--------|-------------|
| BLOCK-KNOWN-BAD | Any | Any | Drop | Log at Start + End |
| ALLOW-HTTPS-OUT | Trust | Untrust:443 | Allow | Log at End |
| ALLOW-DNS | Trust | DNS-Servers | Allow | Log at End |
| BLOCK-LATERAL-MOVEMENT | Trust | Trust | Drop | Log at Start + End |
| DEFAULT-DENY | Any | Any | Drop | Log at Start |

### 2.2 Critical Rule Categories

**High-Priority Blocks (log immediately):**
- Known threat intelligence feeds
- RFC 1918 spoofed external traffic
- Direct outbound traffic to non-approved countries

---

## 3. Responding to Blocked Connection Alerts

When the AI SIEM Copilot reports blocked connections:

### 3.1 Single Source, Multiple Destinations (Scanning Pattern)

**Indicators:**
- Same source IP blocking against >10 destination IPs within 15 minutes
- OpenSearch query: `action:DENY AND srcip:<IP>`

**Response Steps:**
1. Query OpenSearch for full context: `srcip:<IP> AND @timestamp:[now-1h TO now]`
2. Check threat intelligence for the source IP
3. If confirmed malicious: Add to dynamic block list
4. If internal IP: Investigate for malware/compromise
5. Document in incident ticket

### 3.2 Outbound Data Exfiltration Indicators

**Indicators:**
- High volume outbound traffic to unknown IPs
- Traffic to country codes not in approved list
- DNS queries to DGA-pattern domains

**Response Steps:**
1. Immediately capture packet data if DLP triggered
2. Isolate the source host from network
3. Preserve forensic evidence before remediation
4. Escalate to IR team

---

## 4. Rule Change Process

All firewall rule changes require:

1. **Change Request Ticket** with business justification
2. **Security Review** by Network Security team
3. **CAB Approval** for production changes
4. **Test in Dev/Staging** first
5. **Rollback Plan** documented before implementation
6. **Post-Change Verification** within 24 hours

---

## 5. Common Alert Types and Actions

| Alert | Severity | Initial Response |
|-------|----------|-----------------|
| `THREAT:botnet` | Critical | Immediate isolation + IR ticket |
| `THREAT:exploit` | High | Isolate + patch assessment |
| `THREAT:spyware` | High | EDR scan + network capture |
| `DENY:default-policy` | Medium | Review source/destination intent |
| `DENY:geo-block` | Low | Verify if expected traffic |
| `AUTH:admin-fail` | Medium | Check for brute force pattern |
| `AUTH:admin-success-from-new-ip` | High | Verify with admin out-of-band |

---

## 6. Escalation Criteria

**Immediate escalation to SOC Lead:**
- Threat severity = Critical
- Active data exfiltration in progress
- Compromise of firewall admin credentials
- Rule bypass detected
- More than 100 blocked connections from a single IP in 5 minutes
