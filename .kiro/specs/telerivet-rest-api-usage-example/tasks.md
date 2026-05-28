# Implementation Plan

- [x] 1. Create package scaffold and project files





  - Create `telerivet_connector/__init__.py` (empty placeholder)
  - Create `pyproject.toml` with name, version, and dependencies
  - Create `LICENSE` with MIT License, copyright (c) 2026 Suvita
  - Create `.gitignore` excluding `appconfig.ini`, `*.bak`, `*.pyc`, `__pycache__/`, and original source files
  - Create `appconfig.ini.example` with placeholder values showing the required structure
  - _Requirements: 1.1, 1.2, 1.5, 1.6_

- [x] 2. Implement `connector.py` — config loading and timestamp utilities





  - [x] 2.1 Implement `load_config(config_file)` using `configparser`


    - Read `appconfig.ini`, return dict-of-dicts keyed by section
    - Raise `ValueError` with descriptive message if file missing, `[telerivet_info]` absent, or `api_key` missing
    - Use `logging.getLogger(__name__)` — no logger parameter
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 8.1_
  - [x] 2.2 Implement timestamp utility functions


    - `timestamp_to_datetime(ts)` — Unix int → IST datetime (UTC+5:30), returns None for falsy input
    - `day_start_timestamp(date)` — midnight of date → Unix int
    - `day_end_timestamp(date)` — 23:59:59 of date → Unix int
    - `date_range_timestamps(start_date, end_date)` — returns (start_ts, end_ts) tuple
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3. Implement `connector.py` — cursor iteration and query functions





  - [x] 3.1 Implement `_iter_cursor(cursor, key_field, lookup_dict, resolved_field_name, date_fields)`


    - Extract `_data` attribute from each Telerivet object
    - Resolve IDs in `key_field` via `lookup_dict`, join as comma-separated string into `resolved_field_name`
    - Convert fields in `date_fields` from Unix timestamp to IST datetime
    - Flatten `vars` dict directly into the row dict
    - Retry up to 3 times on `ConnectionError` with 30s sleep; raise after exhausting retries
    - Raise immediately on any other exception (fix the original `finally: return` bug)
    - _Requirements: 3.7, 3.8, 3.9, 3.10, 4.7, 4.8_
  - [x] 3.2 Implement `query_messages(api_key, project_id, start_timestamp, end_timestamp, date_fields)`

    - Build timestamp filter dict based on which timestamps are provided (all 4 combinations)
    - Call `project.queryLabels()` to build label ID → name lookup dict
    - Call `_iter_cursor` with `key_field="label_ids"`, `resolved_field_name="labels"`
    - Return `pd.DataFrame` from the result list
    - Log cursor count at INFO level
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 8.2_
  - [x] 3.3 Implement `query_contacts(api_key, project_id, start_timestamp, end_timestamp, date_fields)`

    - Same timestamp filter pattern as `query_messages`
    - Call `project.queryGroups()` to build group ID → name lookup dict
    - Call `_iter_cursor` with `key_field="group_ids"`, `resolved_field_name="groups"`
    - Return `pd.DataFrame` from the result list
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 4. Implement `connector.py` — contact management functions





  - [x] 4.1 Implement `get_contact_by_id(api_key, project_id, contact_id)`


    - Call `project.getContactById(contact_id)`
    - Return contact object on success
    - On any exception: log at ERROR with `exc_info=True`, return `None`
    - _Requirements: 5.1, 5.2, 5.3, 8.4_
  - [x] 4.2 Implement `add_contacts(api_key, project_id, data_df, col_mapping, group_name=None)`


    - Iterate `data_df` rows; apply `col_mapping` to build per-row contact dict
    - Split `phone_number` and `name` as top-level fields; all other mapped targets go into `vars`
    - Skip rows missing `phone_number` with a WARNING log, increment `skipped`
    - Call `project.getOrCreateContact()` for each valid row
    - If `group_name` provided, call `project.getOrCreateGroup()` once and `contact.addToGroup()` per contact
    - On per-row exception: log ERROR, increment `errors`, continue
    - Return `(added, skipped, errors)` tuple
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 8.3_

- [x] 5. Wire up `__init__.py` and write `sample/sample_usage.py`





  - [x] 5.1 Update `telerivet_connector/__init__.py` to re-export all public functions


    - Export: `load_config`, `query_messages`, `query_contacts`, `get_contact_by_id`, `add_contacts`
    - Export: `timestamp_to_datetime`, `day_start_timestamp`, `day_end_timestamp`, `date_range_timestamps`
    - _Requirements: 1.1_
  - [x] 5.2 Write `sample/sample_usage.py`


    - Show `load_config("appconfig.ini")` to read credentials
    - Show `date_range_timestamps` to build a date range for yesterday
    - Show `query_messages` with a date range, print DataFrame shape
    - Show `query_contacts` with no date filter, print DataFrame shape
    - Show `get_contact_by_id` with a placeholder contact ID
    - Show `add_contacts` from a small hardcoded DataFrame with `col_mapping`
    - All examples wrapped in `if __name__ == "__main__"` with try/except
    - _Requirements: 1.3_

- [x] 6. Write `README.md` and delete production pipeline files





  - [x] 6.1 Write `README.md`


    - Title: `telerivet-rest-api-usage-example`
    - "Why this exists" section explaining the Suvita SMS pipeline origin
    - Installation instructions (`pip install .` or `pip install telerivet pandas`)
    - Configuration section showing `appconfig.ini` structure
    - Full usage instructions for each function with code examples
    - API reference table for all public functions and their parameters
    - Note on IST timezone and how to adjust
    - _Requirements: 1.4_
  - [x] 6.2 Delete all production pipeline files


    - Delete: `telerivetDataPull.py`, `telerivetUtil.py`, `telerivetContactsAdd.py`
    - Delete: `messages_util.py`, `messages_util_22Apr24.py`, `messages_util_26Mar24.py`, `messages_util_backup_17thSept.py`
    - Delete: `TelerivetDataPull_messages.py`, `childbirthrecords_util.py`
    - Delete: `sqlalchemydbwrapper.py`, `dbutil.py`, `databasemodels.py`, `fileUtil.py`, `utilityFunctions.py`
    - Delete: `stringOperations.py`, `automapexample.py`, `test.py`, `testFile.py`, `dbOperations_test.py`, `surveyCTOtest.py`
    - Delete: `TeleRivetSample - Copy.py`, `databaseconfig.ini`, `logconfig_contacts.ini`, `logconfig_smsreminder.ini`, `logconfig.ini`
    - Delete: `appconfig_backup.ini`, `appconfig.ini.bak`, `logconfig_contacts.ini.bak`, `logconfig_smsreminder.ini.bak`, `logconfig.ini.bak`
    - _Requirements: 1.6_
