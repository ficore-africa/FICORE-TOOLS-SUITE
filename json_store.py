import json
import os
import uuid
from datetime import datetime
from flask import session, has_request_context
from typing import List, Dict, Optional, Any

class JsonStorage:
    """Custom JSON storage class to manage records with session ID and timestamps."""
    
    def __init__(self, filename: str, logger_instance: 'logging.LoggerAdapter'):
        """
        Initialize JsonStorage with a file path and logger.

        Args:
            filename: Path to the JSON file (relative to project root or absolute).
            logger_instance: Logger instance with SessionAdapter.

        Raises:
            ValueError: If filename is empty or logger_instance is invalid.
            PermissionError: If file or directory is not writable.
        """
        if not filename:
            raise ValueError("Filename cannot be empty")
        if not logger_instance:
            raise ValueError("Logger instance is required")

        # Use /tmp for JSON files on Render
        base_dir = '/tmp' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), '..')
        self.filename = filename if os.path.isabs(filename) else os.path.join(base_dir, filename)
        self.logger = logger_instance

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(self.filename)
        if dir_path:
            self.logger.info(f"Ensuring directory exists: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)

        self._initialize_file()
        self.logger.info(f"Initialized JsonStorage for {os.path.basename(self.filename)} at {self.filename}")

    def _initialize_file(self) -> None:
        """Initialize the JSON file if it doesn't exist and verify permissions."""
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                self.logger.info(f"Created new file: {self.filename}")
            except IOError as e:
                self.logger.error(f"Failed to create {self.filename}: {str(e)}")
                raise PermissionError(f"Cannot create {self.filename}: {str(e)}")

        if not self.is_writable():
            self.logger.error(f"No write permissions for {self.filename}")
            raise PermissionError(f"Cannot write to {self.filename}")

    def is_writable(self) -> bool:
        """Check if the JSON file is writable.

        Returns:
            bool: True if the file is writable, False otherwise.
        """
        try:
            # Check if file exists and is writable
            if os.path.exists(self.filename):
                return os.access(self.filename, os.W_OK)
            # If file doesn't exist, check if directory is writable
            dir_path = os.path.dirname(self.filename) or '.'
            return os.access(dir_path, os.W_OK)
        except Exception as e:
            self.logger.error(f"Error checking write permissions for {self.filename}: {str(e)}")
            return False

    def _read(self) -> List[Dict[str, Any]]:
        """Read all records from the JSON file."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    self.logger.error(f"Invalid data format in {self.filename}: expected list, got {type(data)}")
                    raise ValueError(f"Invalid data format in {self.filename}")
                
                # Validate record structure
                valid_records = []
                for record in data:
                    if not isinstance(record, dict):
                        self.logger.warning(f"Skipping non-dict record in {self.filename}: {record}")
                        continue
                    if not all(key in record for key in ['id', 'session_id', 'timestamp', 'data']):
                        self.logger.warning(f"Skipping record with missing keys in {self.filename}: {record}")
                        continue
                    valid_records.append(record)
                
                self.logger.info(f"Read {len(valid_records)} records from {self.filename}")
                return valid_records
            self.logger.info(f"File {self.filename} not found. Returning empty list.")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from {self.filename}: {str(e)}")
            raise
        except IOError as e:
            self.logger.error(f"Error reading {self.filename}: {str(e)}")
            raise

    def _write(self, data: List[Dict[str, Any]]) -> None:
        """Write data to the JSON file."""
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=4)
            self.logger.info(f"Successfully wrote {len(data)} records to {self.filename}")
        except IOError as e:
            self.logger.error(f"Error writing to {self.filename}: {str(e)}")
            raise

    def write(self, data: List[Dict[str, Any]]) -> None:
        """Public method to write data to the JSON file."""
        self._write(data)

    def read_all(self) -> List[Dict[str, Any]]:
        """Retrieve all records from the JSON file."""
        return self._read()

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all records (alias for read_all)."""
        return self.read_all()

    def append(self, record: Dict[str, Any], user_email: Optional[str] = None, session_id: Optional[str] = None, lang: Optional[str] = None) -> str:
        """Append a new record to the JSON file.

        Args:
            record: Data to store.
            user_email: Optional email associated with the record.
            session_id: Optional session ID; defaults to Flask session['sid'] if not provided.
            lang: Optional language code for the record.

        Returns:
            The record ID.

        Raises:
            RuntimeError: If the record cannot be appended.
        """
        if not session_id:
            session_id = session.get('sid', 'no-session-id') if has_request_context() else 'no-session-id'
        try:
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": record
            }
            if user_email:
                record_with_metadata["user_email"] = user_email
            if lang:
                record_with_metadata["lang"] = lang
            records.append(record_with_metadata)
            self._write(records)
            self.logger.info(f"Appended record {record_id} to {self.filename}")
            return record_id
        except Exception as e:
            self.logger.error(f"Failed to append record to {self.filename}: {str(e)}")
            raise RuntimeError(f"Cannot append record to {self.filename}: {str(e)}")

    def filter_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve records matching the session ID."""
        try:
            records = self._read()
            filtered = [r for r in records if r.get("session_id") == session_id]
            self.logger.info(f"Filtered {len(filtered)} records for session {session_id} in {self.filename}")
            return filtered
        except Exception as e:
            self.logger.error(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}")
            raise

    def filter_by_id(self, record_id: str) -> List[Dict[str, Any]]:
        """Retrieve records matching the record ID."""
        try:
            records = self._read()
            filtered = [r for r in records if r.get("id") == record_id]
            self.logger.info(f"Filtered {len(filtered)} records for ID {record_id} in {self.filename}")
            return filtered
        except Exception as e:
            self.logger.error(f"Error filtering {self.filename} by ID {record_id}: {str(e)}")
            raise

    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record by ID."""
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    self.logger.info(f"Retrieved record {record_id} from {self.filename}")
                    return record
            self.logger.warning(f"Record {record_id} not found in {self.filename}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting record {record_id} from {self.filename}: {str(e)}")
            raise

    def update_by_id(self, record_id: str, updated_data: Dict[str, Any]) -> None:
        """Update a record by ID."""
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    record["data"] = updated_data
                    self._write(records)
                    self.logger.info(f"Updated record {record_id} in {self.filename}")
                    return
            self.logger.warning(f"Record {record_id} not found for update in {self.filename}")
            raise ValueError(f"Record {record_id} not found")
        except Exception as e:
            self.logger.error(f"Error updating record {record_id} in {self.filename}: {str(e)}")
            raise

    def delete_by_id(self, record_id: str) -> None:
        """Delete a record by ID."""
        try:
            records = self._read()
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                self._write(records)
                self.logger.info(f"Deleted record {record_id} from {self.filename}")
            else:
                self.logger.warning(f"Record {record_id} not found for deletion in {self.filename}")
                raise ValueError(f"Record {record_id} not found")
        except Exception as e:
            self.logger.error(f"Error deleting record {record_id} in {self.filename}: {str(e)}")
            raise

def init_storage(filename, logger_instance):
    return JsonStorage(filename, logger_instance)
