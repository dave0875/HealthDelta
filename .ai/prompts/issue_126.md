---
Story
As a user,
I want grounded Q&A over my local records,
So that I can ask focused questions and see where answers came from.

Context / Why
Q&A is mission-critical but must be citation-grounded and safe against hallucination.

Acceptance Criteria
- Given a question over ingested records, when Q&A runs locally, then answer output includes source citations.
- Given low-evidence or ambiguous queries, when Q&A runs, then the system abstains with an explicit insufficiency message.
- Given safety constraints, when answers are rendered, then non-medical-advice disclaimer text is always present.
- Given regression fixtures, when CI runs, then answer format and citation presence are validated deterministically.

Out of Scope
- Open-ended internet search.
- Cloud-hosted retrieval.

Notes
- Retrieval/index strategy should align with Orin resource limits.
---
