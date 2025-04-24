# modules/auth.py
from . import utils
# Remove getpass import if present

# --- User Management ---

def register_user_web(email, password, confirm_password, prn=None):
    """Registers a new user (web version). Returns user object or None."""
    email = email.strip().lower()
    role = None

    if email.endswith(utils.STUDENT_DOMAIN):
        role = "student"
        if not prn or not prn.strip():
            return None, "PRN cannot be empty for students."
        prn = prn.strip()
    elif email.endswith(utils.TEACHER_DOMAIN):
        role = "teacher"
        prn = None # Ensure PRN is None for teachers
    else:
        return None, f"Invalid email domain. Must end with {utils.STUDENT_DOMAIN} or {utils.TEACHER_DOMAIN}"

    if password != confirm_password:
        return None, "Passwords do not match."

    if not password:
        return None, "Password cannot be empty."

    users = utils.load_data(utils.USERS_FILE, [])
    if any(user['email'] == email for user in users):
        return None, "Email already registered."

    hashed_pw = utils.hash_password(password)
    new_user = {
        "user_id": utils.generate_unique_id("user_"),
        "email": email,
        "password_hash": hashed_pw,
        "role": role,
    }
    if role == "student":
        new_user["prn"] = prn

    users.append(new_user)
    if utils.save_data(utils.USERS_FILE, users):
        utils.logging.info(f"{role.capitalize()} registered successfully: {email}")
        return new_user, f"{role.capitalize()} registered successfully!"
    else:
        utils.logging.error(f"Error saving user data for {email}")
        return None, "Error saving user data."


def login_web(email, password):
    """Logs in a user (web version) and returns user data or None."""
    email = email.strip().lower()
    if not email or not password:
        return None # Basic validation

    users = utils.load_data(utils.USERS_FILE, [])
    user_found = None
    for user in users:
        if user['email'] == email:
            user_found = user
            break

    if user_found and utils.check_password(user_found['password_hash'], password):
        # Domain checks (remain the same)
        if user_found['role'] == 'student' and not email.endswith(utils.STUDENT_DOMAIN):
            utils.logging.warning(f"Login failed: Role/domain mismatch for student {email}")
            return None
        if user_found['role'] == 'teacher' and not email.endswith(utils.TEACHER_DOMAIN):
            utils.logging.warning(f"Login failed: Role/domain mismatch for teacher {email}")
            return None

        utils.logging.info(f"Login successful for {email}")
        return user_found # Return the user dictionary
    else:
        utils.logging.warning(f"Login failed for {email} (invalid email/password)")
        return None