import json
import os

from storage import BaseStorage


class JSONStorage(BaseStorage):
    def __init__(self, filename):
        self.filename = filename
        # JSONStorage can handle relative path as file name also, it will create subsequent directories.
        self.ensure_directory_exists()

    def ensure_directory_exists(self):
        directory = os.path.dirname(self.filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def save(self, data):
        existing_data = []
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    # If the file is empty or invalid JSON, start with an empty list
                    existing_data = []
        # to avoid any json object {...} mapping, checking present stored datatype is list or not
        if not isinstance(existing_data, list):
            existing_data = []

        existing_data.append(data)

        with open(self.filename, 'w') as f:
            json.dump(existing_data, f, indent=2)

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return []