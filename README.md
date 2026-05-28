# telerivet-rest-api-usage-example

A minimal Python package demonstrating how to use the [Telerivet REST API Python client](https://github.com/Telerivet/telerivet-python-client) for common operations: querying messages, querying contacts, fetching a contact by ID, and bulk-upserting contacts.

## Why this exists

This code was extracted from a production batch job built for [Suvita](https://suvita.org/)'s maternal health SMS reminder programme in India. That pipeline does three main things:

1. **Enrol caregivers into Telerivet** — eligible caregiver contacts are pulled from Suvita's database and added to Telerivet so they can start receiving SMS reminders.
2. **Pull data back from Telerivet** — contacts, messages, delivery status, groups, and metadata are regularly fetched and stored in Suvita's database, so programme stats don't depend solely on Telerivet.
3. **Keep the database as the source of truth** — enrolments, messages sent, delivery outcomes, and failures are all tracked from one place. Old contacts and messages are also cleaned up from Telerivet over time, but their history remains in the database.

This package strips out all the domain-specific logic and keeps only the reusable Telerivet API patterns: config loading, cursor iteration with retry logic, label/group ID resolution, timestamp utilities, and contact upsert. If you're building anything on top of Telerivet in Python, this is a working reference.

## Installation

```bash
# Install from source (recommended)
pip install .

# Or install dependencies directly
pip install telerivet pandas
```

Requires Python 3.10+.

## Configuration

Copy the example config and fill in your credentials:

```bash
cp appconfig.ini.example appconfig.ini
```

`appconfig.ini` structure:

```ini
[telerivet_info]
api_key = your_api_key_here
project_id = your_project_id_here
```

The real `appconfig.ini` is gitignored. Never commit credentials.

Get your API key and project ID from the [Telerivet dashboard](https://telerivet.com/dashboard) under Settings → API.

## Usage

### Load config

```python
from telerivet_connector import load_config

config = load_config("appconfig.ini")
api_key = config["telerivet_info"]["api_key"]
project_id = config["telerivet_info"]["project_id"]
```

### Build a date range

```python
import datetime
from telerivet_connector import date_range_timestamps

yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
start_ts, end_ts = date_range_timestamps(yesterday, yesterday)
```

### Query messages

```python
from telerivet_connector import query_messages

df = query_messages(
    api_key=api_key,
    project_id=project_id,
    start_timestamp=start_ts,
    end_timestamp=end_ts,
    date_fields=["time_created", "time_sent", "time_updated"],
)
print(df.shape)
print(df.columns.tolist())
```

Returns a `pandas.DataFrame` where each row is one message. Label IDs are resolved to names in a `labels` column (comma-separated). Fields in `date_fields` are converted to IST datetimes. Contact `vars` are flattened into top-level columns.

### Query contacts

```python
from telerivet_connector import query_contacts

df = query_contacts(
    api_key=api_key,
    project_id=project_id,
    date_fields=["time_created", "last_message_time"],
)
print(df.shape)
```

Same pattern as `query_messages`. Group IDs are resolved to names in a `groups` column. Omit `start_timestamp` / `end_timestamp` to fetch all contacts.

### Get a contact by ID

```python
from telerivet_connector import get_contact_by_id

contact = get_contact_by_id(api_key, project_id, "CT00000000000000000000000000")
if contact is not None:
    print(contact.name, contact.phone_number)
```

Returns `None` (and logs the error) if the contact doesn't exist or the API call fails.

### Add or update contacts

```python
import pandas as pd
from telerivet_connector import add_contacts

data = pd.DataFrame([
    {"mobile": "+911234567890", "full_name": "Priya Sharma", "village": "Pune"},
    {"mobile": "+919876543210", "full_name": "Anita Verma",  "village": "Mumbai"},
])

col_mapping = {
    "mobile":    "phone_number",  # top-level field
    "full_name": "name",          # top-level field
    "village":   "village",       # goes into contact vars
}

added, skipped, errors = add_contacts(
    api_key=api_key,
    project_id=project_id,
    data_df=data,
    col_mapping=col_mapping,
    group_name="MyGroup",         # optional; creates group if it doesn't exist
)
print(f"added={added}, skipped={skipped}, errors={errors}")
```

Rows missing `phone_number` are skipped with a warning. Per-row exceptions are logged and counted in `errors` without stopping the loop.

See `sample/sample_usage.py` for a complete runnable example.

## API Reference

### `load_config(config_file)`

| Parameter | Type | Description |
|---|---|---|
| `config_file` | `str` | Path to the INI config file |

Returns `dict[str, dict[str, str]]` keyed by section name. Raises `ValueError` if the file is missing, `[telerivet_info]` is absent, or `api_key` is missing.

---

### `query_messages(api_key, project_id, start_timestamp, end_timestamp, date_fields)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Telerivet API key |
| `project_id` | `str` | required | Telerivet project ID |
| `start_timestamp` | `int \| None` | `None` | Unix timestamp — filter messages created after this time |
| `end_timestamp` | `int \| None` | `None` | Unix timestamp — filter messages created before this time |
| `date_fields` | `list[str] \| None` | `None` | Field names to convert from Unix timestamp to IST datetime |

Returns `pandas.DataFrame`.

---

### `query_contacts(api_key, project_id, start_timestamp, end_timestamp, date_fields)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Telerivet API key |
| `project_id` | `str` | required | Telerivet project ID |
| `start_timestamp` | `int \| None` | `None` | Unix timestamp — filter contacts created after this time |
| `end_timestamp` | `int \| None` | `None` | Unix timestamp — filter contacts created before this time |
| `date_fields` | `list[str] \| None` | `None` | Field names to convert from Unix timestamp to IST datetime |

Returns `pandas.DataFrame`.

---

### `get_contact_by_id(api_key, project_id, contact_id)`

| Parameter | Type | Description |
|---|---|---|
| `api_key` | `str` | Telerivet API key |
| `project_id` | `str` | Telerivet project ID |
| `contact_id` | `str` | Telerivet contact ID (e.g. `CT...`) |

Returns the Telerivet contact object, or `None` on failure.

---

### `add_contacts(api_key, project_id, data_df, col_mapping, group_name)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Telerivet API key |
| `project_id` | `str` | required | Telerivet project ID |
| `data_df` | `pandas.DataFrame` | required | Source data |
| `col_mapping` | `dict[str, str]` | required | Maps DataFrame column names to Telerivet field names |
| `group_name` | `str \| None` | `None` | If provided, adds each contact to this group (creates if needed) |

Returns `tuple[int, int, int]` — `(added, skipped, errors)`.

---

### Timestamp utilities

| Function | Signature | Description |
|---|---|---|
| `timestamp_to_datetime` | `(ts: int) -> datetime \| None` | Unix timestamp → IST datetime (UTC+5:30). Returns `None` for falsy input. |
| `day_start_timestamp` | `(date: datetime) -> int` | Midnight of the given date → Unix timestamp |
| `day_end_timestamp` | `(date: datetime) -> int` | 23:59:59 of the given date → Unix timestamp |
| `date_range_timestamps` | `(start: datetime, end: datetime) -> tuple[int, int]` | Full day range → `(start_ts, end_ts)` |

## Timezone note

All datetime conversions use IST (UTC+5:30) because the original pipeline was built for India. To use a different timezone, adjust the offset in `connector.py`:

```python
# In telerivet_connector/connector.py
_IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
```

Replace with your own offset, or use a library like `pytz` or `zoneinfo` for named timezones:

```python
from zoneinfo import ZoneInfo
# then in timestamp_to_datetime:
return utc_dt.astimezone(ZoneInfo("America/New_York"))
```

## License

MIT License — Copyright (c) 2026 Suvita
