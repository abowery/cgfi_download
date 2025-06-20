#! /usr/bin/python3

import sqlite3
import csv

def export_user_info_to_csv(db_path='dafni_metadata_database', output_csv='user_info/user_info_export.csv'):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, organisation, role, purpose, timestamp FROM user_info")
        rows = cursor.fetchall()

        headers = ['ID', 'Organisation', 'Role', 'Purpose', 'Timestamp']

        with open(output_csv, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            writer.writerows(rows)

        print(f"Data exported successfully to '{output_csv}'.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_user_info_to_csv()
