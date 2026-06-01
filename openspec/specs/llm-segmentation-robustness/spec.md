# llm-segmentation-robustness Specification

## Purpose
Make the vision analysis step provider-tolerant: silently retry undersegmenting responses (notably ollama llava-class models) with a strengthened prompt up to twice before falling back to whatever the LLM ultimately returns, so the standard pattern path doesn't break on weaker providers.

## Requirements

### Requirement: Vision analysis retries silently when key parts are missing
The backend SHALL provide `analyze_with_retry(img_bytes, prompt)` that wraps the existing `analyze_image` and re-issues the call up to two additional times if the response is missing core body parts. The minimum threshold for accepting a response is: at least 4 parts total, at least one part whose name case-insensitively contains `head`, and at least one part whose name contains `body` or `torso`. The retry SHALL append the strengthened instruction "IMPORTANT: include ALL visible body parts — head, body, BOTH arms, BOTH legs, ears, tail, etc. Do not omit symmetric parts." to the original prompt. The retry SHALL be silent (no user-facing message). After the maximum retries, the last response SHALL be returned regardless of whether the threshold was met.

#### Scenario: First response passes the threshold
- **WHEN** the first `analyze_image` call returns a response with Head, Body, and at least two limb-class parts
- **THEN** the response is returned immediately with no retry

#### Scenario: First response misses parts and retry succeeds
- **WHEN** the first response has fewer than 4 parts or is missing Head or Body
- **THEN** the call is re-issued with the strengthened prompt and the retried response is returned if it passes the threshold

#### Scenario: Maximum retries exceeded
- **WHEN** the response still fails the threshold after the second retry (3 total calls)
- **THEN** the last response is returned without raising, and `/generate` proceeds with whatever parts are present

#### Scenario: Retry is silent
- **WHEN** retry fires
- **THEN** no extra status message is added to the `/generate` HTTP response and no error is logged at error severity (info-level log is acceptable for debugging)

### Requirement: /generate uses the retry wrapper
The `/generate` endpoint's vision call SHALL use `analyze_with_retry`, not `analyze_image` directly, so the robustness applies to every standard pattern request.

#### Scenario: Endpoint wired through retry
- **WHEN** a `/generate` request is processed
- **THEN** the vision call goes through `analyze_with_retry` and benefits from the threshold check
