"""
sample/sample_usage.py

Demonstrates all public functions in telerivet_connector.
Copy and adapt this script for your own project.

Prerequisites:
    pip install .          # installs telerivet and pandas
    cp appconfig.ini.example appconfig.ini   # then fill in your credentials
"""

import datetime
import pandas as pd

from telerivet_connector import (
    load_config,
    query_messages,
    query_contacts,
    get_contact_by_id,
    add_contacts,
    date_range_timestamps,
)


if __name__ == "__main__":

    # ------------------------------------------------------------------
    # 1. Load credentials from appconfig.ini
    # ------------------------------------------------------------------
    try:
        config = load_config("appconfig.ini")
        api_key = config["telerivet_info"]["api_key"]
        project_id = config["telerivet_info"]["project_id"]
        print(f"Loaded config — project_id: {project_id}")
    except (ValueError, KeyError) as e:
        print(f"Config error: {e}")
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # 2. Build a date range for yesterday
    # ------------------------------------------------------------------
    try:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        start_ts, end_ts = date_range_timestamps(yesterday, yesterday)
        print(f"Date range: {start_ts} → {end_ts}  (yesterday, full day)")
    except Exception as e:
        print(f"Timestamp error: {e}")
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # 3. Query messages for yesterday
    # ------------------------------------------------------------------
    try:
        messages_df = query_messages(
            api_key=api_key,
            project_id=project_id,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            date_fields=["time_created", "time_sent", "time_updated"],
        )
        print(f"Messages DataFrame shape: {messages_df.shape}")
        if not messages_df.empty:
            print(messages_df.head(2).to_string())
    except Exception as e:
        print(f"query_messages error: {e}")

    # ------------------------------------------------------------------
    # 4. Query all contacts (no date filter)
    # ------------------------------------------------------------------
    try:
        contacts_df = query_contacts(
            api_key=api_key,
            project_id=project_id,
            date_fields=["time_created", "last_message_time"],
        )
        print(f"Contacts DataFrame shape: {contacts_df.shape}")
        if not contacts_df.empty:
            print(contacts_df.head(2).to_string())
    except Exception as e:
        print(f"query_contacts error: {e}")

    # ------------------------------------------------------------------
    # 5. Fetch a single contact by ID
    # ------------------------------------------------------------------
    try:
        placeholder_contact_id = "CT00000000000000000000000000"  # replace with a real ID
        contact = get_contact_by_id(api_key, project_id, placeholder_contact_id)
        if contact is not None:
            print(f"Found contact: {contact.name} ({contact.phone_number})")
        else:
            print(f"Contact '{placeholder_contact_id}' not found (or an error occurred).")
    except Exception as e:
        print(f"get_contact_by_id error: {e}")

    # ------------------------------------------------------------------
    # 6. Add / update contacts from a small hardcoded DataFrame
    # ------------------------------------------------------------------
    try:
        sample_data = pd.DataFrame([
            {"mobile": "+911234567890", "full_name": "Priya Sharma",  "village": "Pune"},
            {"mobile": "+919876543210", "full_name": "Anita Verma",   "village": "Mumbai"},
            {"mobile": "",              "full_name": "Missing Phone",  "village": "Delhi"},  # will be skipped
        ])

        col_mapping = {
            "mobile":    "phone_number",
            "full_name": "name",
            "village":   "village",   # goes into vars
        }

        added, skipped, errors = add_contacts(
            api_key=api_key,
            project_id=project_id,
            data_df=sample_data,
            col_mapping=col_mapping,
            group_name="SampleGroup",
        )
        print(f"add_contacts result — added: {added}, skipped: {skipped}, errors: {errors}")
    except Exception as e:
        print(f"add_contacts error: {e}")
