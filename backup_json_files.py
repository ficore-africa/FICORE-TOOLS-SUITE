import os
import json
import logging
from datetime import datetime

def backup_json_files(data_dir='data', backup_file='data/backup.txt'):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler('data/backup.log')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    
    try:
        with open(backup_file, 'a') as bf:
            for filename in os.listdir(data_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(data_dir, filename)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        backup_entry = {
                            'timestamp': timestamp,
                            'filename': filename,
                            'data': data
                        }
                        json.dump(backup_entry, bf, indent=2)
                        bf.write('\n')
                        logger.info(f"Backed up {filename} to {backup_file}")
                    except Exception as e:
                        logger.error(f"Error backing up {filename}: {e}")
    except Exception as e:
        logger.error(f"Error writing to {backup_file}: {e}")
        raise