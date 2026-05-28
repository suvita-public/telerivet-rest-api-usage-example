# Requirements Document

## Introduction

This project extracts and packages the Telerivet REST API integration code from an existing internal SMS reminder pipeline (built for Suvita's maternal health program) into a standalone, open-source Python library called `telerivet-rest-api-usage-example`. The goal is to demonstrate how to use the [Telerivet REST API Python client](https://github.com/Telerivet/telerivet-python-client) for querying messages, querying contacts, fetching a contact by ID, and adding/updating contacts — with clean config loading, proper logging, retry logic, and timestamp utilities. All domain-specific database and pipeline logic is excluded; only the Telerivet API interaction patterns are preserved.

## Glossary

- **Telerivet**: A cloud messaging platform for SMS, voice, and other channels, accessible via REST API.
- **Telerivet Python client**: The official `telerivet` PyPI package used to interact with the Telerivet REST API.
- **Connector**: The `telerivet_connector/connector.py` module that wraps Telerivet API calls.
- **Config file**: An `appconfig.ini` file read via `configparser`, containing `[telerivet_info]` with `api_key` and project ID mappings.
- **Cursor**: A Telerivet API lazy iterator returned by `queryMessages()` or `queryContacts()`, which pages through results automatically.
- **Label**: A Telerivet message tag; label IDs are resolved to human-readable names via `queryLabels()`.
- **Group**: A Telerivet contact grouping; group IDs are resolved to names via `queryGroups()`.
- **Timestamp**: A Unix epoch integer used by the Telerivet API for date range filtering.
- **IST**: Indian Standard Time (UTC+5:30), used for timestamp-to-datetime conversion in the original pipeline.
- **vars**: Telerivet contact custom variables, stored as a flat key-value dict on each contact object.
- **date_fields**: A semicolon-separated list of field names whose values should be converted from Unix timestamps to datetime objects during cursor iteration.
- **getOrCreateContact**: Telerivet API method that upserts a contact by phone number.

---

## Requirements

### Requirement 1: Package structure

**User Story:** As a developer, I want a properly structured Python package, so that I can install it and import it cleanly.

#### Acceptance Criteria

1. THE system SHALL provide a `telerivet_connector/` directory containing `__init__.py` and `connector.py`.
2. THE system SHALL provide a `pyproject.toml` with `name = "telerivet-rest-api-usage-example"`, `version = "1.0.0"`, and dependencies `telerivet` and `pandas`.
3. THE system SHALL provide a `sample/sample_usage.py` demonstrating all public functions.
4. THE system SHALL provide a `README.md` with a "Why this exists" section, full usage instructions, and API reference.
5. THE system SHALL provide a `LICENSE` file with MIT License, copyright `(c) 2026 Suvita`.
6. THE system SHALL provide a `.gitignore` that excludes `appconfig.ini` and the original source pipeline files.

---

### Requirement 2: Configuration loading

**User Story:** As a developer, I want config loaded from a file rather than hardcoded, so that I can use my own API key and project IDs without modifying source code.

#### Acceptance Criteria

1. THE Connector SHALL expose a `load_config(config_file)` function that reads `appconfig.ini` using `configparser` and returns a config dict.
2. WHEN `load_config` is called with a path to a valid `appconfig.ini`, THE Connector SHALL return a dict containing at minimum the `telerivet_info` section with `api_key`.
3. IF `config_file` does not exist or is missing the `[telerivet_info]` section, THEN THE Connector SHALL raise a `ValueError` with a descriptive message identifying the missing section or file.
4. THE Connector SHALL NOT hardcode any API keys, project IDs, or credentials anywhere in source code.

---

### Requirement 3: Query messages

**User Story:** As a developer, I want to fetch messages from a Telerivet project with optional date range filtering, so that I can analyse outbound and inbound SMS activity.

#### Acceptance Criteria

1. THE Connector SHALL expose a `query_messages(api_key, project_id, start_timestamp, end_timestamp, date_fields)` function that returns a `pandas.DataFrame`.
2. WHEN both `start_timestamp` and `end_timestamp` are provided, THE Connector SHALL pass `time_created={'min': start_timestamp, 'max': end_timestamp}` to the Telerivet cursor.
3. WHEN only `start_timestamp` is provided, THE Connector SHALL pass `time_created={'min': start_timestamp}`.
4. WHEN only `end_timestamp` is provided, THE Connector SHALL pass `time_created={'max': end_timestamp}`.
5. WHEN neither timestamp is provided, THE Connector SHALL call `queryMessages()` with no filter.
6. THE Connector SHALL resolve label IDs to label names by calling `project.queryLabels()` and storing results in a lookup dict, then joining resolved names as a comma-separated string in a `labels` column.
7. THE Connector SHALL convert any field listed in `date_fields` from a Unix timestamp to a `datetime` object (UTC+5:30 / IST) during cursor iteration.
8. THE Connector SHALL flatten `vars` fields from each message directly into the row dict.
9. WHEN a `ConnectionError` occurs during cursor iteration, THE Connector SHALL retry up to 3 times with a 30-second wait between attempts, then raise the exception if all retries are exhausted.
10. IF any other exception occurs during cursor iteration, THEN THE Connector SHALL raise it with a descriptive message.

---

### Requirement 4: Query contacts

**User Story:** As a developer, I want to fetch contacts from a Telerivet project with optional date range filtering, so that I can inspect enrolled contacts and their custom variables.

#### Acceptance Criteria

1. THE Connector SHALL expose a `query_contacts(api_key, project_id, start_timestamp, end_timestamp, date_fields)` function that returns a `pandas.DataFrame`.
2. WHEN both `start_timestamp` and `end_timestamp` are provided, THE Connector SHALL pass `time_created={'min': start_timestamp, 'max': end_timestamp}` to the contacts cursor.
3. WHEN only `start_timestamp` is provided, THE Connector SHALL pass `time_created={'min': start_timestamp}`.
4. WHEN only `end_timestamp` is provided, THE Connector SHALL pass `time_created={'max': end_timestamp}`.
5. WHEN neither timestamp is provided, THE Connector SHALL call `queryContacts()` with no filter.
6. THE Connector SHALL resolve group IDs to group names by calling `project.queryGroups()` and storing results in a lookup dict, then joining resolved names as a comma-separated string in a `groups` column.
7. THE Connector SHALL convert any field listed in `date_fields` from a Unix timestamp to a `datetime` object (UTC+5:30 / IST) during cursor iteration.
8. THE Connector SHALL flatten `vars` fields from each contact directly into the row dict.

---

### Requirement 5: Get contact by ID

**User Story:** As a developer, I want to fetch a single contact by their Telerivet contact ID, so that I can look up contact details on demand.

#### Acceptance Criteria

1. THE Connector SHALL expose a `get_contact_by_id(api_key, project_id, contact_id)` function.
2. WHEN the contact exists, THE Connector SHALL return the Telerivet contact object.
3. IF the contact does not exist or an exception occurs, THEN THE Connector SHALL log the error and return `None` rather than raising, preserving the original pipeline's fault-tolerant behaviour.

---

### Requirement 6: Add or update contacts

**User Story:** As a developer, I want to upsert contacts into a Telerivet project from a DataFrame, so that I can bulk-enrol participants without writing boilerplate API loop code.

#### Acceptance Criteria

1. THE Connector SHALL expose an `add_contacts(api_key, project_id, data_df, col_mapping, group_name)` function.
2. THE Connector SHALL iterate over each row in `data_df`, map source columns to Telerivet fields using `col_mapping` (a dict of `source_col → target_field`), and call `project.getOrCreateContact()`.
3. THE Connector SHALL treat `phone_number` and `name` as top-level contact fields; all other mapped targets SHALL be passed as contact `vars`.
4. WHEN a row is missing a `phone_number` value, THE Connector SHALL skip that row and log a warning.
5. WHEN `group_name` is provided, THE Connector SHALL call `project.getOrCreateGroup(group_name)` once and add each successfully upserted contact to that group.
6. THE Connector SHALL return a tuple `(added, skipped, errors)` with counts for each outcome.
7. IF an exception occurs for a single row, THEN THE Connector SHALL log the error, increment the error count, and continue processing remaining rows.

---

### Requirement 7: Timestamp utilities

**User Story:** As a developer, I want helper functions for converting between dates and Unix timestamps, so that I can build date range filters without reimplementing the conversion logic.

#### Acceptance Criteria

1. THE Connector SHALL expose a `timestamp_to_datetime(ts)` function that converts a Unix timestamp integer to a `datetime` object adjusted to IST (UTC+5:30).
2. THE Connector SHALL expose a `day_start_timestamp(date)` function that returns the Unix timestamp for midnight at the start of the given date.
3. THE Connector SHALL expose a `day_end_timestamp(date)` function that returns the Unix timestamp for 23:59:59 at the end of the given date.
4. THE Connector SHALL expose a `date_range_timestamps(start_date, end_date)` function that returns a tuple `(start_timestamp, end_timestamp)` covering the full day range from start to end inclusive.
5. WHEN any timestamp utility receives `None` or a falsy value, THE Connector SHALL return `None` rather than raising an exception.

---

### Requirement 8: Logging

**User Story:** As a developer, I want the library to use standard Python logging rather than a passed-in logger, so that I can control log output through my own logging configuration.

#### Acceptance Criteria

1. THE Connector SHALL use `logging.getLogger(__name__)` internally and SHALL NOT accept a `logger` parameter in any public function.
2. THE Connector SHALL log informational messages (record counts, retry attempts) at `INFO` level.
3. THE Connector SHALL log debug-level details (per-record processing) at `DEBUG` level.
4. THE Connector SHALL log errors with `exc_info=True` at `ERROR` level.
5. THE Connector SHALL NOT configure any log handlers, formatters, or file outputs — that responsibility belongs to the calling application.
