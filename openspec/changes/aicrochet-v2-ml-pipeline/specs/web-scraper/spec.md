## ADDED Requirements

### Requirement: Ravelry API scraper collects amigurumi patterns
The scraper SHALL query the Ravelry REST API for patterns with `pattern_type=amigurumi`, paginate through results, and persist raw responses (JSON + photo URLs) to local storage. It SHALL respect the Ravelry rate limit of 1 request per second using exponential backoff on 429 responses.

#### Scenario: Successful batch collection
- **WHEN** the scraper runs with valid Ravelry credentials
- **THEN** it downloads at least 100 pattern records per run and writes each to the local raw store before continuing

#### Scenario: Rate limit handled gracefully
- **WHEN** the Ravelry API returns HTTP 429
- **THEN** the scraper waits at least 2 seconds before retrying the same request, with delay doubling on each consecutive 429 up to 60 seconds

#### Scenario: Duplicate patterns skipped
- **WHEN** a pattern ID already exists in the raw store
- **THEN** the scraper skips downloading it and logs a skip message

---

### Requirement: Finished-object photo classifier filters images
The scraper SHALL run a binary classifier on each photo associated with a pattern before including the photo in a training pair. Only photos classified as "finished object" with confidence ≥ 0.85 SHALL be added to the training dataset.

#### Scenario: WIP photo rejected
- **WHEN** a photo shows a partially assembled doll with visible stuffing or incomplete parts
- **THEN** the classifier assigns class=`wip` and the photo is excluded from the training dataset

#### Scenario: Finished photo accepted
- **WHEN** a photo shows a complete assembled doll against a plain background
- **THEN** the classifier assigns class=`finished` with confidence ≥ 0.85 and the photo is included

#### Scenario: Low-confidence photo logged but excluded
- **WHEN** the classifier confidence is < 0.85 for either class
- **THEN** the photo is excluded and its URL is written to a review log for manual inspection

---

### Requirement: Scraper is resumable and idempotent
The scraper SHALL store a cursor (last processed page and pattern ID) so it can resume after interruption without re-downloading already-collected patterns.

#### Scenario: Resume after crash
- **WHEN** the scraper process is interrupted mid-run and restarted
- **THEN** it resumes from the last successfully stored cursor position without duplicating already-stored records

---

### Requirement: Secondary scraper for Amigurumi Today
The scraper SHALL include an HTML scraper for `amigurumitoday.com` free patterns as a secondary source. It SHALL extract the pattern text and main finished-object photo from each free pattern page.

#### Scenario: Pattern and photo extracted
- **WHEN** the scraper fetches a free pattern page from Amigurumi Today
- **THEN** it returns a record containing the full pattern text and at least one image URL
