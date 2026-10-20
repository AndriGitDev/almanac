---
title: Keep API errors predictable
type: decision
tags: [demo, api]
source: manual
project: api
certainty: 3
validity-context: fictional Almanac demonstration project
date: 2026-10-20T12:00
---

# Keep API errors predictable

Return a stable error code alongside a readable explanation. Avoid exposing internal exception details to clients.

## Related

- [[project-api]]
- [[request-tracing]]
- [[api-contract-tests]]
- [[clear-failure-states]]
