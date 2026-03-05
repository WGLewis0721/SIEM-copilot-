# Incident Response Playbook — CNAP Environment

**Version:** 4.0  
**Last Updated:** 2024-12  
**Owner:** Security Operations Center  
**Classification:** INTERNAL USE ONLY

---

## Overview

This playbook provides step-by-step procedures for responding to security incidents detected in the CNAP environment. The AI SIEM Copilot references this document to provide actionable guidance.

---

## Incident Severity Levels

| Severity | Response Time | Examples |
|----------|--------------|---------|
| P1 – Critical | 15 minutes | Active data exfiltration, ransomware, total firewall bypass |
| P2 – High | 1 hour | Confirmed compromise, active lateral movement, admin credential theft |
| P3 – Medium | 4 hours | Failed compromise attempt, policy violation, anomalous access |
| P4 – Low | 24 hours | Configuration drift, minor policy violation |

---

## Playbook 1: Malware/Ransomware Detection

### Trigger Conditions
- Threat log: `threat/content-name` matches ransomware signature
- EDR alert: File encryption behavior detected
- OpenSearch: Large volume of `SMB` or `RDP` lateral movement

### Response Steps

**Phase 1: Containment (0-15 minutes)**
1. [ ] Isolate affected host from network immediately
   - If AppGate: Terminate all sessions for the device
   - If physical: Disable switch port
2. [ ] Preserve forensic memory image before shutdown
3. [ ] Notify SOC Lead (P1 escalation)
4. [ ] Start incident ticket with timestamp

**Phase 2: Investigation (15-60 minutes)**
1. [ ] Query OpenSearch for lateral movement from infected host:
   ```
   srcip:<infected_ip> AND action:ALLOW AND @timestamp:[now-24h TO now]
   ```
2. [ ] Identify all accessed resources
3. [ ] Check for C2 communication (Palo Alto threat logs)
4. [ ] Determine initial infection vector (email, USB, malicious download)

**Phase 3: Eradication**
1. [ ] Reimage affected system from known-good baseline
2. [ ] Change all credentials that may have been accessed
3. [ ] Patch the exploited vulnerability if applicable
4. [ ] Update threat intelligence feeds with IOCs

**Phase 4: Recovery**
1. [ ] Restore from verified clean backup
2. [ ] Verify system integrity before reconnecting
3. [ ] Monitor for 72 hours post-recovery

---

## Playbook 2: Unauthorized Access (Privilege Escalation)

### Trigger Conditions
- Admin access from unusual IP/time
- AppGate: `risk_score > 0.8` with successful authentication
- Palo Alto: Admin interface access from untrusted zone

### Response Steps

**Phase 1: Verification (0-30 minutes)**
1. [ ] Verify with the user out-of-band (phone, not email)
2. [ ] Query all actions taken by the suspicious session
3. [ ] Review what data/systems were accessed

**Phase 2: Containment**
1. [ ] If confirmed unauthorized: Terminate all active sessions
2. [ ] Revoke credentials and certificates
3. [ ] Enable enhanced logging on affected accounts

**Phase 3: Investigation**
1. [ ] Determine how credentials were obtained
2. [ ] Review for data exfiltration (large file downloads, unusual API calls)
3. [ ] Check for backdoor/persistence mechanisms

---

## Playbook 3: DDoS / Traffic Flood

### Trigger Conditions
- Palo Alto: > 10,000 connections/second from single source
- OpenSearch: Spike in `action:DENY` volume

### Response Steps
1. [ ] Enable rate limiting on affected interface
2. [ ] Activate geographic blocking for source countries
3. [ ] Contact ISP/upstream provider for scrubbing
4. [ ] Monitor business-critical services for availability

---

## Escalation Matrix

| Situation | Escalate To | Method |
|-----------|------------|--------|
| Active P1 incident | SOC Lead + CISO | Phone (direct) |
| Data breach confirmed | Legal + Privacy Officer | Phone (immediate) |
| Insider threat suspected | HR + Legal + CISO | In-person only |
| Media/press inquiries | Communications Officer | Email + follow-up call |
| Law enforcement required | General Counsel | Legal coordination |

---

## Post-Incident Requirements

All P1/P2 incidents require:
- [ ] Timeline reconstruction within 24 hours
- [ ] Root cause analysis within 72 hours  
- [ ] Lessons learned document within 2 weeks
- [ ] Control improvements within 30 days
