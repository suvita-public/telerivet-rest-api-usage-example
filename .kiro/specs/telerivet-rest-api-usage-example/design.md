# Design Document

## Overview

`telerivet-rest-api-usage-example` is a minimal, self-contained Python package that demonstrates how to use the [Telerivet REST API Python client](https://github.com/Telerivet/telerivet-python-client) for common operations: querying messages, querying contacts, fetching a contact by ID, and bulk-upserting contacts. It is extracted from a production SMS reminder pipeline built for Suvita's maternal health program in India.

The library has no database dependency. All internal pipeline logic (SQLAlchemy ORM, SurveyCTO integration, fuzzy name matching, message processing) is excluded. What remains is the pure Telerivet API interaction layer, cleaned up and made reusable.

---

## Architecture

```
telerivet-rest-api-usage-example/
├── telerivet_connector/
│   ├── __init__.py          # re-exports public API
│   └── connector.py         # all implementation
├── sample/
│   └── sample_usage.py      # runnable examples
├── appconfig.ini.example    # template config (real appconfig.ini is gitignored)
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

There is intentionally no sub-module split. All logic lives in `connector.py` — the surface area is small enough that splitting would add navigation overhead without benefit.

### Dependency graph

```
sample_usage.py
    └── telerivet_connector
            └── connector.py
                    ├── telerivet          (PyPI: telerivet)
                    ├── pandas             (PyPI: pandas)
                    ├── configparser       (stdlib)
                    ├── logging            (stdlib)
                    └── datetime           (stdlib)
```

No third-party dependencies beyond `telerivet` and `pandas`.

---

## Components and Interfaces

### `telerivet_connector/connector.py`

All public functions are module-level. No class is needed — the Telerivet client is instantiated per-call, which matches the original pipeline's pattern and keeps functions independently testable.

#### `load_config(config_file: str) -> dict`

Reads `appconfig.ini` using `configparser`. Returns a flat dict-of-dicts keyed by section name. Raises `ValueError` if the file is missing or `[telerivet_info]` section is absent.

```python
config = load_config("appconfig.ini")
api_key = config["telerivet_info"]["api_key"]
```

#### `query_messages(api_key, project_id, start_timestamp=None, end_timestamp=None, date_fields=None) -> pd.DataFrame`

Wraps `project.queryMessages()`. Resolves label IDs → names via `project.queryLabels()`. Iterates the cursor via the internal `_iter_cursor()` helper. Returns a DataFrame where each row is one message, with `vars` fields flattened into columns and a `labels` column containing comma-joined label names.

#### `query_contacts(api_key, project_id, start_timestamp=None, end_timestamp=None, date_fields=None) -> pd.DataFrame`

Wraps `project.queryContacts()`. Resolves group IDs → names via `project.queryGroups()`. Same cursor iteration pattern as `query_messages`. Returns a DataFrame with `vars` flattened and a `groups` column.

#### `get_contact_by_id(api_key, project_id, contact_id) -> telerivet.Contact | None`

Wraps `project.getContactById()`. Returns the contact object on success, `None` on any exception (preserving the original pipeline's fault-tolerant behaviour for orphaned contact lookups).

#### `add_contacts(api_key, project_id, data_df, col_mapping, group_name=None) -> tuple[int, int, int]`

Iterates `data_df` rows. For each row, applies `col_mapping` (source column → target field) to build a contact dict. Calls `project.getOrCreateContact()`. Optionally adds to a group. Returns `(added, skipped, errors)`.

#### Timestamp utilities (module-level)

| Function | Signature | Description |
|---|---|---|
| `timestamp_to_datetime` | `(ts: int) -> datetime \| None` | Unix ts → IST datetime (UTC+5:30) |
| `day_start_timestamp` | `(date: datetime) -> int` | midnight of date → Unix ts |
| `day_end_timestamp` | `(date: datetime) -> int` | 23:59:59 of date → Unix ts |
| `date_range_timestamps` | `(start: datetime, end: datetime) -> tuple[int, int]` | full day range → (start_ts, end_ts) |

#### Internal helper: `_iter_cursor(cursor, key_field, lookup_dict, resolved_field_name, date_fields)`

This is the core cursor iteration logic extracted from `getDatafromCursor()` in the original `telerivetUtil.py`. It:

1. Iterates the Telerivet cursor, extracting the `_data` attribute from each object (the raw API response dict).
2. For the `key_field` (e.g. `label_ids` or `group_ids`), resolves each ID via `lookup_dict` and joins as a comma-separated string into `resolved_field_name`.
3. For any field in `date_fields`, converts the Unix timestamp value to an IST datetime.
4. Flattens `vars` dict directly into the row.
5. Retries up to 3 times on `ConnectionError` with 30s sleep between attempts.
6. Returns a `list[dict]`.

This is private (prefixed `_`) because callers should use `query_messages` / `query_contacts` instead.

### `telerivet_connector/__init__.py`

Re-exports the public API so callers can do:

```python
from telerivet_connector import load_config, query_messages, query_contacts, get_contact_by_id, add_contacts
from telerivet_connector import timestamp_to_datetime, day_start_timestamp, day_end_timestamp, date_range_timestamps
```

### `sample/sample_usage.py`

A runnable script demonstrating all public functions. Uses `load_config("appconfig.ini")` to read credentials. Shows:

1. Loading config and building timestamps for a date range
2. Querying messages with a date range
3. Querying all contacts
4. Fetching a single contact by ID
5. Adding/updating contacts from a DataFrame

---

## Data Models

No custom data classes. The library works with:

- `dict` — intermediate row representation during cursor iteration
- `pandas.DataFrame` — output of `query_messages` and `query_contacts`
- `telerivet.Contact` — returned by `get_contact_by_id`
- `tuple[int, int, int]` — `(added, skipped, errors)` from `add_contacts`

### DataFrame column conventions (from original pipeline)

For messages:
- `labels` — comma-joined resolved label names (was `label_ids` in raw API)
- `vars.*` — all contact custom variables flattened to top-level columns
- Date fields (e.g. `time_created`, `time_updated`, `time_sent`) — converted to IST datetime

For contacts:
- `groups` — comma-joined resolved group names (was `group_ids` in raw API)
- `vars.*` — all contact custom variables flattened to top-level columns
- Date fields (e.g. `time_created`, `last_message_time`) — converted to IST datetime

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `appconfig.ini` missing | `load_config` raises `ValueError("Config file not found: <path>")` |
| `[telerivet_info]` section missing | `load_config` raises `ValueError("Missing [telerivet_info] section in <path>")` |
| `api_key` missing from config | `load_config` raises `ValueError("Missing api_key in [telerivet_info]")` |
| `ConnectionError` during cursor iteration | Retry up to 3 times, 30s sleep; raise after 3rd failure |
| Any other exception during cursor iteration | Raise immediately with original traceback |
| Contact not found in `get_contact_by_id` | Log at ERROR, return `None` |
| Missing `phone_number` in `add_contacts` row | Log warning, skip row, increment `skipped` |
| Exception for a single row in `add_contacts` | Log error, increment `errors`, continue |

The original pipeline used a `finally: return message_list` pattern in `getDatafromCursor` which silently swallowed exceptions. This design corrects that — the `finally` block is removed and exceptions propagate properly, except in `get_contact_by_id` where returning `None` is the documented contract.

---

## Testing Strategy

No test framework is set up in this library (it is an example/reference implementation). The `sample/sample_usage.py` serves as a manual integration test. Users who want to add tests can use `pytest` with `unittest.mock.patch` to mock the `telerivet.API` object.

Key things worth testing if extended:
- `load_config` with missing file, missing section, missing key
- `_iter_cursor` with a mock cursor that raises `ConnectionError` on first call
- `timestamp_to_datetime` with known values
- `add_contacts` with rows missing phone numbers

---

## Design Decisions

**Why no class?** The original code was procedural. Wrapping in a class would add boilerplate (`__init__`, `self.api_key`, etc.) without benefit for an example library. Functions are easier to read and copy-paste.

**Why keep pandas?** The original pipeline returned DataFrames and the column-flattening logic (vars, date conversion) is tightly coupled to DataFrame construction. Removing pandas would require a different return type and lose the column-naming conventions that are part of the documented knowledge.

**Why IST (UTC+5:30)?** The original pipeline was built for India. The `timestamp_to_datetime` function preserves this. Users in other timezones can adjust the offset or use `datetime.timezone` — this is documented in the README.

**Why `_iter_cursor` is private?** It's an implementation detail of how the Telerivet Python client exposes raw data via `_data` attribute introspection. This is an undocumented internal of the client library and may change. Callers should use the higher-level functions.

**appconfig.ini.example** is committed; the real `appconfig.ini` is gitignored. This is the standard pattern for config-with-secrets.
