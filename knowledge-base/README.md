# CNAP AI SIEM Copilot — Knowledge Base

This directory contains security runbooks, SOPs, and playbooks that are uploaded to S3 and used by the RAG Agent to provide context in AI-generated security analyses.

## Structure

```
knowledge-base/
├── palo-alto/
│   ├── firewall-rules-sop.md      # Firewall rule management procedures
│   └── troubleshooting-guide.md   # Common issues and log field reference
├── appgate/
│   ├── sdp-architecture.md        # Zero-trust architecture overview
│   └── authentication-flow.md     # Auth troubleshooting and log analysis
└── incident-response/
    ├── playbook-template.md        # IR playbooks for common scenarios
    └── escalation-procedures.md    # Escalation matrix and contacts
```

## Adding New Documents

1. Add your document (`.md`, `.txt`, or `.pdf`) to the appropriate directory
2. Upload to S3: `./scripts/init-knowledge-base.sh $BUCKET_NAME`
3. The RAG agent will automatically index the new document on its next run

## Document Quality Guidelines

For best RAG retrieval quality:
- Use clear section headers
- Include specific field names and query examples
- Add log format examples with realistic field values
- Include escalation criteria and threshold values
- Keep documents focused on a single topic (one runbook per file)
- Recommended length: 500–3000 words per document
