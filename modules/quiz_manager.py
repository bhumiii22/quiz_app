import random
from . import utils

# --- Question Management ---

def add_question(subject_id, text, options, correct_answer, marks):
    """Adds a single question to the questions data."""
    questions_data = utils.load_data(utils.QUESTIONS_FILE, {}) # Ensure default is dict
    subject_id = subject_id.strip().upper() # Standardize subject ID

    if not all([text, options, correct_answer is not None, marks > 0]):
         print("Error: Invalid question data provided.")
         return None

    # Ensure correct_answer is one of the options
    if correct_answer not in options:
        print(f"Error: Correct answer '{correct_answer}' is not in the provided options {options}.")
        return None

    new_question = {
        "q_id": utils.generate_unique_id("q_"),
        "text": text,
        "options": options,
        "correct_answer": correct_answer,
        "marks": marks
    }

    if subject_id not in questions_data:
        questions_data[subject_id] = []

    questions_data[subject_id].append(new_question)

    if utils.save_data(utils.QUESTIONS_FILE, questions_data):
        print(f"Question added successfully to Subject ID: {subject_id}")
        return new_question["q_id"]
    else:
        print("Error saving question.")
        return None

def get_questions_by_subject(subject_id):
    """Retrieves all questions for a given subject ID."""
    questions_data = utils.load_data(utils.QUESTIONS_FILE, {})
    subject_id = subject_id.strip().upper()
    return questions_data.get(subject_id, [])

def get_all_subject_ids():
    """Returns a list of all available subject IDs."""
    questions_data = utils.load_data(utils.QUESTIONS_FILE, {})
    return list(questions_data.keys())

# --- Quiz Management ---

def create_quiz(title, subject_id, creator_email, question_ids, total_marks):
    """Creates a new quiz entry."""
    if not all([title, subject_id, creator_email, question_ids]):
        print("Error: Missing data for quiz creation.")
        return None

    quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    subject_id = subject_id.strip().upper()

    new_quiz = {
        "quiz_id": utils.generate_unique_id("qz_"),
        "title": title.strip(),
        "subject_id": subject_id,
        "creator_email": creator_email,
        "question_ids": question_ids,
        "total_marks": total_marks, # Store total marks for the quiz
        "created_at": utils.datetime.datetime.now().isoformat() # Optional: track creation time
    }

    quizzes.append(new_quiz)
    if utils.save_data(utils.QUIZZES_FILE, quizzes):
        print(f"Quiz '{title}' created successfully with ID: {new_quiz['quiz_id']}")
        return new_quiz['quiz_id']
    else:
        print("Error saving quiz.")
        return None

def get_quiz_details(quiz_id):
    """Retrieves metadata for a specific quiz."""
    quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    for quiz in quizzes:
        if quiz['quiz_id'] == quiz_id:
            return quiz
    return None

def get_questions_for_quiz(quiz_id):
    """Retrieves the actual question objects associated with a quiz ID."""
    quiz_details = get_quiz_details(quiz_id)
    if not quiz_details:
        return None, None # Quiz not found

    question_ids = quiz_details.get("question_ids", [])
    subject_id = quiz_details.get("subject_id")

    if not subject_id:
        utils.logging.error(f"Quiz {quiz_id} is missing subject_id.")
        return None, None

    all_subject_questions = get_questions_by_subject(subject_id)
    if not all_subject_questions:
         utils.logging.warning(f"No questions found for subject {subject_id} associated with quiz {quiz_id}.")
         return [], quiz_details # Return empty list but quiz details

    quiz_questions = [q for q in all_subject_questions if q['q_id'] in question_ids]

    # Ensure the order matches question_ids if needed, though usually not critical for taking the quiz
    # Reordering can be complex if questions were deleted; simpler to just return matching ones.
    if len(quiz_questions) != len(question_ids):
         utils.logging.warning(f"Mismatch in question count for quiz {quiz_id}. Expected {len(question_ids)}, found {len(quiz_questions)}.")
         # Potentially filter question_ids in quiz_details to match existing ones if needed elsewhere

    return quiz_questions, quiz_details


def generate_smart_quiz(subject_id, target_marks, creator_email, title_prefix="Smart Quiz"):
    """Generates a quiz with questions randomly selected to meet target marks."""
    subject_id = subject_id.strip().upper()
    available_questions = get_questions_by_subject(subject_id)

    if not available_questions:
        print(f"Error: No questions found for Subject ID: {subject_id}")
        return None

    # Check if target marks are achievable
    total_available_marks = sum(q['marks'] for q in available_questions)
    if total_available_marks < target_marks:
        print(f"Error: Cannot generate quiz of {target_marks} marks. Only {total_available_marks} marks available for {subject_id}.")
        return None
    if target_marks <= 0:
        print("Error: Target marks must be positive.")
        return None

    # Shuffle questions to ensure randomness
    random.shuffle(available_questions)

    selected_questions = []
    selected_q_ids = []
    current_marks = 0

    # Strategy: Try to get as close as possible without necessarily exceeding
    # Alternative: Could try to exactly match, which is a variation of the subset sum problem (harder)
    for question in available_questions:
        # Add if it doesn't exceed the target (or fits within a small tolerance if desired)
        if current_marks + question['marks'] <= target_marks:
             selected_questions.append(question)
             selected_q_ids.append(question['q_id'])
             current_marks += question['marks']
             # If exact match found, break early
             if current_marks == target_marks:
                 break

    # If after iterating, we are still below target, maybe add the smallest possible question
    # that gets us closest (optional complexity). For now, we accept being potentially under target.
    if not selected_q_ids:
         print("Error: Could not select any questions (possibly all questions have marks > target marks).")
         return None

    print(f"Selected {len(selected_q_ids)} questions totaling {current_marks} marks (Target: {target_marks}).")

    # Create the quiz
    quiz_title = f"{title_prefix} - {subject_id} ({current_marks} Marks)"
    return create_quiz(quiz_title, subject_id, creator_email, selected_q_ids, current_marks)