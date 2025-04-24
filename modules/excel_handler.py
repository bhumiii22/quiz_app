import pandas as pd
import os
from . import utils # To use logging

def read_questions_from_excel(filepath):
    """
    Reads quiz questions from an Excel file.
    Expected columns: 'Question Text', 'Option A', 'Option B',
                      'Option C', 'Option D', 'Correct Option Letter', 'Marks'
    """
    required_columns = ['Question Text', 'Option A', 'Option B', 'Option C', 'Option D', 'Correct Option Letter', 'Marks']
    questions = []

    if not os.path.exists(filepath):
        utils.logging.error(f"Excel file not found: {filepath}")
        print(f"Error: File not found at {filepath}")
        return None

    try:
        df = pd.read_excel(filepath)

        # Validate columns
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            utils.logging.error(f"Excel file missing required columns: {missing}")
            print(f"Error: Excel file missing required columns: {', '.join(missing)}")
            return None

        for index, row in df.iterrows():
            try:
                text = str(row['Question Text']).strip()
                options = [
                    str(row['Option A']).strip(),
                    str(row['Option B']).strip(),
                    str(row['Option C']).strip(),
                    str(row['Option D']).strip()
                ]
                # Ensure options are not empty
                if not all(options):
                    utils.logging.warning(f"Row {index+2}: Skipping question due to empty option(s). Text: '{text[:30]}...'")
                    print(f"Warning: Row {index+2} has empty options, skipping question: '{text[:30]}...'")
                    continue

                correct_option_letter = str(row['Correct Option Letter']).strip().upper()
                if correct_option_letter not in ['A', 'B', 'C', 'D']:
                    utils.logging.warning(f"Row {index+2}: Invalid correct option '{correct_option_letter}'. Skipping question: '{text[:30]}...'")
                    print(f"Warning: Row {index+2} has invalid correct option '{correct_option_letter}'. Skipping question: '{text[:30]}...'")
                    continue
                # Convert letter to index (A=0, B=1, etc.)
                correct_answer_index = ord(correct_option_letter) - ord('A')
                correct_answer = options[correct_answer_index] # Store the actual answer text

                marks = int(row['Marks'])
                if marks <= 0:
                     utils.logging.warning(f"Row {index+2}: Invalid marks '{marks}'. Skipping question: '{text[:30]}...'")
                     print(f"Warning: Row {index+2} has invalid marks '{marks}'. Skipping question: '{text[:30]}...'")
                     continue

                if not text:
                    utils.logging.warning(f"Row {index+2}: Skipping question due to empty text.")
                    print(f"Warning: Row {index+2} has empty question text, skipping.")
                    continue


                questions.append({
                    "text": text,
                    "options": options,
                    "correct_answer": correct_answer, # Store the text of the correct option
                    "marks": marks
                })
            except (ValueError, TypeError) as e:
                utils.logging.error(f"Error processing row {index+2} in Excel: {e}. Skipping.")
                print(f"Error processing row {index+2}: {e}. Skipping question.")
            except IndexError:
                 utils.logging.error(f"Error processing row {index+2}: Correct Option Letter '{correct_option_letter}' out of bounds for options {options}. Skipping.")
                 print(f"Error processing row {index+2}: Correct Option Letter '{correct_option_letter}' is invalid for the provided options. Skipping question.")


        utils.logging.info(f"Successfully read {len(questions)} questions from {filepath}")
        return questions

    except Exception as e:
        utils.logging.error(f"Failed to read or process Excel file {filepath}: {e}")
        print(f"An error occurred while reading the Excel file: {e}")
        return None