from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from config import mysql
import MySQLdb.cursors
import random, string

teacher_bp = Blueprint('teacher_bp', __name__)
bcrypt = Bcrypt()

#---------------------------------AUTH------------------------------------------------------------------

#--------------------------Teacher Registration Route----------------------------------------------
@teacher_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']  # No hashing here

        # Check if email already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM teacher WHERE email = %s", (email,))
        existing_user = cur.fetchone()
        
        if existing_user:
            flash('Email already exists. Please use a different email.', 'danger')
            cur.close()
            return redirect(url_for('teacher_bp.register'))

        # Insert plain-text password into the database
        cur.execute("INSERT INTO teacher (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, password))
        mysql.connection.commit()
        cur.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('teacher_bp.login'))

    return render_template('register.html')

#-----------------------------------Teacher Login Route-------------------------------------------------------------
@teacher_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM teacher WHERE email = %s", (email,))
        teacher = cur.fetchone()
        cur.close()

        if teacher and teacher[3] == password:  # Plain-text comparison
            session['email'] = email  # Store email in session
            session['teacher_id'] = teacher[0]  # Store teacher_id in session (assuming teacher id is the first column)
            session['username'] = teacher[1]  # Store teacher username in session (assuming teacher username is the second column)
            flash('Login successful!', 'success')
            return redirect(url_for('teacher_bp.dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

#-----------------------------------Account---------------------------------------------------------------------------------------

@teacher_bp.route('/t_acc_info')
def t_acc_info():
    if 'teacher_id' in session:  # Check for teacher_id in session
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Use teacher_id instead of teacher_username
        cursor.execute('SELECT * FROM teacher WHERE id = %s', (session['teacher_id'],))
        account = cursor.fetchone()

        # Fetch classes created by this teacher
        cursor.execute('SELECT class_name FROM t_classes WHERE teacher_id = %s', (session['teacher_id'],))
        classes = cursor.fetchall()  # List of tuples: [(class_name1), (class_name2), ...]

        cursor.close()

        # Pass 'classes' to the template
        return render_template('t_acc_info.html', account=account, username=session['username'], classes=classes)
    else:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))


#------------------------------------AUTH END------------------------------------------------------------------------------------


# Teacher Dashboard Route
@teacher_bp.route('/dashboard')
def dashboard():
    if 'teacher_id' not in session:  # Ensure only logged-in teachers access the dashboard
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for('teacher_bp.login'))

    teacher_id = session['teacher_id']  # Use teacher_id from the session

    # Fetch the teacher's username (needed for display)
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM teacher WHERE id = %s", (teacher_id,))
    teacher = cur.fetchone()

    if not teacher:
        flash("Invalid teacher information.", "danger")
        return redirect(url_for('teacher_bp.login'))

    username = teacher[0]  # The fetched username

    # Fetch classes created by this teacher using teacher_id
    cur.execute("SELECT class_name FROM t_classes WHERE teacher_id = %s", (teacher_id,))
    classes = cur.fetchall()  # List of classes (tuples)

    cur.close()

    # Pass the username and classes to the template
    return render_template('teacher.html', username=username, classes=classes)


#-------------------------------------VIEWWWW------------------------------------------------------------

@teacher_bp.route('/view_class/<string:class_name>', methods=['GET', 'POST'])
def view_class(class_name):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the username of the current teacher
    cursor.execute('SELECT username FROM teacher WHERE id = %s', (session['teacher_id'],))
    teacher_info = cursor.fetchone()

    if not teacher_info:
        flash('User not found.', 'danger')
        return redirect(url_for('teacher_bp.login'))

    # Fetch all classes created by the logged-in teacher
    cursor.execute('SELECT class_name FROM t_classes WHERE teacher_id = %s', (session['teacher_id'],))
    classes = cursor.fetchall()

    # Check if the class_name is valid and belongs to the teacher
    cursor.execute('SELECT * FROM t_classes WHERE class_name = %s AND teacher_id = %s', 
                   (class_name, session['teacher_id']))
    section = cursor.fetchone()

    if not section:
        flash('Class not found or unauthorized access.', 'danger')
        return redirect(url_for('teacher_bp.dashboard'))

    quiz_code = None  # To store the generated quiz code

    if request.method == 'POST':  # If the teacher clicks "Create Quiz"
        quiz_title = request.form['quiz_title']

        # Generate a random quiz code
        quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Insert quiz into the database
        cursor.execute('INSERT INTO quizzes (quiz_title, quiz_code, class_name, teacher_id) VALUES (%s, %s, %s, %s)', 
                       (quiz_title, quiz_code, class_name, session['teacher_id']))
        mysql.connection.commit()
        
        flash(f'Quiz "{quiz_title}" created successfully! Share this code with students: {quiz_code}', 'success')

    # Fetch quizzes associated with this class
    cursor.execute('SELECT * FROM quizzes WHERE class_name = %s', (class_name,))
    quizzes = cursor.fetchall()

    cursor.close()

    return render_template('view_class.html', 
                           username=teacher_info['username'],  # Pass teacher's username
                           classes=classes,  # Pass all classes created by teacher
                           class_name=class_name, 
                           quizzes=quizzes, 
                           quiz_code=quiz_code)  # Pass enrolled students

#-----------------------------------MANAGE QUIZ------------------------------------------------------------

@teacher_bp.route('/manage_quiz/<int:quiz_id>', methods=['GET', 'POST'])
def manage_quiz(quiz_id):
    if 'teacher_id' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('teacher_bp.login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch teacher's username from the session
    cursor.execute('SELECT username FROM teacher WHERE id = %s', (session['teacher_id'],))
    teacher = cursor.fetchone()
    teacher_username = teacher['username'] if teacher else "Unknown"

    # Fetch the quiz details
    cursor.execute('SELECT * FROM quizzes WHERE id = %s AND teacher_id = %s', 
                   (quiz_id, session['teacher_id']))
    quiz = cursor.fetchone()
    if not quiz:
        flash("Unauthorized access or quiz not found.", "danger")
        return redirect(url_for('teacher_bp.dashboard'))

    # Fetch all classes created by the teacher (use teacher_id)
    cursor.execute('SELECT * FROM t_classes WHERE teacher_id = %s', (session['teacher_id'],))
    classes = cursor.fetchall()

    # Handle POST request to add a new question
    if request.method == 'POST':
        question_text = request.form['question_text']
        option_1 = request.form['option_1']
        option_2 = request.form['option_2']
        option_3 = request.form['option_3']
        option_4 = request.form['option_4']
        correct_option = request.form['correct_option']

        cursor.execute("""
            INSERT INTO quiz_questions (quiz_id, question_text, option_1, option_2, option_3, option_4, correct_option)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (quiz_id, question_text, option_1, option_2, option_3, option_4, correct_option))
        mysql.connection.commit()
        flash("Question added successfully!", "success")

    # Fetch all questions for this quiz
    cursor.execute('SELECT * FROM quiz_questions WHERE quiz_id = %s', (quiz_id,))
    questions = cursor.fetchall()

    cursor.close()

    return render_template('manage_quiz.html', quiz=quiz, questions=questions, 
                           username=teacher_username, classes=classes)

@teacher_bp.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))
    
    cursor = mysql.connection.cursor()
    try:
        # Delete quiz questions related to the quiz
        cursor.execute('DELETE FROM quiz_questions WHERE quiz_id = %s', (quiz_id,))
        
        # Delete student answers related to the quiz
        cursor.execute('DELETE FROM student_answers WHERE quiz_id = %s', (quiz_id,))
        
        # Delete the quiz itself
        cursor.execute('DELETE FROM quizzes WHERE id = %s', (quiz_id,))
        mysql.connection.commit()
        flash('Quiz deleted successfully.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting quiz: {e}', 'danger')
    finally:
        cursor.close()
    
    return redirect(request.referrer)


@teacher_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch teacher's username from the session (same as in manage_quiz)
    cursor.execute('SELECT username FROM teacher WHERE id = %s', (session['teacher_id'],))
    teacher = cursor.fetchone()
    teacher_username = teacher['username'] if teacher else "Unknown"

    # Fetch the current question details
    cursor.execute('SELECT * FROM quiz_questions WHERE id = %s AND quiz_id IN (SELECT id FROM quizzes WHERE teacher_id = %s)', 
                   (question_id, session['teacher_id']))
    question = cursor.fetchone()

    if not question:
        flash('Question not found or unauthorized access.', 'danger')
        return redirect(url_for('teacher_bp.manage_quiz', quiz_id=question['quiz_id']))

    # Fetch all classes for sidebar
    cursor.execute('SELECT * FROM t_classes WHERE teacher_id = %s', (session['teacher_id'],))
    classes = cursor.fetchall()

    # Handle POST request to update the question
    if request.method == 'POST':
        updated_question_text = request.form['question_text']
        updated_option_1 = request.form['option_1']
        updated_option_2 = request.form['option_2']
        updated_option_3 = request.form['option_3']
        updated_option_4 = request.form['option_4']
        updated_correct_option = request.form['correct_option']

        cursor.execute(""" 
            UPDATE quiz_questions
            SET question_text = %s, option_1 = %s, option_2 = %s, option_3 = %s, option_4 = %s, correct_option = %s
            WHERE id = %s
        """, (updated_question_text, updated_option_1, updated_option_2, updated_option_3, updated_option_4, updated_correct_option, question_id))

        mysql.connection.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('teacher_bp.manage_quiz', quiz_id=question['quiz_id']))

    cursor.close()

    # Pass the current question data to the template, including teacher_username
    return render_template('edit_question.html', 
                           question=question, 
                           classes=classes, 
                           username=teacher_username)  # Pass username to template


@teacher_bp.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the question to ensure it exists and belongs to the teacher
    cursor.execute('SELECT * FROM quiz_questions WHERE id = %s AND quiz_id IN (SELECT id FROM quizzes WHERE teacher_id = %s)', 
                   (question_id, session['teacher_id']))
    question = cursor.fetchone()

    if not question:
        flash('Question not found or unauthorized access.', 'danger')
        return redirect(url_for('teacher_bp.manage_quiz', quiz_id=question['quiz_id']))

    # Delete the question from the database
    cursor.execute('DELETE FROM quiz_questions WHERE id = %s', (question_id,))
    mysql.connection.commit()

    flash('Question deleted successfully!', 'success')
    return redirect(url_for('teacher_bp.manage_quiz', quiz_id=question['quiz_id']))

#----------------------------------VIEW SCORE-------------------------------------------------

@teacher_bp.route('/quiz_scores/<int:quiz_id>', methods=['GET'])
def quiz_scores(quiz_id):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # Use DictCursor consistently

    # Retrieve username of the logged-in teacher
    teacher_id = session['teacher_id']
    cursor.execute('SELECT username FROM teacher WHERE id = %s', (teacher_id,))
    teacher = cursor.fetchone()
    teacher_username = teacher['username'] if teacher else "Unknown"

    # Fetch sections (classes) created by this teacher
    cursor.execute("SELECT class_name FROM t_classes WHERE teacher_id = %s", (teacher_id,))
    sections = cursor.fetchall()
    
    # Fetch quiz details
    cursor.execute('SELECT quiz_title, class_name FROM quizzes WHERE id = %s', (quiz_id,))
    quiz = cursor.fetchone()
    
    if not quiz:
        flash('Quiz not found.', 'danger')
        return redirect(url_for('teacher_bp.dashboard'))
    
    class_name = quiz['class_name']  # Fetch the class name

    # Fetch student scores for the quiz
    cursor.execute("""
        SELECT sa.student_id, s.first_name, s.last_name, sa.selected_option, qq.correct_option
        FROM student_answers sa
        JOIN student_info s ON sa.student_id = s.student_id
        JOIN quiz_questions qq ON sa.question_id = qq.id
        WHERE sa.quiz_id = %s
    """, (quiz_id,))
    answers = cursor.fetchall()
    
    # Calculate scores for each student
    student_scores = {}
    for answer in answers:
        student_id = answer['student_id']
        if student_id not in student_scores:
            student_scores[student_id] = {'first_name': answer['first_name'], 
                                          'last_name': answer['last_name'], 
                                          'score': 0}
        
        # Compare the selected option with the correct answer
        if answer['selected_option'] == answer['correct_option']:
            student_scores[student_id]['score'] += 1
    
    cursor.close()

    # Render the scores page
    return render_template('quiz_scores.html', 
                           quiz=quiz,
                           student_scores=student_scores,
                           username=teacher_username,
                           classes=sections,
                           class_name=class_name)  # Pass class_name

#------------------------------ATTENDANCE---------------------------------------------------------------

@teacher_bp.route('/attendance/<int:quiz_id>', methods=['GET'])
def attendance(quiz_id):
    if 'teacher_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('teacher_bp.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Retrieve the logged-in teacher's username
    teacher_id = session['teacher_id']
    cursor.execute("SELECT username FROM teacher WHERE id = %s", (teacher_id,))
    teacher = cursor.fetchone()
    teacher_username = teacher['username'] if teacher else "Unknown"

    # Retrieve sections (classes) created by the teacher
    cursor.execute("SELECT class_name FROM t_classes WHERE teacher_id = %s", (teacher_id,))
    sections = cursor.fetchall()

    # Fetch the class_name linked to this quiz
    cursor.execute("SELECT class_name FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_info = cursor.fetchone()
    class_name = quiz_info['class_name'] if quiz_info else None

    # Fetch attendance summary for the given quiz
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN submitted_at BETWEEN t.start_time AND t.end_time THEN 1 END) AS present,
            COUNT(CASE WHEN submitted_at > t.end_time THEN 1 END) AS absent
        FROM student_quiz_scores s
        JOIN t_classes t ON s.quiz_id = t.id
        WHERE s.quiz_id = %s
    """, (quiz_id,))
    attendance_summary = cursor.fetchone()

    present = attendance_summary['present'] if attendance_summary else 0
    absent = attendance_summary['absent'] if attendance_summary else 0

    cursor.close()

    # Render the attendance page with sidebar data
    return render_template('attendance_summary.html',
                           username=teacher_username,
                           classes=sections,
                           present=present,
                           absent=absent,
                           class_name=class_name)  # Pass class_name to the template
