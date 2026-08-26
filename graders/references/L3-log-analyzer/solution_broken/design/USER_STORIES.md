# loganalyze -- User Stories

The baseline stories from REQUIREMENTS.md §1.3, restated and traced to the
functional requirements (`FR-n`) they justify (REQUIREMENTS.md §5.2 -- required
deliverable at this rung).

## Operator profiles

- **On-call SRE (triage).** Paged at 02:00; needs to know what broke and when,
  from a piped `zcat`/`tail` stream, without choking on a truncated tail.
- **Capacity reviewer (weekly).** Reviewing traffic shape; needs top-N paths and
  stable, machine-readable output for a dashboard job.

## Stories

| ID | Story | Justifies |
|----|-------|-----------|
| **US-1** | As an on-call SRE, I want to pipe a log slice into the tool, so that I can triage without copying files around. | FR-1 (stdin / `-` / `FILE`) |
| **US-2** | As an on-call SRE, I want the error rate and status breakdown for a specific time window, so that I can confirm when an incident started and stopped. | FR-5, FR-6, FR-7 |
| **US-3** | As an on-call SRE, I want a corrupt or truncated line skipped and *counted*, not aborting the run, so that a bad tail never costs me the whole report. | FR-3, FR-13, NFR-2 |
| **US-4** | As a capacity reviewer, I want the top N requested paths, so that I can see where load concentrates. | FR-4, FR-8 |
| **US-5** | As a capacity reviewer, I want machine-readable JSON with a stable, documented schema, so that I can script against it without rewriting my parser every release. | FR-9, §2.1 schema |
| **US-6** | As any operator, I want `--help` to tell me the grammar, exit codes, and the tool's ordering/timezone rules, so that I do not have to read the source. | FR-11, NFR-6 |
| **US-7** | As a script author, I want exit codes distinguishing "worked", "runtime failure", and "you called me wrong", so that my wrapper can branch correctly. | FR-10, FR-12, NFR-5 |
| **US-8** | As a capacity reviewer, I want to run this against a multi-gigabyte log on a small box, so that I do not need more RAM than the log has bytes. | NFR-1 (streaming, bounded memory) |

Every functional requirement `FR-1..FR-13` is traced by at least one story
above (FR-2 -- line parsing -- underpins US-2/US-4 and is exercised by every
story that reads entries).
