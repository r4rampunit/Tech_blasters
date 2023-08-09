from flask import Flask, render_template, request, jsonify, session
import os
from werkzeug.utils import secure_filename
import docx
import PyPDF2
from transformers import GPT2Tokenizer, GPT2ForSequenceClassification
import smtplib
from email.mime.text import MIMEText
import os
from flask import Flask, render_template, send_from_directory               
from email.message import EmailMessage
import smtplib
import ssl

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'txt'}

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

chatbox_responses = {
    1: "Tell me about your experience with Python.",
    2: "How many years of experience do you have in Django?",
    3: "Have you worked with React?",
    4: "Do you have any experience in Java?",
    5: "Tell me about your full-stack development experience.",
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def evaluate_job_description(job_description):
    tokenizer = GPT2Tokenizer.from_pretrained("distilgpt2")
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model = GPT2ForSequenceClassification.from_pretrained("distilgpt2")

    inputs = tokenizer(job_description, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)

    evaluation_score = outputs.logits.mean().item()
    return evaluation_score

def calculate_answer_score(answers):
    job_description = "We are looking for a software engineer with experience in Python and Django framework."

    questions = [
        "How many years of experience do you have in Python?",
        "How many years of experience do you have in Django?",
        "Have you worked with React?",
        "Do you have any experience in Java?",
        "Tell me about your full-stack development experience."
    ]

    question_weights = [2, 2, 1, 1, 1]

    all_answers = ' '.join(map(str, answers))  # Convert answers to strings before joining

    answer_score = 0
    for i, question in enumerate(questions):
        if question.lower() in all_answers.lower():
            answer_score += question_weights[i]

    experience_score = 0
    for i, answer in enumerate(answers[:2]):
        try:
            experience = int(answer)
            if experience >= 5:
                experience_score += 2
            elif experience >= 3:
                experience_score += 1
        except ValueError:
            if answer.strip() == '':
                pass  # Skip empty answers
            else:
                raise ValueError(f"Invalid answer for question {i+1}: {answer}")

    final_score = answer_score + experience_score

    return final_score



def select_top_candidates(scores, num_candidates=2):
    sorted_scores = sorted(scores, key=lambda x: x[2], reverse=True)
    return sorted_scores[:num_candidates]
def send_email(to_email, subject, body):
    email_sender = 'punit76singh@gmail.com'
    email_password = 'axhiphbiaetsfaup'

    em = EmailMessage()
    em['from'] = email_sender
    em['To'] = to_email
    em['Subject'] = subject
    em.set_content(body)
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(email_sender, email_password)
            smtp.sendmail(email_sender, [to_email], em.as_string())
        print(f"Email sent to: {to_email}")
    except smtplib.SMTPException as e:
        print(f"Error sending email: {e}")

@app.route('/<path:filename>')
def serve_static(filename):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(os.path.join(root_dir, 'static'), filename)

@app.route('/upload', methods=['POST'])
def upload():
    if 'cv' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})

    cv_file = request.files['cv']
    if cv_file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})

    if cv_file and allowed_file(cv_file.filename):
        filename = secure_filename(cv_file.filename)
        cv_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        session['cv_filename'] = filename  
        show_chatbox = True  
        return jsonify({'status': 'success', 'show_chatbox': show_chatbox})

    return jsonify({'status': 'error', 'message': 'Invalid file format'})



@app.route('/')
def home():
    session['question_number'] = 1
    return render_template('index.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    session['name'] = data['name']
    session['email'] = data['email']
    session['job_description_text'] = "Your long job description text goes here"
    return jsonify({'status': 'success'})


@app.route('/submit', methods=['POST'])
def submit_answers():
    answers = request.form.getlist('answer')

    job_description_text = extract_text_from_docx(session['job_description_path'])
    cv_text = extract_text_from_docx(session['resume_path'])

    job_description_score = evaluate_job_description(job_description_text)
    cv_score = evaluate_job_description(cv_text)

    cv_matching_score = cv_score / job_description_score
    answer_score = calculate_answer_score(list(map(int, answers)))

    final_score = cv_matching_score + answer_score

    scores = [(cv_matching_score, answer_score, final_score)]
    top_candidates = select_top_candidates(scores, num_candidates=2)

    for candidate in top_candidates:
        send_email("candidate_email@example.com", "Interview Invitation", f"Congratulations! You have been selected for the interview. Your total score is {candidate[2]}. Please check your email for further instructions.")

    session.clear()

    return jsonify({'status': 'success', 'message': 'Answers recorded successfully.'})

@app.route('/questionnaire', methods=['POST'])
def questionnaire():
    if request.method == 'POST':
        session['question_number'] += 1

        if session['question_number'] > 5:
            session.clear()
            return jsonify({'status': 'completed'})  

        question_number = session['question_number']

        return jsonify({
            'status': 'success',
            'question': chatbox_responses.get(question_number, '')
        })

@app.route('/submit_questionnaire', methods=['POST'])
def submit_questionnaire():
    data = request.form.to_dict()
    name = data.get('name')
    email = data.get('email')
    cv_file = request.files.get('cv')
    answers = [data.get(f'answer{i}', '') for i in range(1, 6)]
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"CV File: {cv_file.filename if cv_file else None}")
    print("Answers:")
    for i, answer in enumerate(answers, start=1):
        print(f"Question {i}: {answer}")

    job_description_text = session['job_description_text'] 
    cv_text = extract_text_from_docx(cv_file)
    job_description_score = evaluate_job_description(job_description_text)
    cv_score = evaluate_job_description(cv_text)
    cv_matching_score = cv_score / job_description_score
    answer_score = calculate_answer_score(list(map(int, answers)))
    final_score = cv_matching_score + answer_score
    scores = [(cv_matching_score, answer_score, final_score)]
    top_candidates = select_top_candidates(scores, num_candidates=2)

    for candidate in top_candidates:
        send_email(email, "Interview Invitation", f"Congratulations! You have been selected for the physical interview. Your total score is {candidate[2]}. Please check your email for further instructions.  Thanks and regards Tech_Blasters")

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)