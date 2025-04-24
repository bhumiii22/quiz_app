from modules import auth, quiz_taker, utils

def student_menu(current_user):
    """Displays the main menu for students."""
    print("\n--- Student Portal ---")
    print(f"Logged in as: {current_user['email']} (PRN: {current_user.get('prn', 'N/A')})")
    print("1. View Available Quizzes")
    print("2. Take Quiz")
    print("3. View Completed Quizzes & Results")
    print("4. Logout")
    return input("Choose an option: ")

def display_quizzes(quiz_list, title="Quizzes"):
    """Helper function to display a list of quizzes."""
    if not quiz_list:
        print(f"No {title.lower()} found.")
        return False # Indicates none were displayed

    print(f"\n--- {title} ---")
    for i, quiz in enumerate(quiz_list):
        print(f"  {i+1}. ID: {quiz['quiz_id']} | Title: {quiz.get('title', 'N/A')} | Subject: {quiz.get('subject_id', 'N/A')} | Marks: {quiz.get('total_marks', 'N/A')}")
    return True # Indicates quizzes were displayed

def select_quiz(quiz_list):
    """Prompts user to select a quiz from the list by number."""
    if not quiz_list:
        return None # No quizzes to select

    while True:
        try:
            choice = int(input("Enter the number of the quiz: ")) - 1
            if 0 <= choice < len(quiz_list):
                return quiz_list[choice]['quiz_id']
            else:
                print("Invalid choice number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        # Offer option to go back
        back = input("Enter 'b' to go back, or press Enter to try again: ").lower()
        if back == 'b':
            return None


def view_completed(student_prn):
    """Displays completed quizzes and results for the student."""
    completed = quiz_taker.get_completed_quizzes(student_prn)
    if not completed:
        print("\nYou have not completed any quizzes yet.")
        return

    print("\n--- Completed Quizzes & Results ---")
    for i, result in enumerate(completed):
        print(f"  {i+1}. Quiz Title: {result.get('quiz_title', 'N/A')}")
        print(f"     Subject: {result.get('subject_id', 'N/A')}")
        print(f"     Score: {result.get('score', 'N/A')} / {result.get('total_marks', 'N/A')}")
        print(f"     Completed On: {result.get('timestamp', 'N/A')}")
        print("-" * 20)


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
            if logged_in_user and logged_in_user['role'] == 'student':
                current_user = logged_in_user
                if 'prn' not in current_user or not current_user['prn']:
                     print("Error: Logged in student is missing PRN. Please contact admin.")
                     current_user = None # Prevent proceeding without PRN
            elif logged_in_user:
                print("Access Denied: This portal is for students only.")
            # Else login failed message already printed by auth.login()
        elif initial_choice == '2':
            auth.register_user() # Allow registration from here
        elif initial_choice == '3':
            print("Exiting.")
            exit()
        else:
            print("Invalid choice.")


    # If login successful
    student_prn = current_user.get('prn')
    while True:
        choice = student_menu(current_user)

        if choice == '1':
            available = quiz_taker.get_available_quizzes(student_prn)
            display_quizzes(available, title="Available Quizzes")
        elif choice == '2':
            available = quiz_taker.get_available_quizzes(student_prn)
            if display_quizzes(available, title="Select Quiz to Take"):
                selected_quiz_id = select_quiz(available)
                if selected_quiz_id:
                    quiz_taker.start_quiz(student_prn, selected_quiz_id)
                else:
                    print("No quiz selected or went back.")
        elif choice == '3':
            view_completed(student_prn)
        elif choice == '4':
            print("Logging out.")
            break
        else:
            print("Invalid option, please try again.")