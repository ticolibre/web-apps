import os
import re
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from flask import Flask, request, send_file, render_template, jsonify
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = tempfile.mkdtemp()
DOWNLOAD_FOLDER = tempfile.mkdtemp()
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_homework_name(homework_name):
    match = re.search(r'Homework\s*(?:\$\$|#)?(\d+)', str(homework_name))
    if match:
        return f"Homework {match.group(1)}", int(match.group(1))
    return "Unknown Homework", float('inf')

def round_to_nearest_quarter(number):
    return round(number * 4) / 4

class CustomPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 11)
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footer_text = f"Report generated by TicoLibre on {current_datetime}"
        self.cell(0, 10, footer_text, 0, 0, 'C')

def generate_student_pdfs(input_file_path, evaluation, professor, course):
    # Ensure download directory exists
    os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
    
    # Load the spreadsheet
    data = pd.read_excel(input_file_path)

    # Columns related to homework
    homework_columns = data.columns[4:-1]

    # Generate PDFs for each student
    student_reports = []
    for idx, student in data.iterrows():
        # Collect homework results for the student
        student_homeworks = student[homework_columns].to_dict()
        
        # Create a sanitized file name using the student's full name
        student_full_name = f"{student['First name']}_{student['Last name']}".replace(" ", "_")
        
        # Ensure filename is compatible and secure
        pdf_filename = secure_filename(f"{student_full_name}_report.pdf")
        full_pdf_path = os.path.join(app.config['DOWNLOAD_FOLDER'], pdf_filename)
        
        # Generate PDF
        pdf = CustomPDF(format='A4')
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)

        # Add campus, professor, and course information from user input
        pdf.cell(0, 10, f"Evaluation: {evaluation}", ln=True, align='C')
        pdf.cell(0, 10, f"Professor: {professor}", ln=True, align='C')
        pdf.cell(0, 10, f"Course: {course}", ln=True, align='C')
        pdf.ln(10)

        # Center and add student details
        pdf.cell(0, 10, f"Username: {student['Username']}", ln=True, align='C')
        pdf.cell(0, 10, f"Name: {student['First name']} {student['Last name']}", ln=True, align='C')
        pdf.cell(0, 10, f"Email: {student['Email address']}", ln=True, align='C')
        pdf.ln(10)

        # Add homework results section title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, "Homework Results:", ln=True, align='C')
        pdf.ln(5)

        # Table dimensions
        table_width = 150
        left_margin = (pdf.w - table_width) / 2

        # Create a table header
        pdf.set_x(left_margin)
        pdf.cell(100, 10, 'Homework', 1, 0, 'C')
        pdf.cell(50, 10, 'Score', 1, 1, 'C')

        # Set font for table contents
        pdf.set_font('Arial', '', 16)

        # Sort and display homework results
        sorted_homeworks = sorted(
            [(clean_homework_name(homework)[0], score) for homework, score in student_homeworks.items()],
            key=lambda x: clean_homework_name(x[0])[1]
        )

        for cleaned_homework_name, score in sorted_homeworks:
            pdf.set_x(left_margin)
            pdf.cell(100, 10, f"{cleaned_homework_name}", 1, 0, 'C')
            pdf.cell(50, 10, f"{score}", 1, 1, 'C')

        # Add final result
        final_result = round_to_nearest_quarter(student['Results'])
        pdf.ln(10)
        pdf.cell(0, 10, f"Final Result: {final_result}", ln=True, align='C')

        # Output the PDF
        pdf.output(full_pdf_path)

        # Store student report information
        student_reports.append({
            'name': f"{student['First name']} {student['Last name']}",
            'filename': pdf_filename
        })

    return student_reports

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'excel_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    excel_file = request.files['excel_file']
    
    # Verify configuration inputs
    evaluation = request.form.get('evaluation')
    professor = request.form.get('professor')
    course = request.form.get('course')
    
    if not all([evaluation, professor, course]):
        return jsonify({'error': 'Missing configuration details'}), 400
    
    # If no file is selected
    if excel_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Check file types
    if not allowed_file(excel_file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    # Save file
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(excel_file.filename))
    
    excel_file.save(excel_path)
    
    try:
        # Generate PDFs with configuration details
        student_reports = generate_student_pdfs(excel_path, evaluation, professor, course)
        return jsonify(student_reports)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        # Ensure the filename is secure 
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], safe_filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)