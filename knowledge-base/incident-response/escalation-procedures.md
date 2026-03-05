# Escalation Procedures — CNAP Security Operations

**Version:** 2.5  
**Last Updated:** 2024-12  
**Owner:** SOC Director

---

## Escalation Philosophy

**Always escalate too early rather than too late.** The cost of a false positive escalation is far lower than a missed incident.

---

## Escalation Tiers

### Tier 1: Analyst On-Duty

**Handles:** P4 incidents, initial triage for P3
- Document all findings in SIEM
- Attempt automated remediation
- Escalate to Tier 2 if unable to resolve in 30 minutes

### Tier 2: Senior Analyst / SOC Lead

**Handles:** P2-P3 incidents, Tier 1 escalations
- Coordinate with system owners
- Authorize containment actions
- Escalate to Tier 3 for P1

### Tier 3: CISO / Incident Response Team

**Handles:** P1 incidents, confirmed breaches, executive notifications
- Full IR team activation
- Legal/compliance coordination
- Executive briefings

---

## Automatic Escalation Triggers

The CNAP AI SIEM Copilot is configured to flag these as immediate escalations:

| Condition | Escalation Level | Reason |
|-----------|-----------------|--------|
| Ransomware signature detected | Tier 3 (immediate) | Business continuity risk |
| Firewall admin credentials used from external IP | Tier 3 (immediate) | Infrastructure compromise |
| Data exfiltration > 1GB to external IP | Tier 2 (< 15 min) | Data breach indicator |
| Failed authentication > 100 attempts | Tier 2 (< 30 min) | Active attack |
| AppGate risk score > 0.9 | Tier 2 (< 30 min) | High-confidence compromise |
| Zero-day exploit signature | Tier 3 (immediate) | Novel threat |
| 3+ simultaneous high alerts | Tier 2 (< 15 min) | Coordinated attack |

---

## Contact Information

**All contacts are maintained in the SOC playbook system — this document contains placeholder formats only.**

| Role | Tier | Contact Method |
|------|------|---------------|
| Analyst On-Duty | 1 | SOC chat channel |
| SOC Lead | 2 | SOC phone bridge |
| CISO | 3 | Phone (24/7) |
| Legal | 3 | Emergency legal line |
| FBI Cyber Division | External | Incident coordination |
| CISA | External | Federal reporting |

---

## Communication Templates

### Initial Notification (P1/P2)

```
Subject: [P{SEVERITY}] Security Incident — {BRIEF DESCRIPTION} — {TIMESTAMP}

Incident ID: {TICKET_ID}
Severity: P{N} — {SEVERITY_NAME}
Detected By: CNAP AI SIEM Copilot / {ANALYST}
Systems Affected: {SYSTEMS}
Status: ACTIVE — INVESTIGATING

Current Actions:
- {ACTION 1}
- {ACTION 2}

Next Update: {TIME} or when status changes

Contact: {ANALYST} via SOC bridge
```

### All-Clear Notification

```
Subject: [RESOLVED] Security Incident — {TICKET_ID} — {BRIEF DESCRIPTION}

Incident ID: {TICKET_ID}
Resolution Time: {DURATION}
Root Cause: {SUMMARY}
Actions Taken: {SUMMARY}
Status: RESOLVED — monitoring in place

Post-Incident Review: Scheduled for {DATE}
```
