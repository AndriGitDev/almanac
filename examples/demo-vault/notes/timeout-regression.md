---
title: Cover upstream timeouts in tests
type: bugfix
tags: [demo, api]
source: manual
project: api
certainty: 3
validity-context: fictional Almanac demonstration project
date: 2026-10-20T12:00
---

# Cover upstream timeouts in tests

A fake upstream that never replies revealed a missing timeout in the example client. Keep that scenario in the regression suite.

## Related

- [[project-api]]
- [[api-contract-tests]]
- [[request-validation]]
