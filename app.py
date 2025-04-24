# ... (Keep imports and setup from previous app.py) ...
import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
import datetime

# Import your modules
from modules import utils, auth, quiz_manager, quiz_taker, excel_handler, performance_analyzer

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_replace_me_too')
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# --- Helper Functions & Decorators (keep login_required, format_datetime) ---
def login_required(role=None):
    """Decorator to require login and optionally a specific role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_email' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
            if role and session.get('user_role') != role:
                flash(f'You do not have permission ({role} required).', 'error')
                return redirect(url_for('index')) # Redirect to a safe page
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
    return '.' in filename and          filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# --- Routes ---

@app.route('/')
def index():
    # ... (index route remains the same) ...
    if 'user_email' in session:
        if session.get('user_role') == 'student':
            return redirect(url_for('student_dashboard'))
        elif session.get('user_role') == 'teacher':
            return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('login')) # Default to login if not logged in


# --- Authentication Routes (login, register, logout remain the same) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (login route remains the same) ...
    if 'user_email' in session:
        return redirect(url_for('index')) # Already logged in

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = auth.login_web(email, password)

        if user:
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            if user['role'] == 'student':
                session['user_prn'] = user.get('prn')
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (register route remains the same) ...
    if 'user_email' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        prn = request.form.get('prn') # May be empty
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        user, message = auth.register_user_web(email, password, confirm_password, prn)

        if user:
            flash(message, 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
            return render_template('register.html', email=email, prn=prn)

    return render_template('register.html')

@app.route('/logout')
@login_required()
def logout():
    # ... (logout route remains the same) ...
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --- Student Routes (student_dashboard, take_quiz, quiz_result remain the same) ---
@app.route('/student/dashboard')
@login_required(role='student')
def student_dashboard():
    # ... (student_dashboard route remains the same) ...
    student_prn = session.get('user_prn')
    if not student_prn:
        flash('Error: Student PRN not found in session.', 'error')
        return redirect(url_for('logout'))

    available = quiz_taker.get_available_quizzes(student_prn)
    completed = quiz_taker.get_completed_quizzes(student_prn)

    return render_template('student_dashboard.html',
                           available_quizzes=available,
                           completed_quizzes=completed)


@app.route('/quiz/take/<quiz_id>', methods=['GET', 'POST'])
@login_required(role='student')
def take_quiz(quiz_id):
    # ... (take_quiz route remains the same) ...
    student_prn = session.get('user_prn')
    quiz_details = quiz_manager.get_quiz_details(quiz_id)

    if not quiz_details:
        flash("Quiz not found.", 'error')
        return redirect(url_for('student_dashboard'))

    completed_quizzes = quiz_taker.get_completed_quizzes(student_prn)
    if any(c['quiz_id'] == quiz_id for c in completed_quizzes):
         flash("You have already completed this quiz.", 'info')
         return redirect(url_for('student_dashboard'))

    quiz_session_key = f'quiz_{quiz_id}'

    if request.method == 'GET' and quiz_session_key not in session: # Start quiz only if not already in progress
        questions, _ = quiz_manager.get_questions_for_quiz(quiz_id)
        if questions is None:
             flash("Error loading questions for this quiz.", 'error')
             return redirect(url_for('student_dashboard'))
        if not questions:
            flash("This quiz currently has no questions.", 'info')
            return redirect(url_for('student_dashboard'))

        random.shuffle(questions)
        session[quiz_session_key] = {
            'questions': questions, 'current_q_index': 0, 'score': 0,
            'total_marks': 0, 'answers': {}
        }
        session.modified = True

    if quiz_session_key not in session:
         flash("Quiz session not found. Please start again.", 'error')
         return redirect(url_for('student_dashboard'))

    quiz_state = session[quiz_session_key]
    current_index = quiz_state['current_q_index']
    questions = quiz_state['questions']

    if request.method == 'POST':
        if current_index >= len(questions):
             flash("Attempted to answer after quiz finished.", "warning")
             return redirect(url_for('student_dashboard'))

        submitted_answer = request.form.get('answer')
        current_question = questions[current_index]

        if submitted_answer:
            quiz_state['answers'][current_question['q_id']] = submitted_answer
            # Score calculation happens here based on current_question['correct_answer']
            if submitted_answer == current_question['correct_answer']:
                quiz_state['score'] += current_question['marks']
            # Update total marks potentially encountered so far (optional, final recalc is safer)
            # quiz_state['total_marks'] += current_question['marks']

            quiz_state['current_q_index'] += 1
            session[quiz_session_key] = quiz_state
            session.modified = True
            current_index += 1
        else:
            flash("Please select an answer.", "error")
            # Re-render same question by falling through to the GET-like logic below

    # Check if quiz finished or display next question
    if current_index >= len(questions):
        final_score = quiz_state['score']
        # Recalculate total marks accurately from the original question list in session
        final_total_marks = sum(q['marks'] for q in questions)
        student_answers = quiz_state['answers']

        # --- Save Result ---
        results = utils.load_data(utils.RESULTS_FILE, [])
        new_result = {
            "result_id": utils.generate_unique_id("res_"), "student_prn": student_prn,
            "quiz_id": quiz_id, "score": final_score, "total_marks": final_total_marks,
            "timestamp": utils.datetime.datetime.now().isoformat(), "answers": student_answers
        }
        results.append(new_result)
        saved = utils.save_data(utils.RESULTS_FILE, results)
        # --- End Save Result ---

        feedback = quiz_taker.generate_feedback(final_score, final_total_marks)
        session.pop(quiz_session_key, None) # Clean up session
        session.modified = True

        if saved:
            flash("Quiz submitted successfully!", 'success')
        else:
            flash("Quiz finished, but there was an error saving your result.", 'error')

        return render_template('quiz_result.html',
                               score=final_score, total_marks=final_total_marks,
                               feedback=feedback, quiz_title=quiz_details['title'],
                               subject_id=quiz_details['subject_id'])
    else:
        # Display current question
        current_question = questions[current_index]
        display_options = random.sample(current_question['options'], len(current_question['options']))
        current_question['options'] = display_options # Use shuffled options for template

        return render_template('take_quiz.html',
                               quiz_details=quiz_details, current_question=current_question,
                               current_q_index=current_index, total_questions=len(questions))

# --- Teacher Routes ---
@app.route('/teacher/dashboard')
@login_required(role='teacher')
def teacher_dashboard():
    # ... (teacher_dashboard route remains the same) ...
    all_quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    questions_data = utils.load_data(utils.QUESTIONS_FILE, {})
    subjects = {sid: len(qlist) for sid, qlist in questions_data.items()}

    return render_template('teacher_dashboard.html',
                           all_quizzes=all_quizzes,
                           subjects=subjects)


# --- NEW/UPDATED Teacher Routes ---

@app.route('/teacher/quiz/create/manual', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_manual():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', '').strip().upper()
        quiz_title = request.form.get('quiz_title', '').strip()
        q_ids_str = request.form.get('question_ids', '')

        if not all([subject_id, quiz_title, q_ids_str]):
            flash('All fields (Subject ID, Title, Question IDs) are required.', 'error')
            return redirect(request.url)

        # Validate and parse question IDs
        question_ids = [qid.strip() for qid in q_ids_str.split(',') if qid.strip()]
        if not question_ids:
             flash('Please provide at least one valid Question ID.', 'error')
             return redirect(request.url)

        # Optional: Validate if question IDs actually exist for the subject
        all_subject_qids = {q['q_id'] for q in quiz_manager.get_questions_by_subject(subject_id)}
        valid_qids = [qid for qid in question_ids if qid in all_subject_qids]
        invalid_qids = [qid for qid in question_ids if qid not in all_subject_qids]

        if invalid_qids:
            flash(f'Warning: The following Question IDs were not found for subject {subject_id} and were ignored: {", ".join(invalid_qids)}', 'warning')

        if not valid_qids:
             flash(f'None of the provided Question IDs were valid for subject {subject_id}. Quiz not created.', 'error')
             return redirect(request.url)

        # Calculate total marks for valid questions
        questions_data = utils.load_data(utils.QUESTIONS_FILE, {})
        total_marks = 0
        subject_questions = questions_data.get(subject_id, [])
        qid_to_marks = {q['q_id']: q['marks'] for q in subject_questions}
        for qid in valid_qids:
            total_marks += qid_to_marks.get(qid, 0)


        # Create the quiz using the validated IDs
        quiz_id = quiz_manager.create_quiz(quiz_title, subject_id, session['user_email'], valid_qids, total_marks)
        if quiz_id:
            flash(f'Quiz "{quiz_title}" created successfully!', 'success')
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Error creating the quiz.', 'error')
            return redirect(request.url) # Stay on form page on error

    # GET request
    return render_template('create_quiz_manual.html')


@app.route('/teacher/quiz/create/excel', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_excel():
    # This route's POST logic was already mostly implemented in the previous response
    # Ensure the GET part renders the template
    if request.method == 'POST':
        # --- POST logic from previous answer ---
        subject_id = request.form.get('subject_id', '').strip().upper()
        create_quiz_flag = request.form.get('create_quiz_now') == 'yes'
        quiz_title = request.form.get('quiz_title', '').strip()

        if not subject_id:
            flash('Subject ID is required.', 'error')
            return redirect(request.url)
        if 'excel_file' not in request.files:
            flash('No file part.', 'error')
            return redirect(request.url)
        file = request.files['excel_file']
        if file.filename == '':
            flash('No selected file.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(filepath)
                questions_from_excel = excel_handler.read_questions_from_excel(filepath)

                if questions_from_excel is None:
                    flash('Error reading questions from Excel file. Check format and columns.', 'error')
                elif not questions_from_excel:
                     flash('No valid questions found in the Excel file.', 'warning')
                else:
                    added_q_ids = []
                    total_marks_added = 0
                    success_count = 0
                    for q_data in questions_from_excel:
                        q_id = quiz_manager.add_question(
                            subject_id=subject_id, text=q_data['text'],
                            options=q_data['options'], correct_answer=q_data['correct_answer'],
                            marks=q_data['marks']
                        )
                        if q_id:
                            added_q_ids.append(q_id)
                            total_marks_added += q_data['marks']
                            success_count += 1
                    flash(f'Successfully added {success_count} / {len(questions_from_excel)} questions to Subject ID: {subject_id}.', 'info')

                    if create_quiz_flag and added_q_ids:
                        if not quiz_title: quiz_title = f"{subject_id} Quiz from {filename}"
                        quiz_id = quiz_manager.create_quiz(quiz_title, subject_id, session['user_email'], added_q_ids, total_marks_added)
                        if quiz_id: flash(f"Quiz '{quiz_title}' created successfully.", 'success')
                        else: flash("Questions added, but failed to create quiz.", 'error')
                os.remove(filepath)
            except Exception as e:
                flash(f"An error occurred: {e}", 'error')
                if os.path.exists(filepath): os.remove(filepath)
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid file type. Only .xlsx allowed.', 'error')
            return redirect(request.url)
    # --- End POST Logic ---

    # GET request
    return render_template('create_quiz_excel.html')


@app.route('/teacher/quiz/create/smart', methods=['GET', 'POST'])
@login_required(role='teacher')
def create_quiz_smart():
    available_subjects = quiz_manager.get_all_subject_ids() # Get list of subjects for dropdown

    if request.method == 'POST':
        subject_id = request.form.get('subject_id', '').strip().upper()
        title_prefix = request.form.get('title_prefix', 'Smart Quiz').strip()
        try:
            target_marks = int(request.form.get('target_marks', '0'))
        except ValueError:
            flash('Invalid number for target marks.', 'error')
            return render_template('create_quiz_smart.html', available_subjects=available_subjects)

        if not subject_id or target_marks <= 0:
            flash('Subject ID and positive target marks are required.', 'error')
            return render_template('create_quiz_smart.html', available_subjects=available_subjects)

        # Call the smart generator - Adapt generate_smart_quiz if it needs modification
        # Assume it returns quiz_id on success, None on failure and prints errors/info
        # We might want it to return (quiz_id, message) instead
        quiz_id = quiz_manager.generate_smart_quiz(subject_id, target_marks, session['user_email'], title_prefix)

        if quiz_id:
             # Need to get the actual title from the created quiz if generate_smart_quiz doesn't return it
             created_quiz = quiz_manager.get_quiz_details(quiz_id)
             title = created_quiz.get('title', 'Smart Quiz') if created_quiz else 'Smart Quiz'
             flash(f'Smart quiz "{title}" generated successfully!', 'success')
             return redirect(url_for('teacher_dashboard'))
        else:
             # Error message might be printed by generate_smart_quiz,
             # or ideally returned by it. For now, a generic flash.
             flash(f'Failed to generate smart quiz. Insufficient questions or marks for subject {subject_id}?', 'error')
             return render_template('create_quiz_smart.html', available_subjects=available_subjects)


    # GET request
    return render_template('create_quiz_smart.html', available_subjects=available_subjects)


@app.route('/teacher/questions/add', methods=['GET', 'POST'])
@login_required(role='teacher')
def add_questions_manual_form():
    subject_preset = request.args.get('subject_id', '') # Allow pre-filling subject via URL param

    if request.method == 'POST':
        subject_id = request.form.get('subject_id', '').strip().upper()
        text = request.form.get('question_text', '').strip()
        opt_a = request.form.get('option_a', '').strip()
        opt_b = request.form.get('option_b', '').strip()
        opt_c = request.form.get('option_c', '').strip()
        opt_d = request.form.get('option_d', '').strip()
        correct_letter = request.form.get('correct_option_letter', '').upper()
        try:
            marks = int(request.form.get('marks', '0'))
        except ValueError:
            marks = 0

        if not all([subject_id, text, opt_a, opt_b, opt_c, opt_d, correct_letter]) or marks <= 0:
            flash('All fields are required, and marks must be positive.', 'error')
            # Re-render form with entered values
            return render_template('add_questions_manual.html', subject_id_preset=subject_id,
                                   question_text=text, option_a=opt_a, option_b=opt_b,
                                   option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                   marks=marks)

        options = [opt_a, opt_b, opt_c, opt_d]
        correct_answer = ""
        if correct_letter == 'A': correct_answer = opt_a
        elif correct_letter == 'B': correct_answer = opt_b
        elif correct_letter == 'C': correct_answer = opt_c
        elif correct_letter == 'D': correct_answer = opt_d
        else:
             flash('Invalid correct option letter.', 'error')
             return render_template('add_questions_manual.html', subject_id_preset=subject_id,
                                   question_text=text, option_a=opt_a, option_b=opt_b,
                                   option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                   marks=marks)

        # Call add_question - adapt if its return value/feedback changed
        q_id = quiz_manager.add_question(subject_id, text, options, correct_answer, marks)

        if q_id:
            flash(f'Question added successfully to {subject_id}!', 'success')
            # Redirect back to the form, maybe pre-filling the subject ID
            return redirect(url_for('add_questions_manual_form', subject_id=subject_id))
        else:
            # Assume add_question gives feedback or check for specific errors
            flash('Error adding question. Check data or logs.', 'error')
            return render_template('add_questions_manual.html', subject_id_preset=subject_id,
                                   question_text=text, option_a=opt_a, option_b=opt_b,
                                   option_c=opt_c, option_d=opt_d, correct_option_letter=correct_letter,
                                   marks=marks)

    # GET request
    return render_template('add_questions_manual.html', subject_id_preset=subject_preset)


@app.route('/teacher/analysis')
@login_required(role='teacher')
def view_analysis():
    # ... (view_analysis route remains the same) ...
    quiz_id = request.args.get('quiz_id')
    if not quiz_id:
        flash("Please select a quiz to analyze.", "warning")
        return redirect(url_for('teacher_dashboard'))

    analysis_data, error_msg = performance_analyzer.analyze_quiz_performance(quiz_id)

    if error_msg and not analysis_data: # Check if analysis function itself failed badly
        flash(f"Error generating analysis: {error_msg}", 'error')
        return redirect(url_for('teacher_dashboard'))

    return render_template('performance_analysis.html', analysis=analysis_data)


# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)