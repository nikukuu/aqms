import MySQLdb
from flask import Blueprint, render_template, request, redirect, flash, url_for, session
from config import mysql
from MySQLdb.cursors import DictCursor

student_bp = Blueprint('student_bp', __name__)

# Student Authentication Route
@student_bp.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        student_id = request.form['student_id']
        quiz_code = request.form['quiz_code']

        # Check if quiz code exists
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM quizzes WHERE quiz_code = %s", (quiz_code,))
        quiz = cur.fetchone()

        if quiz:
            # Check if the student ID is valid and if the student is enrolled in the class for this quiz
            cur.execute("""
                SELECT si.student_id 
                FROM student_info si
                JOIN t_classes tc ON si.section_id = tc.id
                WHERE si.student_id = %s AND tc.teacher_id = %s
            """, (student_id, quiz['teacher_id']))
            student_in_class = cur.fetchone()

            if student_in_class:
                # Store the student_id in the session for use in take_quiz
                session['student_id'] = student_id
                flash(f'Quiz authentication successful! Welcome, Student {student_id}!', 'success')
                return redirect(url_for('student_bp.take_quiz', quiz_id=quiz['id']))
            else:
                flash('You are not enrolled in the section for this quiz.', 'danger')
        else:
            flash('Invalid Quiz Code. Please try again.', 'danger')

        cur.close()

    return render_template('student_auth.html')


#------------------------AUTH---END-------------------------------------------------------------------------------------


@student_bp.route('/take_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def take_quiz(quiz_id):
    student_id = session.get('student_id')
    if not student_id:
        flash('You are not authorized to take this quiz.', 'danger')
        return redirect(url_for('student_bp.auth'))
    
    # Check if the student already took this quiz
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT * FROM student_answers 
        WHERE student_id = %s AND quiz_id = %s
    """, (student_id, quiz_id))
    existing_answers = cur.fetchone()

    if existing_answers:
        flash('You have already taken this quiz. Retaking is not allowed.', 'danger')
        cur.close()
        return redirect(url_for('student_bp.auth'))

    if request.method == 'POST':
        # Retrieve all questions for the quiz
        cur.execute('SELECT * FROM quiz_questions WHERE quiz_id = %s', (quiz_id,))
        questions = cur.fetchall()

        score = 0

        for question in questions:
            # Get the selected option as a string (e.g., 'option_1')
            selected_option = request.form.get(f'question_{question["id"]}')

            if selected_option:
                # Fetch the correct answer (correct_option) from the question
                correct_option = question['correct_option']

                # Compare the selected option with the correct answer
                if selected_option == correct_option:
                    score += 1

                # Save the student's answer in the database
                cur.execute("""
                    INSERT INTO student_answers (student_id, quiz_id, question_id, selected_option, correct_answer)
                    VALUES (%s, %s, %s, %s, %s)
                """, (student_id, quiz_id, question['id'], selected_option, correct_option))
        
        # After calculating the score, insert it into the student_quiz_scores table
        cur.execute("""
            INSERT INTO student_quiz_scores (student_id, quiz_id, score, total_questions)
            VALUES (%s, %s, %s, %s)
        """, (student_id, quiz_id, score, len(questions)))

        # Commit changes and close the cursor
        mysql.connection.commit()
        cur.close()

        # Show the result with the final score
        flash(f'You scored {score} out of {len(questions)}', 'success')
        return redirect(url_for('student_bp.quiz_results', quiz_id=quiz_id, student_id=student_id))

    # GET request - show quiz questions
    cur.execute('SELECT * FROM quizzes WHERE id = %s', (quiz_id,))
    quiz = cur.fetchone()

    cur.execute('SELECT * FROM quiz_questions WHERE quiz_id = %s', (quiz_id,))
    questions = cur.fetchall()

    cur.close()
    return render_template('take_quiz.html', quiz=quiz, questions=questions)


@student_bp.route('/quiz_results/<int:quiz_id>/<int:student_id>')
def quiz_results(quiz_id, student_id):
    # Connect to the database
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch quiz details
    cur.execute('SELECT quiz_title FROM quizzes WHERE id = %s', (quiz_id,))
    quiz = cur.fetchone()

    # Fetch student's answers and compare with the correct answers
    cur.execute("""
        SELECT sa.question_id, sa.selected_option, qq.correct_option, qq.question_text
        FROM student_answers sa
        JOIN quiz_questions qq ON sa.question_id = qq.id
        WHERE sa.student_id = %s AND sa.quiz_id = %s
    """, (student_id, quiz_id))
    answers = cur.fetchall()

    # Calculate score
    score = sum(1 for ans in answers if ans['selected_option'] == ans['correct_option'])
    total_questions = len(answers)


    cur.close()

    # Render results page
    return render_template('quiz_results.html', quiz=quiz, answers=answers, score=score, total=total_questions)