#! /usr/bin/python3

import sqlite3, subprocess, os, shutil, tempfile, zipfile
import pexpect, sys, json, sqlite3, subprocess, pathlib
from flask import Flask, render_template, request, send_file
from subprocess import Popen, PIPE


app = Flask(__name__)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('example.db')
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

@app.route('/', methods=['GET', 'POST'])
def index():
    datasets = []
    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        from_date = request.form.get('from_date', '')
        to_date = request.form.get('to_date', '')
        sources = request.form.getlist('source')
        subjects = request.form.getlist('subject')
        formats = request.form.getlist('format')

        query = 'SELECT * FROM datasets WHERE title LIKE ?'
        params = [f'%{search_query}%']

        if from_date:
            query += ' AND date_range_begin >= ?'
            params.append(from_date)
        if to_date:
            query += ' AND date_range_end <= ?'
            params.append(to_date)
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

    sources = get_distinct_values('sources', 'description')
    subjects = get_distinct_values('subjects', 'description')
    formats = get_distinct_values('formats', 'description')

    return render_template('index.html', datasets=datasets, sources=sources, subjects=subjects, formats=formats)

@app.route('/download/<version_uuid>', methods=['GET'])
def download(version_uuid):

    # Install the dafni-cli library locally 
    subprocess.call(["/bin/pip","install","-q","dafni-cli"])

    dafni_login = str(pathlib.Path().resolve()) + "/../../.local/bin/dafni login"
    child = pexpect.spawn(dafni_login)
    child.expect('Username: ')
    i = child.sendline('CGFI_USERNAME')
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


    # Create a temporary directory in the same location as app.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, 'temp_download')
    os.makedirs(temp_dir, exist_ok=True)
    try:
        # Run the dafni download dataset command and save to temp_dir
        os.chdir(temp_dir)
        subprocess.run(['dafni', 'download', 'dataset', version_uuid], check=True)
        subprocess.run(['dafni', 'logout'], check=True)
        os.chdir("..") 

        # Zip the contents of the temp_dir
        zip_filename = f'{version_uuid}.zip'
        zip_filepath = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file != zip_filename:  # Exclude the zip file itself
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, temp_dir))

        return send_file(zip_filepath, as_attachment=True)
    except subprocess.CalledProcessError as e:
        return f"An error occurred: {e}", 500
    except Exception as e:
        return f"An error occurred during zipping: {e}", 500
    finally:
        # Clean up: remove the temporary directory and its contents
        shutil.rmtree(temp_dir)



if __name__ == '__main__':
    app.run(debug=True)

