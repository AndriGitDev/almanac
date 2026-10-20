---
title: Give outbound requests a retry budget
type: pattern
tags: [demo, api]
source: manual
project: api
certainty: 3
validity-context: fictional Almanac demonstration project
date: 2026-10-20T12:00
---

# Give outbound requests a retry budget

A request has a fixed time budget shared by all attempts. Stop retrying when the remaining budget cannot cover another attempt.

## Related

- [[project-api]]
- [[api-error-format]]
- [[timeout-regression]]
- [[bounded-retries]]
