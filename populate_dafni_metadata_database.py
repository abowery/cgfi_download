#! /usr/bin/python3

import pexpect, sys, json, sqlite3, subprocess, pathlib
from subprocess import Popen, PIPE


# Function to create the database and tables
def create_database(db_name):
    # Connect to the database (it will be created if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create 'formats' table
    cursor.execute('''
    DROP TABLE IF EXISTS formats
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS formats (
        description TEXT(100),
        identifier INTEGER(100)
    )
    ''')

    # Create 'sources' table
    cursor.execute('''
    DROP TABLE IF EXISTS sources
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sources (
        description TEXT,
        identifier NUMERIC
    )
    ''')

    # Create 'subjects' table
    cursor.execute('''
    DROP TABLE IF EXISTS subjects
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subjects (
        description TEXT,
        identifier NUMERIC
    )
    ''')

    # Create 'datasets' table
    cursor.execute('''
    DROP TABLE IF EXISTS datasets
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS datasets (
        title TEXT,
        description TEXT,
        subject TEXT,
        source TEXT,
        format TEXT,
        date_range_begin TEXT,
        date_range_end TEXT,
        version_uuid NUMERIC
    )
    ''')

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def populate_database(db_name, data):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Populate formats table
    for format_text, format_value in data['filters']['formats'].items():
        cursor.execute('INSERT INTO formats (description, identifier) VALUES (?, ?)', (format_text, format_value))

    # Populate sources table
    for source_text, source_value in data['filters']['sources'].items():
        cursor.execute('INSERT INTO sources (description, identifier) VALUES (?, ?)', (source_text, source_value))

    # Populate subjects table
    for subject_text, subject_value in data['filters']['subjects'].items():
        cursor.execute('INSERT INTO subjects (description, identifier) VALUES (?, ?)', (subject_text, subject_value))

    # Populate datasets table
    for metadata in data['metadata']:
        title = metadata.get('title', None)
        description = metadata.get('description', None)
        subject = metadata.get('subject', None)
        source = metadata.get('source', None)
        #format_list = ','.join(metadata.get('formats', []))
        format_list = ','.join([f if f is not None else 'NULL' for f in metadata.get('formats',[])])
        date_range_begin = metadata.get('date_range', {}).get('begin', None)
        date_range_end = metadata.get('date_range', {}).get('end', None)
        version_uuid = metadata.get('id', {}).get('version_uuid', None)

        cursor.execute('''
        INSERT INTO datasets (title, description, subject, source, format, date_range_begin, date_range_end, version_uuid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, subject, source, format_list, date_range_begin, date_range_end, version_uuid))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def print_table_contents(cursor, table_name):
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    print(f"\nContents of table '{table_name}':")
    for row in rows:
        print(row)


def print_database_contents(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Print contents of formats table
    print_table_contents(cursor, 'formats')

    # Print contents of sources table
    print_table_contents(cursor, 'sources')

    # Print contents of subjects table
    print_table_contents(cursor, 'subjects')

    # Print contents of datasets table
    print_table_contents(cursor, 'datasets')

    conn.close()


def interact_with_dafni():

    # Login to dafni service
    dafni_exec = "/PATH_TO_CGFI_DOWNLOAD/cgfi_download/./venv/bin/dafni"
    dafni_login = dafni_exec + " login"
    child = pexpect.spawn(dafni_login)
    #child.logfile = sys.stdout.buffer
    child.expect('Username: ')
    i = child.sendline('cgfi-service-account')  
    i = child.expect(['Password: ','Username: '])
    if i == 0:
      print('Username accepted')
      child.sendline('CGFI_PASSWORD')
      j = child.expect(['Logged in as cgfi-service-account','Password: '])
      if j == 0:
         print('Login successful')
      elif j == 1:
         print('Login unsuccessful')
    elif i == 1:
      print('Username not accepted')

    # Get all datasets
    process = subprocess.Popen([dafni_exec,"get","datasets","-j"],stdout=subprocess.PIPE,text=True)
    data = json.loads(process.stdout.read())

    #print(data)

    # Populate database
    populate_database('dafni_metadata_database', data)

    # Log out of dafni service
    subprocess.call([dafni_exec,"logout"])


if __name__ == '__main__':

    # Create the database
    db_name = 'dafni_metadata_database'
    create_database(db_name)
    print(f"Database '{db_name}' created with the specified tables.")

    # Start the dafni cli
    interact_with_dafni()

    # Unused sample test data
    sample_data = {
    "filters": {
       "formats": {
         "application/geopackage+sqlite3": 4,
         "application/json": 6,
         "application/octet-stream": 11,
         "application/pdf": 4,
         "application/pgp-keys": 33,
         "application/vnd.dbf": 2,
         "application/vnd.ms-excel": 1,
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": 9,
         "application/x-netcdf": 53,
         "application/x-qgis": 9,
         "application/x-tar": 17,
         "application/xml": 5,
         "application/zip": 30,
         "image/png": 24,
         "image/tiff": 3,
         "text/csv": 701,
         "text/plain": 30,
         "text/x-sh": 1
        },
        "sources": { "source1": 1, "source2": 2 },
        "subjects": { "subject1": 1, "subject2": 2 },
        "total_dataset_count": 3
    },
    "metadata": [
        {
            "auth": { },
            "date_range": { "begin": "1980-12-01", "end": "1981-12-01" },
            "description": "this is a test",
            "formats": [ "format1" ],
            "id": { "asset_id": "", "dataset_uuid": "", "metadata_uuid": "", "version_uuid": "123456" },
            "modified_date": "",
            "source": "source1",
            "status": "",
            "subject": "subject1",
            "title": "Test_file1"
        }
    ]
    }
 
    # Print the contents of the database
    #print_database_contents(db_name)
