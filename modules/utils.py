# modules/utils.py (Modify the PLOTS_DIR line)
import json
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from filelock import FileLock
import logging
import datetime # Make sure datetime is imported

# --- Configuration ---
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
QUESTIONS_FILE = os.path.join(DATA_DIR, "questions.json")
QUIZZES_FILE = os.path.join(DATA_DIR, "quizzes.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
# CHANGE THIS LINE:
PLOTS_DIR = os.path.join("static", "plots") # Directory within static folder

# Ensure data and plot directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True) # This now creates static/plots

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- File I/O with Locking ---
# (load_data and save_data functions remain the same)
def load_data(filepath, default_data=None):
    """Loads JSON data from a file. Creates file if it doesn't exist."""
    if default_data is None:
        default_data = [] # Default to list for users, quizzes, results
        if 'questions' in filepath:
             default_data = {} # Default to dict for questions

    lock_path = filepath + ".lock"
    lock = FileLock(lock_path)
    try:
        with lock:
            if not os.path.exists(filepath):
                logging.info(f"File {filepath} not found. Creating with default data.")
                with open(filepath, 'w') as f:
                    json.dump(default_data, f, indent=4)
                return default_data
            else:
                with open(filepath, 'r') as f:
                    try:
                        data = json.load(f)
                        # Basic validation: ensure questions is dict, others are list
                        if 'questions' in filepath and not isinstance(data, dict):
                            logging.warning(f"Data in {filepath} is not a dict. Resetting.")
                            return default_data
                        elif 'questions' not in filepath and not isinstance(data, list):
                             logging.warning(f"Data in {filepath} is not a list. Resetting.")
                             return default_data
                        return data
                    except json.JSONDecodeError:
                        logging.error(f"Error decoding JSON from {filepath}. Returning default data.")
                        return default_data
    except Exception as e:
        logging.error(f"Error loading data from {filepath}: {e}")
        return default_data

def save_data(filepath, data):
    """Saves data to a JSON file with file locking."""
    lock_path = filepath + ".lock"
    lock = FileLock(lock_path)
    try:
        with lock:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            # logging.info(f"Data saved to {filepath}") # Optional: uncomment for verbose logging
            return True
    except Exception as e:
        logging.error(f"Error saving data to {filepath}: {e}")
        return False

# --- Utility Functions ---
# (generate_unique_id, hash_password, check_password remain the same)
def generate_unique_id(prefix=""):
    """Generates a unique ID."""
    return prefix + str(uuid.uuid4())

def hash_password(password):
    """Generates a secure hash for a password."""
    return generate_password_hash(password)

def check_password(hashed_password, password):
    """Checks if the provided password matches the hash."""
    return check_password_hash(hashed_password, password)

def get_plot_path(filename):
    """Returns the full path for saving a plot."""
    # This path is used by matplotlib for saving
    return os.path.join(PLOTS_DIR, filename)

def get_plot_url(filename):
    """Returns the URL path for accessing the plot in HTML."""
    # Use forward slashes for URL, relative to static folder
    return f"static/plots/{filename}"

# --- Domain Constants ---
STUDENT_DOMAIN = "@gst.sies.edu.in"
TEACHER_DOMAIN = "@sies.edu.in"