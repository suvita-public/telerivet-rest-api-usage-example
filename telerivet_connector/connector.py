"""
telerivet_connector/connector.py

Wraps the Telerivet REST API Python client for common operations:
querying messages, querying contacts, fetching a contact by ID,
and bulk-upserting contacts.
"""

import configparser
import datetime
import logging
import os
import time

import pandas as pd
import telerivet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def load_config(config_file: str) -> dict:
    """Read *config_file* (INI format) and return a dict-of-dicts keyed by section.

    Raises ValueError if:
    - the file does not exist
    - the [telerivet_info] section is absent
    - api_key is missing from [telerivet_info]
    """
    if not os.path.exists(config_file):
        raise ValueError(f"Config file not found: {config_file}")

    config = configparser.ConfigParser()
    config.read(config_file)

    if not config.has_section("telerivet_info"):
        raise ValueError(f"Missing [telerivet_info] section in {config_file}")

    if not config.has_option("telerivet_info", "api_key"):
        raise ValueError(f"Missing api_key in [telerivet_info] of {config_file}")

    result = {}
    for section in config.sections():
        result[section] = dict(config.items(section))

    logger.debug("Loaded config from %s — sections: %s", config_file, list(result.keys()))
    return result


# ---------------------------------------------------------------------------
# Timestamp utilities
# ---------------------------------------------------------------------------

_IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def timestamp_to_datetime(ts) -> datetime.datetime | None:
    """Convert a Unix timestamp integer to an IST (UTC+5:30) datetime.

    Returns None for falsy input (0, None, empty string, etc.).
    """
    if not ts:
        return None
    utc_dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return utc_dt.astimezone(_IST_OFFSET)


def day_start_timestamp(date: datetime.datetime) -> int:
    """Return the Unix timestamp for midnight at the start of *date*."""
    start_of_day = datetime.datetime(date.year, date.month, date.day)
    return int(start_of_day.timestamp())


def day_end_timestamp(date: datetime.datetime) -> int:
    """Return the Unix timestamp for 23:59:59 at the end of *date*."""
    end_of_day = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)
    return int(end_of_day.timestamp())


def date_range_timestamps(start_date: datetime.datetime, end_date: datetime.datetime) -> tuple[int, int]:
    """Return (start_timestamp, end_timestamp) covering the full day range from start to end inclusive."""
    return day_start_timestamp(start_date), day_end_timestamp(end_date)


# ---------------------------------------------------------------------------
# Internal cursor helper
# ---------------------------------------------------------------------------

def _iter_cursor(
    cursor,
    key_field: str,
    lookup_dict: dict,
    resolved_field_name: str,
    date_fields: list[str] | None,
) -> list[dict]:
    """Iterate a Telerivet API cursor and return a list of row dicts.

    For each object in *cursor*:
    - Extracts the raw ``_data`` attribute dict.
    - Resolves IDs in *key_field* via *lookup_dict*, joining as a
      comma-separated string stored under *resolved_field_name*.
    - Converts any field listed in *date_fields* from a Unix timestamp
      to an IST datetime using :func:`timestamp_to_datetime`.
    - Flattens the ``vars`` dict directly into the row.

    Retries up to 3 times on :class:`ConnectionError` with a 30-second
    sleep between attempts, then re-raises.  Any other exception is
    raised immediately (fixes the original ``finally: return`` bug).
    """
    _date_fields = set(date_fields) if date_fields else set()
    max_retries = 3
    retry_count = 0
    rows: list[dict] = []

    while retry_count < max_retries:
        try:
            for obj in cursor:
                row: dict = {}
                # Extract the raw API response dict via the _data attribute
                raw = getattr(obj, "_data", None)
                if raw is None:
                    # Fallback: scan dir() for any attribute starting with _data
                    for attr in dir(obj):
                        if attr.startswith("_data"):
                            raw = getattr(obj, attr)
                            break
                if not raw:
                    continue

                for key, value in raw.items():
                    if key == key_field:
                        # Resolve IDs → names; fall back to the raw ID if not found
                        resolved = [lookup_dict.get(id_, id_) for id_ in (value or [])]
                        row[resolved_field_name] = ",".join(resolved)
                    elif key in _date_fields:
                        row[key] = timestamp_to_datetime(value)
                    elif key == "vars":
                        if value:
                            row.update(value)
                    else:
                        row[key] = value

                rows.append(row)

            # Cursor exhausted successfully — exit the retry loop
            break

        except ConnectionError as exc:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(
                    "ConnectionError during cursor iteration — max retries (%d) reached",
                    max_retries,
                    exc_info=True,
                )
                raise
            logger.info(
                "ConnectionError during cursor iteration — retrying (%d/%d) in 30s",
                retry_count,
                max_retries,
            )
            time.sleep(30)

        except Exception:
            logger.error("Unexpected error during cursor iteration", exc_info=True)
            raise

    return rows


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def query_messages(
    api_key: str,
    project_id: str,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    date_fields: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch messages from a Telerivet project and return a :class:`pandas.DataFrame`.

    Applies an optional date range filter via *start_timestamp* / *end_timestamp*
    (Unix integers).  Label IDs are resolved to human-readable names and stored
    in a ``labels`` column.  Fields listed in *date_fields* are converted to IST
    datetimes.  ``vars`` fields are flattened into top-level columns.
    """
    tr = telerivet.API(api_key)
    project = tr.initProjectById(project_id)

    # Build timestamp filter
    if start_timestamp is not None and end_timestamp is not None:
        cursor = project.queryMessages(time_created={"min": start_timestamp, "max": end_timestamp})
    elif start_timestamp is not None:
        cursor = project.queryMessages(time_created={"min": start_timestamp})
    elif end_timestamp is not None:
        cursor = project.queryMessages(time_created={"max": end_timestamp})
    else:
        cursor = project.queryMessages()

    logger.info("query_messages: cursor count = %d", cursor.count())

    # Build label ID → name lookup
    label_lookup = {label.id: label.name for label in project.queryLabels()}

    rows = _iter_cursor(cursor, "label_ids", label_lookup, "labels", date_fields)
    return pd.DataFrame(rows)


def query_contacts(
    api_key: str,
    project_id: str,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    date_fields: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch contacts from a Telerivet project and return a :class:`pandas.DataFrame`.

    Applies an optional date range filter via *start_timestamp* / *end_timestamp*
    (Unix integers).  Group IDs are resolved to human-readable names and stored
    in a ``groups`` column.  Fields listed in *date_fields* are converted to IST
    datetimes.  ``vars`` fields are flattened into top-level columns.
    """
    tr = telerivet.API(api_key)
    project = tr.initProjectById(project_id)

    # Build timestamp filter
    if start_timestamp is not None and end_timestamp is not None:
        cursor = project.queryContacts(time_created={"min": start_timestamp, "max": end_timestamp})
    elif start_timestamp is not None:
        cursor = project.queryContacts(time_created={"min": start_timestamp})
    elif end_timestamp is not None:
        cursor = project.queryContacts(time_created={"max": end_timestamp})
    else:
        cursor = project.queryContacts()

    # Build group ID → name lookup
    group_lookup = {group.id: group.name for group in project.queryGroups()}

    rows = _iter_cursor(cursor, "group_ids", group_lookup, "groups", date_fields)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Contact management functions
# ---------------------------------------------------------------------------

def get_contact_by_id(api_key: str, project_id: str, contact_id: str):
    """Fetch a single Telerivet contact by ID.

    Returns the contact object on success, or ``None`` if the contact does
    not exist or any exception occurs (fault-tolerant behaviour matching the
    original pipeline).
    """
    try:
        tr = telerivet.API(api_key)
        project = tr.initProjectById(project_id)
        return project.getContactById(contact_id)
    except Exception:
        logger.error(
            "Failed to get contact by ID '%s'", contact_id, exc_info=True
        )
        return None


def add_contacts(
    api_key: str,
    project_id: str,
    data_df: pd.DataFrame,
    col_mapping: dict,
    group_name: str | None = None,
) -> tuple[int, int, int]:
    """Upsert contacts into a Telerivet project from a DataFrame.

    *col_mapping* maps source DataFrame column names to Telerivet target field
    names.  ``phone_number`` and ``name`` are treated as top-level contact
    fields; all other mapped targets are passed as contact ``vars``.

    If *group_name* is provided, every successfully upserted contact is added
    to that group (created if it does not exist).

    Returns ``(added, skipped, errors)`` counts.
    """
    tr = telerivet.API(api_key)
    project = tr.initProjectById(project_id)

    # Resolve group once if needed
    group = None
    if group_name:
        group = project.getOrCreateGroup(group_name)

    added = 0
    skipped = 0
    errors = 0

    for _, row in data_df.iterrows():
        # Apply column mapping to build the contact payload
        mapped: dict = {}
        for src_col, target_field in col_mapping.items():
            if src_col in row.index:
                mapped[target_field] = row[src_col]

        phone_number = mapped.get("phone_number")
        if not phone_number:
            logger.warning(
                "Skipping row — missing phone_number (mapped fields: %s)",
                list(mapped.keys()),
            )
            skipped += 1
            continue

        try:
            contact_params: dict = {"phone_number": phone_number}

            if "name" in mapped:
                contact_params["name"] = mapped["name"]

            # All other mapped targets go into vars
            vars_dict = {
                k: v for k, v in mapped.items()
                if k not in ("phone_number", "name")
            }
            if vars_dict:
                contact_params["vars"] = vars_dict

            contact = project.getOrCreateContact(contact_params)

            if group is not None:
                contact.addToGroup(group)

            logger.debug("Upserted contact: %s", phone_number)
            added += 1

        except Exception:
            logger.error(
                "Error upserting contact with phone_number '%s'",
                phone_number,
                exc_info=True,
            )
            errors += 1

    logger.info(
        "add_contacts complete — added: %d, skipped: %d, errors: %d",
        added, skipped, errors,
    )
    return added, skipped, errors
