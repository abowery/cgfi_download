import sys
import os

from app import app as application

sys.path.insert(0, "/PATH_TO_CGFI_DOWNLOAD/cgfi_download")

activate_this = '/PATH_TO_CGFI_DOWNLOAD/cgfi_download/venv/bin/activate_this.py'
with open(activate_this) as file_:
   exec(file_.read(), dict(__file__=activate_this))
