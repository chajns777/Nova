# Security Policy

## Supported Versions

Security fixes are applied to the `main` branch.

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |

## Reporting a Vulnerability

Please do **not** report security vulnerabilities in public GitHub issues.

Use **GitHub Security Advisories** (private vulnerability reporting) on this repository to report a potential issue. Include:

- A clear description of the vulnerability and affected component (e.g., self-learning skills validation, local web server, file/media ingestion, web research, or ChatSorter integration).
- Steps to reproduce or a proof of concept.
- Potential impact (such as arbitrary code execution, local file access, or unintended data exfiltration).

You can expect an initial acknowledgment within a few days, followed by status updates as the issue is investigated and patched.

## Security Considerations for Nova

Nova runs locally with Ollama and interacts with files, web content, and dynamically generated Python skills:

- **Self-learning skills:** Bypasses of the skill safety allow-list or validation checks that allow unintended system, file, or network access are in scope.
- **Local server & integrations:** Issues involving unauthorized local API access, path traversal, or unsafe handling of external responses (web pages, media parsers, or optional ChatSorter memory) are in scope.
- **Local storage:** Conversation history, memory (`memory.json`), and configuration (`config.json`) are stored locally; do not commit personal data or secrets to the repository.

## Out of Scope

- General LLM behavior, hallucinations, or prompt susceptibility inherent to the underlying Ollama model.
- Misconfiguration by the user (such as exposing the local server to untrusted networks or running untrusted third-party skills).
- Vulnerabilities belonging strictly to upstream dependencies unless triggered through an unsafe usage pattern in Nova.
