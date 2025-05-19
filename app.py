import os
import re
import uuid
import fitz  # PyMuPDF
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai
import sqlite3
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# Load environment vars
load_dotenv()

# Flask setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gemini API setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

# Initialize database
conn = sqlite3.connect('cover_letters.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS cover_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Add users table
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()

# Initialize Flask-Login and Bcrypt
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
bcrypt = Bcrypt(app)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

# Load user from database
@login_manager.user_loader
def load_user(user_id):
    cursor.execute("SELECT id, email FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        return User(id=user[0], email=user[1])
    return None


def extract_text_from_pdf(file_path):
    """Extract all text from a PDF using PyMuPDF (fitz)."""
    doc = fitz.open(file_path)
    return "".join(page.get_text() for page in doc)


def extract_contact_info(resume_text):
    """Pull out name, email, phone, and address from raw resume text."""
    # Patterns
    email_pat = r'\b[\w\.-]+?@\w+?\.\w+?\b'
    phone_pat = r'\b(?:\+?\d{1,2}[-\s]?)?(?:\(?\d{3}\)?[-\s]?)?\d{3}[-\s]?\d{4}\b'

    email_m = re.search(email_pat, resume_text)
    phone_m = re.search(phone_pat, resume_text)
    lines = resume_text.splitlines()

    # Heuristics: first line = name, next 2–3 = address
    name = lines[0].strip() if lines else ""
    address = "\n".join(lines[1:4]).strip() if len(lines) > 1 else ""

    return {
        "name":    name,
        "email":   email_m.group() if email_m else "",
        "phone":   phone_m.group() if phone_m else "",
        "address": address
    }


def generate_cover_letter(resume_path, job_desc, tone):
    """Build the prompt (with extracted contact info) and call Gemini."""
    txt = extract_text_from_pdf(resume_path)
    info = extract_contact_info(txt)

    # Prompt for generating the cover letter
    prompt = f"""
You are an AI assistant that writes cover letters. Generate a {tone} cover letter using the following resume and job description and generate professional cover letter that
should not copy github and linkedin from resume.

Resume:
{txt}

Job Description:
{job_desc}

Ensure the letter starts with the candidate's:
Name: {info['name']}
Address: {info['address']}
Phone Number: {info['phone']}
Email Address: {info['email']}

Cover Letter:
"""
    resp = model.generate_content(prompt)
    cover_letter = resp.text

    # Prompt for feedback on the generated cover letter
    feedback_prompt = f"""
You are an AI assistant that provides feedback on cover letters. Analyze the following cover letter and provide feedback on what can be added more and what is good in resume. Be specific and constructive on resume.

Cover Letter:
{cover_letter}

Feedback:
"""
    feedback_resp = model.generate_content(feedback_prompt)
    feedback = feedback_resp.text

    return cover_letter, feedback


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Save user to database
        try:
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Error: Email already registered.", 400

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Verify user credentials
        cursor.execute("SELECT id, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if user and bcrypt.check_password_hash(user[1], password):
            login_user(User(id=user[0], email=email))
            return redirect(url_for('index'))
        else:
            return "Error: Invalid email or password.", 400

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/download/<filename>')
def download_file(filename):
    """Serve the generated cover letter for download."""
    file_path = os.path.join('generated_letters', filename)
    return send_file(file_path, as_attachment=True)


@app.route('/result/<filename>')
@login_required
def result_page(filename):
    """Display the generated cover letter without feedback by default."""
    file_path = os.path.join('generated_letters', filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        cover_letter = f.read()
    download_link = f"/download/{filename}"
    return render_template('result.html', cover_letter=cover_letter, feedback=None, download_link=download_link)


@app.route('/get_feedback', methods=['POST'])
def get_feedback():
    """Generate AI feedback for the cover letter."""
    data = request.get_json()
    cover_letter = data.get('cover_letter', '')

    if not cover_letter:
        return jsonify({'error': 'No cover letter provided'}), 400

    # Generate feedback using the AI model
    feedback_prompt = f"""
    You are an AI assistant that provides feedback on cover letters. Analyze the following cover letter and provide feedback on what is good , what can be added. Be specific and constructive.

    Cover Letter:
    {cover_letter}

    Feedback:
    """
    feedback_resp = model.generate_content(feedback_prompt)
    feedback = feedback_resp.text

    return jsonify({'feedback': feedback})


@app.route('/get_feedback_page', methods=['POST'])
def get_feedback_page():
    """Generate AI feedback for the cover letter and display it."""
    cover_letter = request.form.get('cover_letter', '')

    if not cover_letter:
        return "Error: No cover letter provided.", 400

    # Generate feedback using the AI model
    feedback_prompt = f"""
    You are an AI assistant that provides feedback on cover letters. Analyze the following cover letter and provide feedback on its tone, grammar, and structure. Be specific and constructive.

    Cover Letter:
    {cover_letter}

    Feedback:
    """
    feedback_resp = model.generate_content(feedback_prompt)
    feedback = feedback_resp.text

    # Render the result page with feedback
    return render_template('result.html', cover_letter=cover_letter, feedback=feedback, download_link=None)


@app.route('/generate', methods=['GET', 'POST'])
@login_required
def generate_cover_letter_route():
    if request.method == 'POST':
        # Retrieve form data
        resume_file = request.files.get('resume')
        job_description = request.form.get('job_description', '').strip()
        job_description_file = request.files.get('job_description_file')
        tone = request.form.get('tone', 'professional').strip()

        # Validate inputs
        if not resume_file:
            return "Error: No resume file uploaded.", 400
        if not job_description and not job_description_file:
            return "Error: No job description provided.", 400

        # Save uploaded resume
        filename = secure_filename(resume_file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resume_file.save(save_path)

        # Process job description
        if job_description_file:
            job_desc_filename = secure_filename(job_description_file.filename)
            job_desc_path = os.path.join(app.config['UPLOAD_FOLDER'], job_desc_filename)
            job_description_file.save(job_desc_path)

            # Check the file extension
            file_extension = os.path.splitext(job_desc_filename)[1].lower()

            if file_extension == '.txt':
                # Read plain text files
                with open(job_desc_path, 'r', encoding='utf-8') as f:
                    job_description = f.read()
            elif file_extension == '.pdf':
                # Extract text from PDF files
                job_description = extract_text_from_pdf(job_desc_path)
            else:
                return "Error: Unsupported file type. Please upload a .txt or .pdf file.", 400

        # Generate cover letter
        cover_letter, feedback = generate_cover_letter(save_path, job_description, tone)

        # Save the generated cover letter to a file
        os.makedirs('generated_letters', exist_ok=True)
        output_filename = f"cover_letter_{uuid.uuid4().hex[:8]}.txt"
        output_path = os.path.join('generated_letters', output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cover_letter)

        # Redirect to the result page
        return redirect(url_for('result_page', filename=output_filename))

    # GET request
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)

