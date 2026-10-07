import os
import random
import datetime
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

# Import modules
from modules import utils, auth, quiz_manager, quiz_taker, excel_handler, performance_analyzer

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_replace_me_too')
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file upload size
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Helper Functions & Decorators ---
def login_required(role=None):
    """Decorator to require login and optionally a specific role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_email' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login', next=request.url))
            if role and session.get('user_role') != role:
                flash(f'Access denied: {role.capitalize()} role required.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.template_filter('format_datetime')
def format_datetime_filter(value, format="%Y-%m-%d %H:%M"):
    """Jinja2 filter to format datetime strings."""
    if value:
        try:
            dt_obj = datetime.datetime.fromisoformat(value)
            return dt_obj.strftime(format)
        except (ValueError, TypeError):
            return value
    return ""


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- HTTP Error Handlers ---
@app.errorhandler(400)
def bad_request_error(error):
    logging.warning(f"400 Bad Request: {error}")
    return render_template('400.html', error_message=getattr(error, 'description', str(error))), 400


@app.errorhandler(403)
def forbidden_error(error):
    logging.warning(f"403 Forbidden: {error}")
    return render_template('403.html', error_message=getattr(error, 'description', str(error))), 403


@app.errorhandler(404)
def not_found_error(error):
    logging.warning(f"404 Not Found: {request.path}")
    return render_template('404.html', error_message=getattr(error, 'description', "The requested URL was not found on this server.")), 404


@app.errorhandler(413)
def request_entity_too_large_error(error):
    logging.warning("413 Request Entity Too Large: Uploaded file exceeds 16MB limit.")
    return render_template('413.html'), 413


@app.errorhandler(500)
def internal_server_error(error):
    logging.error(f"500 Internal Server Error: {error}", exc_info=True)
    return render_template('500.html', error_message="An internal server error occurred."), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    # Pass through standard HTTPExceptions so their specific handlers or status codes are honored
    if isinstance(e, HTTPException):
        return render_template('500.html', error_message=e.description), e.code
    logging.error(f"Unhandled Exception occurred: {e}", exc_info=True)
    return render_template('500.html', error_message="An unexpected system error occurred. Please try again later."), 500


# --- Root / Landing Route ---
@app.route('/')
def index():
    try:
        if 'user_email' in session:
            if session.get('user_role') == 'student':
                return redirect(url_for('student_dashboard'))
            elif session.get('user_role') == 'teacher':
                return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('login'))
    except Exception as e:
        logging.error(f"Error in index route: {e}")
        return redirect(url_for('login'))


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'user_email' in session:
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip().lower()
            password = request.form.get('password') or ''

            if not email or not password:
                flash('Please enter both email and password.', 'error')
                return render_template('login.html')

            user = auth.login_web(email, password)

            if user:
                session['user_email'] = user['email']
                session['user_role'] = user['role']
                if user['role'] == 'student':
                    session['user_prn'] = user.get('prn')
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password. Please verify your credentials.', 'error')
                return render_template('login.html')

        return render_template('login.html')
    except Exception as e:
        logging.error(f"Login error: {e}")
        flash('An unexpected error occurred during login. Please try again.', 'error')
        return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if 'user_email' in session:
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = (request.form.get('email') or '').strip().lower()
            prn = (request.form.get('prn') or '').strip()
            password = request.form.get('password') or ''
            confirm_password = request.form.get('confirm_password') or ''

            if not email or not password:
                flash('Email and password fields are required.', 'error')
                return render_template('register.html', email=email, prn=prn)

            user, message = auth.register_user_web(email, password, confirm_password, prn)

            if user:
                flash(message, 'success')
                return redirect(url_for('login'))
            else:
                flash(message, 'error')
                return render_template('register.html', email=email, prn=prn)

        return render_template('register.html')
    except Exception as e:
        logging.error(f"Registration error: {e}")
        flash('An error occurred during registration. Please try again.', 'error')
        return render_template('register.html')


@app.route('/logout')
@login_required()
def logout():
    try:
        session.clear()
        flash('You have been successfully logged out.', 'info')
    except Exception as e:
        logging.error(f"Logout error: {e}")
    return redirect(url_for('login'))


# --- Student Routes ---
@app.route('/student/dashboard')
@login_required(role='student')
def student_dashboard():
    try:
        student_prn = session.get('user_prn')
        if not student_prn:
            flash('Error: Student PRN not found in session. Please log in again.', 'error')
            return redirect(url_for('logout'))

        available = quiz_taker.get_available_quizzes(student_prn) or []
        completed = quiz_taker.get_completed_quizzes(student_prn) or []

        return render_template('student_dashboard.html',
                               available_quizzes=available,
                               completed_quizzes=completed)
    except Exception as e:
        logging.error(f"Error loading student dashboard: {e}")
        flash('Unable to load dashboard data. Please try again.', 'error')
        return render_template('student_dashboard.html', available_quizzes=[], completed_quizzes=[])


@app.route('/quiz/take/<quiz_id>', methods=['GET', 'POST'])
@login_required(role='student')
def take_quiz(quiz_id):
    try:
        student_prn = session.get('user_prn')
        quiz_details = quiz_manager.get_quiz_details(quiz_id)

        if not quiz_details:
            flash("Quiz not found or has been removed.", 'error')
            return redirect(url_for('student_dashboard'))

        completed_quizzes = quiz_taker.get_completed_quizzes(student_prn) or []
        if any(c.get('quiz_id') == quiz_id for c in completed_quizzes):
            flash("You have already completed this quiz.", 'info')
            return redirect(url_for('student_dashboard'))

        quiz_session_key = f'quiz_{quiz_id}'

        if request.method == 'GET' and quiz_session_key not in session:
            questions, _ = quiz_manager.get_questions_for_quiz(quiz_id)
            if questions is None:
                flash("Error loading questions for this quiz.", 'error')
                return redirect(url_for('student_dashboard'))
            if not questions:
                flash("This quiz currently contains no questions.", 'info')
                return redirect(url_for('student_dashboard'))

            random.shuffle(questions)
            session[quiz_session_key] = {
                'questions': questions,
                'current_q_index': 0,
                'score': 0,
                'total_marks': sum(q.get('marks', 0) for q in questions),
                'answers': {}
            }
            session.modified = True

        if quiz_session_key not in session:
            flash("Quiz session expired or not found. Please start again.", 'error')
            return redirect(url_for('student_dashboard'))

        quiz_state = session[quiz_session_key]
        current_index = quiz_state.get('current_q_index', 0)
        questions = quiz_state.get('questions', [])

        if not questions:
            session.pop(quiz_session_key, None)
            flash("No questions available for this quiz.", 'error')
            return redirect(url_for('student_dashboard'))

        if request.method == 'POST':
            if current_index >= len(questions):
                flash("Attempted to answer after quiz was already finished.", "warning")
                return redirect(url_for('student_dashboard'))

            submitted_answer = request.form.get('answer')
            current_question = questions[current_index]

            if submitted_answer:
                quiz_state['answers'][current_question['q_id']] = submitted_answer
                if submitted_answer == current_question.get('correct_answer'):
                    quiz_state['score'] += current_question.get('marks', 0)

                quiz_state['current_q_index'] += 1
                session[quiz_session_key] = quiz_state
                session.modified = True
                current_index += 1
            else:
                flash("Please select an answer before continuing.", "error")

        # Check if quiz finished or display next question
        if current_index >= len(questions):
            final_score = quiz_state.get('score', 0)
            final_total_marks = sum(q.get('marks', 0) for q in questions)
            student_answers = quiz_state.get('answers', {})

            # Save Result
            try:
                results = utils.load_data(utils.RESULTS_FILE, [])
                new_result = {
                    "result_id": utils.generate_unique_id("res_"),
                    "student_prn": student_prn,
                    "quiz_id": quiz_id,
                    "score": final_score,
                    "total_marks": final_total_marks,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "answers": student_answers
                }
                results.append(new_result)
                saved = utils.save_data(utils.RESULTS_FILE, results)
            except Exception as e:
                logging.error(f"Error saving quiz result: {e}")
                saved = False

            feedback = quiz_taker.generate_feedback(final_score, final_total_marks)
            session.pop(quiz_session_key, None)  # Clean up session
            session.modified = True

            if saved:
                flash("Quiz submitted successfully!", 'success')
            else:
                flash("Quiz finished, but there was an error recording your score.", 'error')

            return render_template('quiz_result.html',
                                   score=final_score,
                                   total_marks=final_total_marks,
                                   feedback=feedback,
                                   quiz_title=quiz_details.get('title', 'Quiz'),
                                   subject_id=quiz_details.get('subject_id', 'N/A'))
        else:
            # Display current question
            current_question = dict(questions[current_index])
            raw_options = current_question.get('options', [])
            display_options = random.sample(raw_options, len(raw_options)) if raw_options else []
            current_question['options'] = display_options

            return render_template('take_quiz.html',
                                   quiz_details=quiz_details,
                                   current_question=current_question,
                                   current_q_index=current_index,
                                   total_questions=len(questions))
    except Exception as e:
        logging.error(f"Error in take_quiz route: {e}", exc_info=True)
        flash("An error occurred during the quiz session.", 'error')
        return redirect(url_for('student_dashboard'))


# --- Teacher Routes ---
@app.route('/teacher/dashboard')
@login_required(role='teacher')
def teacher_dashboard():
    try:
        all_quizzes = utils.load_data(utils.QUIZZES_FILE, []) or []
        questions_data = utils.load_data(utils.QUESTIONS_FILE, {}) or {}
        subjects = {sid: len(qlist) for sid, qlist in questions_data.items() if isinstance(qlist, list)}

        return render_template('teacher_dashboard.html',
                               all_quizzes=all_quizzes,
                               subjects=subjects)
    except Exception as e:
        logging.error(f"Error loading teacher dashboard: {e}")
        flash("Unable to load teacher dashboard data.", 'error')
        return render_template('teacher_dashboard.html', all_quizzes=[], subjects={})


@app.route('/teacher/quiz/create/manual', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_manual():
    try:
        if request.method == 'POST':
            subject_id = (request.form.get('subject_id') or '').strip().upper()
            quiz_title = (request.form.get('quiz_title') or '').strip()
            q_ids_str = request.form.get('question_ids') or ''

            if not all([subject_id, quiz_title, q_ids_str]):
                flash('All fields (Subject ID, Title, Question IDs) are required.', 'error')
                return redirect(request.url)

            # Validate and parse question IDs
            question_ids = [qid.strip() for qid in q_ids_str.split(',') if qid.strip()]
            if not question_ids:
                flash('Please provide at least one valid Question ID.', 'error')
                return redirect(request.url)

            # Remove duplicate question IDs while preserving order
            question_ids = list(dict.fromkeys(question_ids))

            # Validate if question IDs actually exist for the subject
            subject_questions = quiz_manager.get_questions_by_subject(subject_id) or []
            all_subject_qids = {q['q_id'] for q in subject_questions if 'q_id' in q}
            valid_qids = [qid for qid in question_ids if qid in all_subject_qids]
            invalid_qids = [qid for qid in question_ids if qid not in all_subject_qids]

            if invalid_qids:
                flash(f'Warning: The following Question IDs were not found for subject {subject_id} and were ignored: {", ".join(invalid_qids)}', 'warning')

            if not valid_qids:
                flash(f'None of the provided Question IDs were valid for subject {subject_id}. Quiz not created.', 'error')
                return redirect(request.url)

            # Calculate total marks for valid questions
            qid_to_marks = {q['q_id']: q.get('marks', 0) for q in subject_questions}
            total_marks = sum(qid_to_marks.get(qid, 0) for q in valid_qids)

            # Create the quiz using the validated IDs
            quiz_id = quiz_manager.create_quiz(quiz_title, subject_id, session['user_email'], valid_qids, total_marks)
            if quiz_id:
                flash(f'Quiz "{quiz_title}" created successfully!', 'success')
                return redirect(url_for('teacher_dashboard'))
            else:
                flash('Error creating the quiz. Please check logs or try again.', 'error')
                return redirect(request.url)

        return render_template('create_quiz_manual.html')
    except Exception as e:
        logging.error(f"Error in create_quiz_manual: {e}", exc_info=True)
        flash("An unexpected error occurred while creating the manual quiz.", 'error')
        return render_template('create_quiz_manual.html')


@app.route('/teacher/quiz/create/excel', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_excel():
    if request.method == 'POST':
        subject_id = (request.form.get('subject_id') or '').strip().upper()
        create_quiz_flag = request.form.get('create_quiz_now') == 'yes'
        quiz_title = (request.form.get('quiz_title') or '').strip()

        if not subject_id:
            flash('Subject ID is required.', 'error')
            return redirect(request.url)

        if 'excel_file' not in request.files:
            flash('No file was uploaded.', 'error')
            return redirect(request.url)

        file = request.files['excel_file']
        if not file or file.filename == '':
            flash('No file selected. Please choose a valid .xlsx file.', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file format. Only Microsoft Excel (.xlsx) spreadsheets are allowed.', 'error')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(filepath)
            questions_from_excel = excel_handler.read_questions_from_excel(filepath)

            if questions_from_excel is None:
                flash('Error reading questions from Excel. Please verify that all required columns are present and properly formatted.', 'error')
            elif not questions_from_excel:
                flash('No valid questions found in the Excel file.', 'warning')
            else:
                added_q_ids = []
                total_marks_added = 0
                success_count = 0
                for q_data in questions_from_excel:
                    q_id = quiz_manager.add_question(
                        subject_id=subject_id,
                        text=q_data['text'],
                        options=q_data['options'],
                        correct_answer=q_data['correct_answer'],
                        marks=q_data['marks']
                    )
                    if q_id:
                        added_q_ids.append(q_id)
                        total_marks_added += q_data['marks']
                        success_count += 1

                flash(f'Successfully imported {success_count} of {len(questions_from_excel)} questions into Subject ID: {subject_id}.', 'info')

                if create_quiz_flag and added_q_ids:
                    if not quiz_title:
                        quiz_title = f"{subject_id} Quiz from {filename}"
                    quiz_id = quiz_manager.create_quiz(quiz_title, subject_id, session['user_email'], added_q_ids, total_marks_added)
                    if quiz_id:
                        flash(f"Quiz '{quiz_title}' created successfully!", 'success')
                    else:
                        flash("Questions were added, but failed to create the quiz.", 'error')

                return redirect(url_for('teacher_dashboard'))
        except Exception as e:
            logging.error(f"Error handling Excel upload: {e}", exc_info=True)
            flash(f"An error occurred while processing the Excel file: {e}", 'error')
        finally:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError as err:
                    logging.warning(f"Could not remove temporary file {filepath}: {err}")

        return redirect(url_for('teacher_dashboard'))

    return render_template('create_quiz_excel.html')


@app.route('/teacher/quiz/create/smart', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_smart():
    try:
        available_subjects = quiz_manager.get_all_subject_ids() or []

        if request.method == 'POST':
            subject_id = (request.form.get('subject_id') or '').strip().upper()
            title_prefix = (request.form.get('title_prefix') or 'Smart Quiz').strip()

            try:
                target_marks = int(request.form.get('target_marks', '0'))
            except ValueError:
                flash('Invalid target marks. Please enter a valid positive number.', 'error')
                return render_template('create_quiz_smart.html', available_subjects=available_subjects)

            if not subject_id or target_marks <= 0:
                flash('Subject ID and positive target marks are required.', 'error')
                return render_template('create_quiz_smart.html', available_subjects=available_subjects)

            quiz_id = quiz_manager.generate_smart_quiz(subject_id, target_marks, session['user_email'], title_prefix)

            if quiz_id:
                created_quiz = quiz_manager.get_quiz_details(quiz_id)
                title = created_quiz.get('title', 'Smart Quiz') if created_quiz else 'Smart Quiz'
                flash(f'Smart quiz "{title}" generated successfully!', 'success')
                return redirect(url_for('teacher_dashboard'))
            else:
                flash(f'Failed to generate smart quiz for subject {subject_id}. Check if there are sufficient questions with matching marks.', 'error')
                return render_template('create_quiz_smart.html', available_subjects=available_subjects)

        return render_template('create_quiz_smart.html', available_subjects=available_subjects)
    except Exception as e:
        logging.error(f"Error in create_quiz_smart: {e}", exc_info=True)
        flash("An error occurred during smart quiz generation.", 'error')
        return render_template('create_quiz_smart.html', available_subjects=[])


@app.route('/teacher/questions/add', methods=['GET', 'POST'])
@login_required(role='teacher')
def add_questions_manual_form():
    subject_preset = request.args.get('subject_id', '')

    if request.method == 'POST':
        try:
            subject_id = (request.form.get('subject_id') or '').strip().upper()
            text = (request.form.get('question_text') or '').strip()
            opt_a = (request.form.get('option_a') or '').strip()
            opt_b = (request.form.get('option_b') or '').strip()
            opt_c = (request.form.get('option_c') or '').strip()
            opt_d = (request.form.get('option_d') or '').strip()
            correct_letter = (request.form.get('correct_option_letter') or '').upper().strip()

            try:
                marks = int(request.form.get('marks', '0'))
            except ValueError:
                marks = 0

            if not all([subject_id, text, opt_a, opt_b, opt_c, opt_d, correct_letter]) or marks <= 0:
                flash('All fields are required, and marks must be a positive number.', 'error')
                return render_template('add_questions_manual.html',
                                       subject_id_preset=subject_id,
                                       question_text=text, option_a=opt_a, option_b=opt_b,
                                       option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                       marks=marks)

            if correct_letter not in ['A', 'B', 'C', 'D']:
                flash('Invalid correct option letter. Must be A, B, C, or D.', 'error')
                return render_template('add_questions_manual.html',
                                       subject_id_preset=subject_id,
                                       question_text=text, option_a=opt_a, option_b=opt_b,
                                       option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                       marks=marks)

            options = [opt_a, opt_b, opt_c, opt_d]
            correct_mapping = {'A': opt_a, 'B': opt_b, 'C': opt_c, 'D': opt_d}
            correct_answer = correct_mapping[correct_letter]

            q_id = quiz_manager.add_question(subject_id, text, options, correct_answer, marks)

            if q_id:
                flash(f'Question added successfully to {subject_id}!', 'success')
                return redirect(url_for('add_questions_manual_form', subject_id=subject_id))
            else:
                flash('Error adding question. Please check data files or server logs.', 'error')
                return render_template('add_questions_manual.html',
                                       subject_id_preset=subject_id,
                                       question_text=text, option_a=opt_a, option_b=opt_b,
                                       option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                       marks=marks)
        except Exception as e:
            logging.error(f"Error in add_questions_manual_form: {e}", exc_info=True)
            flash("An error occurred while saving the question.", 'error')
            return render_template('add_questions_manual.html', subject_id_preset=subject_preset)

    return render_template('add_questions_manual.html', subject_id_preset=subject_preset)


@app.route('/teacher/analysis')
@login_required(role='teacher')
def view_analysis():
    try:
        quiz_id = request.args.get('quiz_id')
        if not quiz_id:
            flash("Please select a quiz to analyze.", "warning")
            return redirect(url_for('teacher_dashboard'))

        analysis_data, error_msg = performance_analyzer.analyze_quiz_performance(quiz_id)

        if error_msg and not analysis_data:
            flash(f"Error generating analysis: {error_msg}", 'error')
            return redirect(url_for('teacher_dashboard'))

        return render_template('performance_analysis.html', analysis=analysis_data)
    except Exception as e:
        logging.error(f"Error in view_analysis: {e}", exc_info=True)
        flash("An error occurred while analyzing quiz performance.", 'error')
        return redirect(url_for('teacher_dashboard'))


# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)