<b>Code for the 'DAFNI Open Access Datasets Download Service'</b>


This code downloads the metadata from the DAFNI CLI service, it uses this to populate a database. This enables a basic webservice to query the metadata and allow the downloading of the datasets hosted by the DAFNI service without authentication. This work was done for the CGFI project (July 2024)

To run the webservice, install the dafni-cli, flask and pexpect pip libraries:

<b>pip3 install dafni-cli flask pexpect</b>

You will need a login to dafni data service. Then populate the metadata database:

<b>./populate_dafni_metadata_database.py</b>

And run the webservice:

<b>python3 app.py</b>

This will enable the service to be available locally at:

http://127.0.0.1:5000/
