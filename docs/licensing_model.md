# Open Source Licensing Model Strategy

This document details the selected licensing model for the IMPACT project, ensuring compliance, community contribution, and commercial-use flexibility.

---

## 1. Chosen License: Apache-2.0
The IMPACT framework and its components are licensed under the **Apache License, Version 2.0**.

### Rationale
* **Permissive Nature**: Commercial entities can integrate IMPACT into their proprietary tooling, dashboard overlays, or CI pipelines without being forced to open-source their own systems (unlike copyleft licenses like GPL).
* **Patent Grant**: Provides explicit protection against patent infringement claims by contributors, which is a major requirement for enterprise adoption.
* **Modification and Distribution**: Allows users to modify code and distribute derivative works, provided they include proper attribution and preserve original notices.

---

## 2. Dependency License Auditing
All third-party libraries imported or declared as runtime dependencies in `pyproject.toml` are audited for compatibility.

### Compatibility Table

| Dependency | License | Type | Compatibility Status |
|------------|---------|------|----------------------|
| `networkx` | BSD-3-Clause | Runtime | **Compatible** (Permissive) |
| `javalang` | MIT | Optional | **Compatible** (Permissive) |
| `rdflib` | BSD-3-Clause | Optional | **Compatible** (Permissive) |
| `pyshacl` | Apache-2.0 | Optional | **Compatible** (Identical) |
| `psycopg2-binary` | LGPL-3.0 (with exceptions) | Optional | **Compatible** (Dynamically linked wrapper) |

---

## 3. Contribution Agreement
Contributors to IMPACT must agree to sign a Developer Certificate of Origin (DCO) on pull request submission, confirming they have the right to submit their contributions under the Apache-2.0 license.
