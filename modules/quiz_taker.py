import datetime
from . import utils
from . import quiz_manager

# --- Quiz Interaction for Students ---

def get_available_quizzes(student_prn):
    """Finds quizzes the student hasn't attempted yet."""
    all_quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    results = utils.load_data(utils.RESULTS_FILE, [])

    completed_quiz_ids = set()
    for result in results:
        # Ensure 'student_prn' exists and matches before adding
        if result.get('student_prn') == student_prn:
            completed_quiz_ids.add(result.get('quiz_id'))

    available_quizzes = [
        quiz for quiz in all_quizzes
        if quiz.get('quiz_id') not in completed_quiz_ids
    ]
    return available_quizzes

def get_completed_quizzes(student_prn):
    """Finds quizzes the student has already attempted, with their results."""
    results = utils.load_data(utils.RESULTS_FILE, [])
    all_quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    quiz_details_map = {q['quiz_id']: q for q in all_quizzes}

    student_results = []
    for result in results:
         if result.get('student_prn') == student_prn:
            quiz_id = result.get('quiz_id')
            quiz_info = quiz_details_map.get(quiz_id)
            # Add quiz title if available
            result_display = result.copy() # Avoid modifying original data
            if quiz_info:
                result_display['quiz_title'] = quiz_info.get('title', 'N/A')
                result_display['subject_id'] = quiz_info.get('subject_id', 'N/A')
            else:
                result_display['quiz_title'] = 'Quiz (Details Missing)'
                result_display['subject_id'] = 'N/A'

            student_results.append(result_display)

    return student_results

def start_quiz(student_prn, quiz_id):
    """Handles the process of a student taking a specific quiz."""
    questions, quiz_details = quiz_manager.get_questions_for_quiz(quiz_id)

    if questions is None:
        print("Error: Quiz not found or could not load questions.")
        return None, None, None # Score, Total Marks, Feedback

    if not questions:
        print("This quiz currently has no questions.")
        # Optionally record an attempt with score 0 or handle differently
        return 0, 0, "Quiz has no questions."

    print(f"\n--- Starting Quiz: {quiz_details.get('title', 'Untitled Quiz')} ---")
    print(f"Subject: {quiz_details.get('subject_id', 'N/A')}")
    print(f"Total Questions: {len(questions)}")
    print("-" * 30)

    score = 0
    total_marks = 0
    student_answers = {} # Store {q_id: student_answer}

    random.shuffle(questions) # Shuffle questions for each attempt

    for i, question in enumerate(questions):
        print(f"\nQ{i+1} ({question['marks']} marks): {question['text']}")
        options = question['options']
        random.shuffle(options) # Shuffle options as well
        option_map = {} # Map displayed letter (A, B, C, D) back to option text
        for j, option in enumerate(options):
            letter = chr(ord('A') + j)
            print(f"  {letter}) {option}")
            option_map[letter] = option

        while True:
            choice = input("Your answer (A/B/C/D): ").strip().upper()
            if choice in option_map:
                chosen_answer = option_map[choice]
                student_answers[question['q_id']] = chosen_answer # Store the chosen text
                if chosen_answer == question['correct_answer']:
                    score += question['marks']
                    print("Correct!")
                else:
                    print(f"Incorrect. The correct answer was: {question['correct_answer']}")
                total_marks += question['marks']
                break
            else:
                print("Invalid choice. Please enter A, B, C, or D.")

    print("\n--- Quiz Finished ---")
    print(f"Your Score: {score} / {total_marks}")

    # Generate Feedback
    feedback = generate_feedback(score, total_marks)
    print(f"Feedback: {feedback}")

    # Save the result
    results = utils.load_data(utils.RESULTS_FILE, [])
    new_result = {
        "result_id": utils.generate_unique_id("res_"),
        "student_prn": student_prn,
        "quiz_id": quiz_id,
        "score": score,
        "total_marks": total_marks, # Use calculated total marks
        "timestamp": datetime.datetime.now().isoformat(),
        "answers": student_answers # Store the answers given
    }
    results.append(new_result)
    if utils.save_data(utils.RESULTS_FILE, results):
        print("Your result has been saved.")
    else:
        print("Error: Could not save your result.")

    return score, total_marks, feedback

def generate_feedback(score, total_marks):
    """Generates simple motivational feedback based on percentage."""
    if total_marks == 0:
        return "Quiz completed (no marks awarded)."
    percentage = (score / total_marks) * 100
    if percentage >= 90:
        return "Excellent work! Truly outstanding performance!"
    elif percentage >= 75:
        return "Great job! You have a strong understanding."
    elif percentage >= 60:
        return "Good effort! Keep practicing to improve further."
    elif percentage >= 40:
        return "You passed, but there's room for improvement. Review the topics."
    else:
        return "Keep trying! Review the material and attempt the quiz again if possible."