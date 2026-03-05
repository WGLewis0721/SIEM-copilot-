# AppGate SDP — Authentication Flow Troubleshooting

**Version:** 2.1  
**Last Updated:** 2024-12  
**Owner:** Identity & Access Management Team

---

## Authentication Event Analysis

### Successful Authentication Log Pattern

```json
{
  "type": "auth",
  "result": "success",
  "user": "jane.smith@agency.gov",
  "mfa_method": "push",
  "device_posture_ok": true,
  "risk_score": 0.12,
  "geo_country": "US",
  "source_ip": "192.0.2.100"
}
```

### Failed Authentication Log Pattern

```json
{
  "type": "auth",
  "result": "failure",
  "reason": "invalid_credentials|mfa_timeout|device_posture_failed|certificate_invalid",
  "user": "jane.smith@agency.gov",
  "source_ip": "203.0.113.50",
  "geo_country": "CN",
  "risk_score": 0.92
}
```

---

## Failure Reason Reference

| Reason Code | Meaning | Common Cause | Resolution |
|-------------|---------|-------------|-----------|
| `invalid_credentials` | Wrong username/password | Forgotten password, credential theft | Password reset |
| `mfa_timeout` | MFA code expired | User didn't respond in time | Ask user to retry |
| `mfa_rejected` | User denied MFA push | Phishing attempt or accidental | Verify with user out-of-band |
| `device_posture_failed` | Device failed compliance check | Outdated OS, EDR issue | Fix device posture |
| `certificate_invalid` | Device cert expired/revoked | Old certificate | Re-enroll device |
| `policy_violation` | Access not permitted by policy | User lacks entitlement | Review policy assignment |
| `session_limit` | Max sessions reached | Legitimate concurrent use or session hijack | Review sessions |
| `account_suspended` | Account disabled | Admin action or automated suspension | IAM team review |

---

## Brute Force Detection

The CNAP SIEM Copilot monitors for:

1. **Password Spray** — One IP attempting many accounts:
   ```
   OpenSearch: type:auth AND result:failure AND source_ip:"<IP>" 
   Threshold: > 20 unique users in 10 minutes
   ```

2. **Credential Stuffing** — Many IPs targeting one account:
   ```
   OpenSearch: type:auth AND result:failure AND user:"<user>"
   Threshold: > 10 source IPs in 15 minutes
   ```

3. **MFA Bombing** — Repeated push notifications:
   ```
   OpenSearch: type:auth AND reason:mfa_rejected AND user:"<user>"
   Threshold: > 5 rejections in 10 minutes
   ```

---

## Session Management

### Active Session Monitoring

Use OpenSearch to monitor active sessions:
```json
{
  "query": { "term": { "type.keyword": "session" } },
  "aggs": {
    "sessions_by_user": {
      "terms": { "field": "user.keyword", "size": 20 }
    }
  }
}
```

### Force Session Termination

When a compromise is suspected:
1. AppGate Admin Console → Users → [username] → Sessions → Terminate All
2. Revoke device certificate in PKI
3. Reset password via out-of-band channel
4. Review audit logs for resource access during compromised period

---

## Integration with SIEM Analysis

When the RAG Agent detects AppGate anomalies, it references this document to:
- Identify the specific failure type
- Apply the correct response procedure
- Cite the specific policy violation
- Recommend escalation when thresholds are exceeded
