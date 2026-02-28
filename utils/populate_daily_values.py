import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from models.entities import Entity
from models.value_names import ValueName
from models.dates import DateEntry
from models.daily_values import DailyValue

# Setup logging
logging.basicConfig(filename='populate_daily_values.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s %(message)s')

SUBMISSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'raw_data', 'submissions')
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sec.db')
engine = create_engine(f'sqlite:///{DB_PATH}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def get_or_create_entity(cik):
    entity = session.query(Entity).filter_by(cik=cik).first()
    if not entity:
        entity = Entity(cik=cik)
        session.add(entity)
        session.commit()
    return entity

def get_or_create_value_name(name):
    value_name = session.query(ValueName).filter_by(name=name).first()
    if not value_name:
        value_name = ValueName(name=name, source=1, added_on=datetime.utcnow())
        session.add(value_name)
        session.commit()
    return value_name

def get_or_create_date_entry(date_str):
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception as e:
        logging.error(f"Invalid date format: {date_str} - {e}")
        return None
    date_entry = session.query(DateEntry).filter_by(date=date_obj).first()
    if not date_entry:
        date_entry = DateEntry(date=date_obj)
        session.add(date_entry)
        session.commit()
    return date_entry

def delete_all_daily_values():
    """One-time callable: Delete all data from the DailyValue table."""
    try:
        num_deleted = session.query(DailyValue).delete()
        session.commit()
        print(f"Deleted {num_deleted} rows from DailyValue table.")
        logging.warning(f"Deleted {num_deleted} rows from DailyValue table via delete_all_daily_values().")
    except Exception as e:
        session.rollback()
        print(f"Error deleting DailyValue data: {e}")
        logging.error(f"Error deleting DailyValue data: {e}", exc_info=True)

def main():
    files = [f for f in os.listdir(SUBMISSIONS_DIR) if f.endswith('.json')]
    total_files = len(files)
    error_files = []
    total_successful_inserts = 0
    print(f"Starting processing of {total_files} files.")
    logging.info(f"Starting processing of {total_files} files.")
    for idx, filename in enumerate(files, 1):
        print(f"Processing file {idx}/{total_files}: {filename}")
        logging.info(f"Processing file {idx}/{total_files}: {filename}")
        file_path = os.path.join(SUBMISSIONS_DIR, filename)
        error_count_before = 0
        successful_inserts = 0
        try:
            with open('populate_daily_values.log', 'r') as logf:
                error_count_before = sum(1 for line in logf)
        except FileNotFoundError:
            error_count_before = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cik = data.get('cik')
            if not cik:
                # Enhanced logging for missing CIK
                sample_content = str(data)[:500]  # Log up to 500 chars of content
                logging.error(f"Missing CIK in file: {filename}. Sample content: {sample_content}")
                print(f"[WARNING] Missing CIK in file: {filename}. See log for details.")
                error_files.append(filename)
                # Try to infer CIK from filename (if possible)
                inferred_cik = None
                if filename.startswith('CIK') and '-' in filename:
                    inferred_cik = filename.split('-')[0].replace('CIK', '')
                if inferred_cik:
                    print(f"[INFO] Attempting to use inferred CIK: {inferred_cik} from filename.")
                    logging.info(f"Attempting to use inferred CIK: {inferred_cik} from filename {filename}.")
                    cik = inferred_cik
                    entity = get_or_create_entity(cik)
                else:
                    continue
            entity = get_or_create_entity(cik)
            filings = data.get('filings', {})
            recent = filings.get('recent', {})
            # Loop over all value names in filings['recent']
            for value_name in recent.keys():
                vn_obj = get_or_create_value_name(value_name)
                values = recent.get(value_name, [])
                # Find the corresponding date array
                if value_name == 'filingDate':
                    date_values = values
                elif value_name == 'reportDate':
                    date_values = values
                else:
                    # Use filingDate if available, else skip
                    date_values = recent.get('filingDate', [])
                # Loop over values and dates
                for idx_val, val in enumerate(values):
                    # Try to get date for this value
                    date_str = None
                    if value_name in ['filingDate', 'reportDate']:
                        date_str = val
                    elif 'filingDate' in recent and idx_val < len(recent['filingDate']):
                        date_str = recent['filingDate'][idx_val]
                    elif 'reportDate' in recent and idx_val < len(recent['reportDate']):
                        date_str = recent['reportDate'][idx_val]
                    if not date_str:
                        continue
                    date_entry = get_or_create_date_entry(date_str)
                    if not date_entry:
                        continue
                    # Store value (try to convert to float, else None)
                    try:
                        # Check if DailyValue already exists
                        existing_dv = session.query(DailyValue).filter_by(
                            entity_id=entity.id,
                            value_name_id=vn_obj.id,
                            date_id=date_entry.id
                        ).first()
                        if existing_dv is not None:
                            continue  # Skip duplicate
                        value_float = float(val)
                    except (ValueError, TypeError):
                        value_float = None
                    try:
                        daily_value = DailyValue(
                            entity_id=entity.id,
                            value_name_id=vn_obj.id,
                            date_id=date_entry.id,
                            value=value_float
                        )
                        session.add(daily_value)
                        session.commit()
                        successful_inserts += 1
                        total_successful_inserts += 1
                    except Exception as e:
                        logging.error(f"Error inserting DailyValue for file {filename}, value_name {value_name}, date {date_str}: {e}", exc_info=True)
                        error_files.append(filename)
            logging.info(f"Completed file {filename}: {successful_inserts} values inserted.")
        except Exception as e:
            logging.error(f"Error processing file {filename}: {e}", exc_info=True)
            error_files.append(filename)
        error_count_after = 0
        try:
            with open('populate_daily_values.log', 'r') as logf:
                error_count_after = sum(1 for line in logf)
        except FileNotFoundError:
            error_count_after = 0
        print(f"Errors after file {filename}: {error_count_after}")
    session.close()
    # Summary logging
    summary_msg = (f"Processing complete. Total files: {total_files}, "
                   f"Total successful inserts: {total_successful_inserts}, "
                   f"Files with errors: {len(set(error_files))}")
    print(summary_msg)
    logging.info(summary_msg)
    if error_files:
        logging.error(f"Files with errors: {set(error_files)}")

if __name__ == "__main__":
    main()
