---
title: Use idempotency keys for retryable writes
type: decision
tags: [demo, api]
source: manual
project: api
certainty: 3
validity-context: fictional Almanac demonstration project
date: 2026-10-20T12:00
---

# Use idempotency keys for retryable writes

In this example service, clients supply a stable key when retrying a payment request. Store the key and result together.

## Related

- [[project-api]]
- [[retry-budget]]
- [[request-tracing]]
- [[bounded-retries]]
