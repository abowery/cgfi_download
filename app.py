from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import subprocess
import os
import shutil
import tempfile
import zipfile
import time
import random
import pathlib
import pexpect
from datetime import datetime

app = Flask(__name__)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('dafni_metadata_database')
    conn.row_factory = sqlite3.Row
    return conn

# Function to fetch distinct values from a table
def get_distinct_values(table, column):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT DISTINCT {column} FROM {table}')
    values = cursor.fetchall()
    conn.close()
    return values

# Function to split 'text' values in formats table and remove 'vnd.' if present
def get_formatted_values():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT description, identifier FROM formats')
    formats = cursor.fetchall()
    conn.close()
    
    formatted_values = []
    for format in formats:
        text_parts = format['description'].split('/')
        if len(text_parts) > 1:
            second_word = text_parts[1]
            if second_word.startswith('vnd.'):
                second_word = second_word[4:]
            formatted_values.append({'description': second_word, 'identifier': format['identifier']})
        else:
            formatted_values.append({'description': format['description'], 'identifier': format['identifier']})
    return formatted_values

# Function to convert date to Unix time
def convert_to_unix_time(date_str, date_format='%Y-%m-%d'):
    try:
        # Try to convert assuming the date_str is a string date
        date_str = date_str.split('T')[0]
        dt = datetime.strptime(date_str, date_format)
        return int(time.mktime(dt.timetuple()))
    except ValueError:
        # If conversion fails, it might already be Unix time, so return it as is
        return int(date_str)

# Function to update date columns to Unix time
def update_dates_to_unix():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT rowid, date_range_begin, date_range_end FROM datasets')
    datasets = cursor.fetchall()

    for dataset in datasets:
        rowid = dataset['rowid']
        date_range_begin = dataset['date_range_begin']
        date_range_end = dataset['date_range_end']

        try:
            # Check if the dates are already Unix timestamps
            if not isinstance(date_range_begin, int):
                unix_date_range_begin = convert_to_unix_time(date_range_begin) if date_range_begin else None
            if not isinstance(date_range_end, int):
                unix_date_range_end = convert_to_unix_time(date_range_end) if date_range_end else None

            cursor.execute('UPDATE datasets SET date_range_begin = ?, date_range_end = ? WHERE rowid = ?',
                           (unix_date_range_begin, unix_date_range_end, rowid))
        except ValueError:
            # If they are already Unix timestamps, just continue
            continue

    conn.commit()
    conn.close()

@app.route('/', methods=['GET'])
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM datasets')
    datasets = cursor.fetchall()
    conn.close()

    sources = get_distinct_values('sources', 'description')
    subjects = get_distinct_values('subjects', 'description')
    formats = get_formatted_values()

    return render_template('index.html', datasets=datasets, sources=sources, subjects=subjects, formats=formats)

@app.route('/filter_datasets', methods=['POST'])
def filter_datasets():
    search_query = request.form.get('search_query', '')
    from_date_str = request.form.get('from_date', '')
    to_date_str = request.form.get('to_date', '')
    sources = request.form.getlist('sources[]')
    subjects = request.form.getlist('subjects[]')
    formats = request.form.getlist('formats[]')

    query = 'SELECT * FROM datasets WHERE 1=1'
    params = []

    if search_query:
        query += ' AND title LIKE ?'
        params.append(f'%{search_query}%')
    if from_date_str:
        from_date_unix = convert_to_unix_time(from_date_str, date_format='%d/%m/%Y')
        query += ' AND date_range_begin >= ?'
        params.append(from_date_unix)
    if to_date_str:
        to_date_unix = convert_to_unix_time(to_date_str, date_format='%d/%m/%Y')
        query += ' AND date_range_end <= ?'
        params.append(to_date_unix)
    if sources:
        query += ' AND source IN (' + ','.join('?' for _ in sources) + ')'
        params.extend(sources)
    if subjects:
        query += ' AND subject IN (' + ','.join('?' for _ in subjects) + ')'
        params.extend(subjects)
    if formats:
        query += ' AND format IN (' + ','.join('?' for _ in formats) + ')'
        params.extend(formats)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    datasets = cursor.fetchall()
    conn.close()

    return jsonify(datasets=[dict(row) for row in datasets])

@app.route('/download/<version_uuid>', methods=['GET'])
def download(version_uuid):

    # Note: ensure the dafni-cli pip library is installed first
    # Change 'PATH_TO_CGFI_DOWNLOAD' to installed directory
    dafni_command = "PATH_TO_CGFI_DOWNLOAD" + "/cgfi_download/./venv/bin/dafni"
    dafni_login = dafni_command + " login"
    child = pexpect.spawn(dafni_login)
    child.expect('Username: ')
    i = child.sendline('cgfi-service-account')
    i = child.expect(['Password: ','Username: '])
    if i == 0:
      print('Username accepted')

      # Change CGFI_PASSWORD to password for accessing the DAFNI service
      child.sendline('CGFI_PASSWORD')
      j = child.expect(['Logged in as cgfi-service-account','Password: '])
      if j == 0:
         print('Login successful')
      elif j == 1:
         print('Login unsuccessful')
    elif i == 1:
      print('Username not accepted')

    # Create a temporary directory in the same location as app.py
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp_download_' + str(random.randint(1000, 9999)))
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Run the dafni download dataset command and save to temp_dir
        os.chdir(temp_dir)
        subprocess.run([dafni_command, 'download', 'dataset', version_uuid], check=True)
        subprocess.run([dafni_command, 'logout'], check=True)
        os.chdir("..") 
        
        zip_filename = os.path.join(os.path.dirname(__file__), f'{version_uuid}.zip')
        shutil.make_archive(zip_filename.replace('.zip', ''), 'zip', temp_dir)

        return send_file(zip_filename, as_attachment=True)
    finally:
        shutil.rmtree(temp_dir)
        os.remove(zip_filename)

if __name__ == '__main__':
    update_dates_to_unix()  # Convert date columns to Unix time on startup
    app.run(debug=True)
