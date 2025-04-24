# modules/performance_analyzer.py
import pandas as pd
import matplotlib.pyplot as plt
import os
from . import utils
import logging # Import logging

# Ensure matplotlib backend is suitable for non-interactive use in web server
# Sometimes needed, especially on servers without a display
import matplotlib
matplotlib.use('Agg') # Use 'Agg' backend which doesn't require a GUI

def analyze_quiz_performance(quiz_id):
    """
    Analyzes results for a specific quiz.
    Returns a dictionary with stats and plot URLs, or None if error.
    """
    results = utils.load_data(utils.RESULTS_FILE, [])
    quizzes = utils.load_data(utils.QUIZZES_FILE, [])

    quiz_info = next((q for q in quizzes if q.get('quiz_id') == quiz_id), None)
    if not quiz_info:
        logging.error(f"Analysis failed: Quiz details not found for ID: {quiz_id}")
        return None, "Quiz details not found."

    quiz_title = quiz_info.get('title', f"Quiz {quiz_id}")
    subject_id = quiz_info.get('subject_id', 'N/A')

    quiz_results = [r for r in results if r.get('quiz_id') == quiz_id]

    analysis_data = {
        "quiz_id": quiz_id,
        "quiz_title": quiz_title,
        "subject_id": subject_id,
        "num_attempts": 0,
        "max_possible_score": 0,
        "average_score": 0,
        "average_percentage": 0,
        "highest_score": 0,
        "lowest_score": 0,
        "top_performers": [], # List of {"prn": "...", "score": ...}
        "bottom_performers": [], # List of {"prn": "...", "score": ...}
        "completers": [], # List of PRNs
        "histogram_url": None,
        "error_message": None
    }

    if not quiz_results:
        analysis_data["error_message"] = "No results found for this quiz yet."
        logging.info(f"No results to analyze for quiz {quiz_id}")
        return analysis_data, None # Return data structure with error message

    try:
        df = pd.DataFrame(quiz_results)

        # --- Basic Stats ---
        analysis_data["num_attempts"] = len(df)
        if not df.empty and 'total_marks' in df.columns and not df['total_marks'].isnull().all():
             analysis_data["max_possible_score"] = int(df['total_marks'].iloc[0]) # Ensure integer
        else:
             analysis_data["max_possible_score"] = 0 # Or handle error more gracefully

        if analysis_data["max_possible_score"] > 0 and not df['score'].isnull().all():
            analysis_data["average_score"] = round(df['score'].mean(), 2)
            analysis_data["average_percentage"] = round((analysis_data["average_score"] / analysis_data["max_possible_score"] * 100), 2)
            analysis_data["highest_score"] = int(df['score'].max()) # Ensure integer
            analysis_data["lowest_score"] = int(df['score'].min()) # Ensure integer
        else:
             # Handle cases with zero marks or no scores
             analysis_data["average_score"] = 0
             analysis_data["average_percentage"] = 0
             analysis_data["highest_score"] = 0
             analysis_data["lowest_score"] = 0


        # --- Identify Performers ---
        df_sorted = df.sort_values(by='score', ascending=False)
        top_n = min(5, analysis_data["num_attempts"])
        bottom_n = min(5, analysis_data["num_attempts"])

        analysis_data["top_performers"] = df_sorted.head(top_n)[['student_prn', 'score']].to_dict('records')
        # Convert score to int in dict records
        for item in analysis_data["top_performers"]: item['score'] = int(item['score'])

        # Get bottom performers and sort them ascending for display
        bottom_df = df_sorted.tail(bottom_n).iloc[::-1]
        analysis_data["bottom_performers"] = bottom_df[['student_prn', 'score']].to_dict('records')
         # Convert score to int in dict records
        for item in analysis_data["bottom_performers"]: item['score'] = int(item['score'])

        analysis_data["completers"] = df['student_prn'].unique().tolist()


        # --- Generate Plots ---
        # 1. Score Distribution Histogram
        plt.figure(figsize=(8, 5)) # Slightly smaller figure for web
        # Ensure scores are numeric, handle potential errors
        numeric_scores = pd.to_numeric(df['score'], errors='coerce').dropna()
        if not numeric_scores.empty:
            bins_count = max(5, min(len(numeric_scores) // 2, 15)) # Dynamic bins
            plt.hist(numeric_scores, bins=bins_count, edgecolor='black')
            plt.title(f'Score Distribution: {quiz_title[:30]}...') # Shorter title
            plt.xlabel('Score')
            plt.ylabel('Number of Students')
            plt.grid(axis='y', alpha=0.7)

            # Save plot to static/plots
            plot_filename = f"hist_{quiz_id}.png"
            plot_filepath = utils.get_plot_path(plot_filename)
            plt.savefig(plot_filepath)
            plt.close() # Close plot to free memory
            analysis_data["histogram_url"] = utils.get_plot_url(plot_filename) # Get URL path
            logging.info(f"Generated histogram for {quiz_id} at {plot_filepath}")
        else:
            logging.warning(f"No numeric scores to plot histogram for quiz {quiz_id}")


    except Exception as e:
        logging.error(f"Error during analysis/plotting for quiz {quiz_id}: {e}", exc_info=True)
        analysis_data["error_message"] = f"An error occurred during analysis: {e}"
        return analysis_data, f"An error occurred during analysis: {e}" # Return data structure with error

    return analysis_data, None # Return data and None for error