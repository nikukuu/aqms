from flask import Flask, render_template
from config import app, mysql
from blueprints.teacher_auth import teacher_bp
from blueprints.student_auth import student_bp

app.secret_key = 'QMS'

# Initialize Blueprints
app.register_blueprint(teacher_bp, url_prefix='/teacher')
app.register_blueprint(student_bp, url_prefix='/student')

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)