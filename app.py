from flask import Flask, render_template, request, jsonify, send_file, redirect, session, url_for
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
app.secret_key = 'SECRET_KEY_HERE'


# Function to fetch distinct values from a table
def get_distinct_values(table, column):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT DISTINCT {column} FROM {table}')
    values = cursor.fetchall()
    conn.close()
    return values


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


# Function to convert date from 'dd/mm/yyyy' to Unix timestamp
def date_to_unix(date_str):
    try:
        return int(time.mktime(datetime.strptime(date_str, '%d/%m/%Y').timetuple()))
    except ValueError:
        return None


# Database connection function
def get_db_connection():
    conn = sqlite3.connect('/PATH_TO_CGFI_DOWNLOAD/cgfi_download/dafni_metadata_database')
    conn.row_factory = sqlite3.Row
    return conn


# Function to get all sources, subjects, and formats from the database
def get_filters():
    conn = get_db_connection()

    sources = conn.execute('SELECT description FROM sources').fetchall()
    subjects = conn.execute('SELECT description FROM subjects').fetchall()
    formats = conn.execute('SELECT description FROM formats').fetchall()

    conn.close()

    # Format the formats to display the second word without 'vnd.'
    #formats = [(f[0].split('/')[-1].replace('vnd.', ''),) for f in formats]
    formats_display = [(f[0].split('/')[-1].replace('vnd.', ''), f[0]) for f in formats]

    return sources, subjects, formats_display


# Function to query datasets based on filters
def get_datasets(search=None, from_date=None, to_date=None, sources=None, subjects=None, formats=None):
    query = 'SELECT title, description, date_range_begin, date_range_end, source, format, subject, version_uuid FROM datasets WHERE 1=1'
    params = []

    # Search by title
    if search:
        query += ' AND title LIKE ?'
        params.append(f'%{search}%')

    # Filter by date range
    if from_date:
        query += ' AND date_range_begin >= ?'
        params.append(from_date)

    if to_date:
        query += ' AND date_range_end <= ?'
        params.append(to_date)

    # Filter by sources
    if sources:
        query += ' AND source IN ({})'.format(','.join('?' * len(sources)))
        params.extend(sources)

    # Filter by subjects
    if subjects:
        query += ' AND subject IN ({})'.format(','.join('?' * len(subjects)))
        params.extend(subjects)

    # Filter by formats
    if formats:
        query += ' AND format IN ({})'.format(','.join('?' * len(formats)))
        params.extend(formats)

    conn = get_db_connection()
    datasets = conn.execute(query, params).fetchall()
    conn.close()

    return datasets


@app.route('/download/<version_uuid>', methods=['GET'])
def download(version_uuid):

    # Note: ensure the dafni-cli pip library is installed first
    # Change 'PATH_TO_CGFI_DOWNLOAD' to installed directory
    dafni_command = "/PATH_TO_CGFI_DOWNLOAD/cgfi_download/./venv/bin/dafni"
    subprocess.run([dafni_command, 'logout'], check=True)
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


@app.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'POST':
        organisation = request.form.get('organisation')
        role = request.form.get('role')
        purpose = request.form.get('purpose')

        if organisation and role and purpose:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO user_info (organisation, role, purpose) VALUES (?, ?, ?)',
                (organisation, role, purpose)
            )
            conn.commit()
            conn.close()
            session['form_completed'] = True
            return redirect(url_for('index'))
    return render_template('form.html')


@app.route('/', methods=['GET', 'POST'])
def index():

    if not session.get('form_completed'):
        return redirect(url_for('start'))

    # Get available filters
    sources, subjects, formats_display = get_filters()

    # Handle search and filters
    search = request.form.get('search', 'cgfi')  # Default search value 'cgfi'

    from_date_str = request.form.get('from_date', '').strip()
    to_date_str = request.form.get('to_date', '').strip()

    if from_date_str:
        from_date_unix = convert_to_unix_time(from_date_str, date_format='%d/%m/%Y')
    else:
        from_date_unix = ''
    if to_date_str:
        to_date_unix = convert_to_unix_time(to_date_str, date_format='%d/%m/%Y')
    else:
        to_date_unix = ''

    selected_sources = request.form.getlist('sources')
    selected_subjects = request.form.getlist('subjects')
    selected_formats = request.form.getlist('formats')

    # Get datasets based on filters
    datasets = get_datasets(search, str(from_date_unix), str(to_date_unix), selected_sources, selected_subjects, selected_formats)

    return render_template('index.html', sources=sources, subjects=subjects, formats=formats_display, datasets=datasets)


if __name__ == '__main__':
    update_dates_to_unix()  # Convert date columns to Unix time on startup
    app.run(debug=True)
