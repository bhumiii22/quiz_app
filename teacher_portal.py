import os
from modules import auth, quiz_manager, excel_handler, performance_analyzer, utils

def teacher_menu(current_user):
    """Displays the main menu for teachers."""
    print("\n--- Teacher Portal ---")
    print(f"Logged in as: {current_user['email']}")
    print("1. Create Quiz Manually")
    print("2. Create Quiz from Excel")
    print("3. Generate Smart Quiz (Random Questions)")
    print("4. View Performance Analysis")
    print("5. View Available Subjects & Question Counts")
    print("6. Add Questions Manually to Subject")
    print("7. Logout")
    return input("Choose an option: ")

def create_manual_quiz(creator_email):
    """Handles manual quiz creation."""
    print("\n--- Create Quiz Manually ---")
    subject_id = input("Enter Subject ID (e.g., CS101): ").strip().upper()
    if not subject_id:
        print("Subject ID cannot be empty.")
        return

    available_questions = quiz_manager.get_questions_by_subject(subject_id)
    if not available_questions:
        print(f"No questions found for Subject ID '{subject_id}'. Please add questions first.")
        add_choice = input("Do you want to add questions to this subject now? (y/n): ").lower()
        if add_choice == 'y':
            add_manual_questions(subject_id)
            available_questions = quiz_manager.get_questions_by_subject(subject_id)
            if not available_questions:
                print("Still no questions available. Cannot create quiz.")
                return
        else:
            return

    print(f"\nAvailable questions for Subject '{subject_id}':")
    for i, q in enumerate(available_questions):
        print(f"  {i+1}. ID: {q['q_id']} | Marks: {q['marks']} | Text: {q['text'][:50]}...")

    selected_indices = input("Enter question numbers to include (comma-separated, e.g., 1,3,5): ")
    selected_q_ids = []
    selected_total_marks = 0
    try:
        indices = [int(idx.strip()) - 1 for idx in selected_indices.split(',')]
        for idx in indices:
            if 0 <= idx < len(available_questions):
                selected_q_ids.append(available_questions[idx]['q_id'])
                selected_total_marks += available_questions[idx]['marks']
            else:
                print(f"Warning: Invalid question number {idx+1} ignored.")
    except ValueError:
        print("Invalid input format for question numbers.")
        return

    if not selected_q_ids:
        print("No valid questions selected.")
        return

    quiz_title = input("Enter a title for this quiz: ").strip()
    if not quiz_title:
        print("Quiz title cannot be empty.")
        return

    quiz_manager.create_quiz(quiz_title, subject_id, creator_email, selected_q_ids, selected_total_marks)

def create_excel_quiz(creator_email):
    """Handles quiz creation from an Excel file."""
    print("\n--- Create Quiz from Excel ---")
    subject_id = input("Enter Subject ID for these questions (e.g., PHY102): ").strip().upper()
    if not subject_id:
        print("Subject ID cannot be empty.")
        return

    filepath = input("Enter the full path to the Excel file (.xlsx): ").strip()
    if not filepath.endswith(".xlsx"):
        print("Invalid file type. Please provide an .xlsx file.")
        return

    questions_from_excel = excel_handler.read_questions_from_excel(filepath)

    if not questions_from_excel:
        print("Could not read questions from Excel file.")
        return

    added_q_ids = []
    total_marks_added = 0
    print(f"\nAdding {len(questions_from_excel)} questions to Subject ID '{subject_id}'...")
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

    if not added_q_ids:
        print("No questions were successfully added from the Excel file.")
        return

    print(f"\nSuccessfully added {len(added_q_ids)} questions to '{subject_id}'.")

    create_quiz_now = input("Do you want to create a quiz using ALL these added questions now? (y/n): ").lower()
    if create_quiz_now == 'y':
        quiz_title = input(f"Enter a title for the quiz (using all {len(added_q_ids)} new questions): ").strip()
        if not quiz_title:
            quiz_title = f"{subject_id} Quiz from {os.path.basename(filepath)}" # Default title
        quiz_manager.create_quiz(quiz_title, subject_id, creator_email, added_q_ids, total_marks_added)
    else:
        print("Questions added. You can create a quiz manually later using these questions.")


def generate_smart_quiz_prompt(creator_email):
    """Handles the 'smart prompt' feature."""
    print("\n--- Generate Smart Quiz ---")
    prompt = input("Enter prompt (e.g., 'Generate quiz of 20 marks from SubjectID: CS101'): ").strip()

    # Basic parsing (can be made more robust with regex)
    try:
        parts = prompt.lower().split("subjectid:")
        subject_id_part = parts[1].strip().upper() # Get the part after "subjectid:"
        # Extract subject ID (assuming it's the first word after the colon)
        subject_id = subject_id_part.split()[0]

        marks_part = prompt.lower().split(" quiz of ")[1].split(" marks")[0]
        target_marks = int(marks_part.strip())

        title_prefix = f"Smart Quiz ({subject_id})" # Default title prefix

        print(f"Attempting to generate quiz: Subject={subject_id}, Marks={target_marks}")
        quiz_manager.generate_smart_quiz(subject_id, target_marks, creator_email, title_prefix)

    except (IndexError, ValueError) as e:
        print("Invalid prompt format. Use: 'Generate quiz of [Number] marks from SubjectID: [ID]'")
        print(f"Parsing error: {e}")


def view_analysis():
    """Handles viewing performance analysis."""
    print("\n--- View Performance Analysis ---")
    quizzes = utils.load_data(utils.QUIZZES_FILE, [])
    if not quizzes:
        print("No quizzes found.")
        return

    print("Available Quizzes:")
    for i, quiz in enumerate(quizzes):
        print(f"  {i+1}. ID: {quiz['quiz_id']} | Title: {quiz.get('title', 'N/A')} | Subject: {quiz.get('subject_id', 'N/A')}")

    try:
        choice = int(input("Enter the number of the quiz to analyze: ")) - 1
        if 0 <= choice < len(quizzes):
            selected_quiz_id = quizzes[choice]['quiz_id']
            performance_analyzer.analyze_quiz_performance(selected_quiz_id)
            print(f"\nNote: Graphs (if generated) are saved in the '{utils.PLOTS_DIR}' directory.")
        else:
            print("Invalid choice.")
    except ValueError:
        print("Invalid input. Please enter a number.")

def view_subjects():
     """Displays available subjects and their question counts."""
     print("\n--- Available Subjects and Question Counts ---")
     questions_data = utils.load_data(utils.QUESTIONS_FILE, {})
     if not questions_data:
         print("No subjects or questions found.")
         return

     subject_ids = sorted(questions_data.keys())
     for subject_id in subject_ids:
         count = len(questions_data[subject_id])
         print(f"- Subject ID: {subject_id}, Questions Available: {count}")


def add_manual_questions(subject_id_preset=None):
    """Allows teacher to add questions manually one by one."""
    print("\n--- Add Questions Manually ---")
    if subject_id_preset:
        subject_id = subject_id_preset
        print(f"Adding questions to Subject ID: {subject_id}")
    else:
        subject_id = input("Enter Subject ID to add questions to (e.g., CS101): ").strip().upper()

    if not subject_id:
        print("Subject ID cannot be empty.")
        return

    while True:
        print("\nEnter details for the new question (or type 'done' for text to finish):")
        text = input("Question Text: ").strip()
        if text.lower() == 'done':
            break
        if not text:
            print("Question text cannot be empty.")
            continue

        options = []
        for i in range(4): # Assuming 4 options (A, B, C, D)
            option = input(f"Option {chr(ord('A') + i)}: ").strip()
            if not option:
                print("Option text cannot be empty.")
                # Simple loop break, teacher has to restart this question
                options = [] # Reset options for this question
                break
            options.append(option)
        if not options: # If loop broke due to empty option
             continue

        correct_letter = input("Correct Option Letter (A/B/C/D): ").strip().upper()
        correct_answer = ""
        if correct_letter in ['A', 'B', 'C', 'D']:
            correct_answer = options[ord(correct_letter) - ord('A')]
        else:
            print("Invalid correct option letter. Must be A, B, C, or D.")
            continue

        try:
            marks = int(input("Marks for this question: "))
            if marks <= 0:
                print("Marks must be a positive integer.")
                continue
        except ValueError:
            print("Invalid input for marks. Please enter a number.")
            continue

        # Add the question
        quiz_manager.add_question(subject_id, text, options, correct_answer, marks)

        cont = input("Add another question to this subject? (y/n): ").lower()
        if cont != 'y':
            break


# --- Main Execution ---
if __name__ == "__main__":
    current_user = None
    while current_user is None:
        print("\nWelcome to the Quiz Application")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        initial_choice = input("Choose an option: ")

        if initial_choice == '1':
            logged_in_user = auth.login()
            if logged_in_user and logged_in_user['role'] == 'teacher':
                current_user = logged_in_user
            elif logged_in_user:
                print("Access Denied: This portal is for teachers only.")
            # Else login failed message already printed by auth.login()
        elif initial_choice == '2':
            auth.register_user() # Allow registration from here
        elif initial_choice == '3':
            print("Exiting.")
            exit()
        else:
            print("Invalid choice.")

    # If login successful
    while True:
        choice = teacher_menu(current_user)
        if choice == '1':
            create_manual_quiz(current_user['email'])
        elif choice == '2':
            create_excel_quiz(current_user['email'])
        elif choice == '3':
            generate_smart_quiz_prompt(current_user['email'])
        elif choice == '4':
            view_analysis()
        elif choice == '5':
             view_subjects()
        elif choice == '6':
             add_manual_questions()
        elif choice == '7':
            print("Logging out.")
            break
        else:
            print("Invalid option, please try again.")