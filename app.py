import os
import datetime
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import check_password_hash

try:
    from psycopg2 import IntegrityError as PgIntegrityError
except ImportError:
    PgIntegrityError = sqlite3.IntegrityError

DBIntegrityError = (sqlite3.IntegrityError, PgIntegrityError)

from database import init_db, get_db_connection, is_postgres

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'college-mini-project-secret-key-2026')

# Context processor to make current_username available in all templates
@app.context_processor
def inject_user():
    return dict(current_username=session.get('username'))

# Prevent browser caching of protected pages (so Back button does not show them after logout)
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Login protection decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize database automatically on startup (creates tables, seeds admin user)
with app.app_context():
    init_db()

def calculate_payroll_breakdown(basic_salary):
    """
    Standard and clear payroll calculation:
    Allowances:
      - HRA (House Rent Allowance): 20% of Basic
      - DA (Dearness Allowance): 10% of Basic
      - Medical Allowance: 1,500.00
      - Gross Salary = Basic + HRA + DA + Medical
    Deductions:
      - PF (Provident Fund): 12% of Basic
      - Professional Tax (PT): 200.00
      - Total Deductions = PF + PT
    Net Salary = Gross Salary - Total Deductions
    """
    basic = float(basic_salary)
    hra = round(basic * 0.20, 2)
    da = round(basic * 0.10, 2)
    medical = 1500.0
    gross_salary = round(basic + hra + da + medical, 2)

    pf = round(basic * 0.12, 2)
    tax = 200.0
    total_deductions = round(pf + tax, 2)
    net_salary = round(gross_salary - total_deductions, 2)

    return {
        'basic_salary': basic,
        'hra': hra,
        'da': da,
        'medical': medical,
        'gross_salary': gross_salary,
        'pf': pf,
        'tax': tax,
        'total_deductions': total_deductions,
        'net_salary': net_salary
    }

def get_performance_rating(score):
    """
    Rating calculation:
    90.00 - 100.00: Excellent
    75.00 - 89.99:  Good (e.g. 80.00 -> Good)
    60.00 - 74.99:  Satisfactory
    50.00 - 59.99:  Average
    Below 50.00:    Needs Improvement
    """
    if score >= 90.0:
        return "Excellent"
    elif score >= 75.0:
        return "Good"
    elif score >= 60.0:
        return "Satisfactory"
    elif score >= 50.0:
        return "Average"
    else:
        return "Needs Improvement"

# ----------------- ROUTES ----------------- #

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication view with validation for empty fields, wrong username, and wrong password."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Validation: Empty fields
        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template('login.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()

        # Validation: Wrong username
        if not user:
            flash("Invalid username. Account does not exist.", "danger")
            return render_template('login.html')

        # Validation: Wrong password
        if not check_password_hash(user['password_hash'], password):
            flash("Invalid password. Please try again.", "danger")
            return render_template('login.html')

        # Authentication success: set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clears user session and redirects to login page."""
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Dashboard view with key statistics, quick navigation, and recent activity."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total employees count
    cursor.execute('SELECT COUNT(*) AS total_employees FROM employees')
    total_employees = int(cursor.fetchone()['total_employees'])

    # 2. Total monthly basic salary commitment
    cursor.execute('SELECT COALESCE(SUM(basic_salary), 0) AS total_payroll FROM employees')
    total_payroll = float(cursor.fetchone()['total_payroll'])

    # 3. Average performance score
    cursor.execute('SELECT COALESCE(AVG(overall_score), 0) AS avg_score FROM appraisals')
    avg_score_raw = float(cursor.fetchone()['avg_score'])
    avg_score = round(avg_score_raw, 2)
    avg_rating = get_performance_rating(avg_score) if total_employees > 0 and avg_score > 0 else "N/A"

    # 4. Department counts
    cursor.execute('''
        SELECT department, COUNT(*) as count 
        FROM employees 
        GROUP BY department 
        ORDER BY count DESC
    ''')
    departments = cursor.fetchall()

    # 5. Recent employees list
    cursor.execute('''
        SELECT emp_id, name, department, designation, basic_salary, created_at 
        FROM employees 
        ORDER BY id DESC 
        LIMIT 5
    ''')
    recent_employees = cursor.fetchall()

    # 6. Recent payroll count
    cursor.execute('SELECT COUNT(*) AS total_payslips FROM payroll_records')
    total_payslips = int(cursor.fetchone()['total_payslips'])

    conn.close()

    return render_template(
        'index.html',
        total_employees=total_employees,
        total_payroll=total_payroll,
        avg_score=avg_score,
        avg_rating=avg_rating,
        departments=departments,
        recent_employees=recent_employees,
        total_payslips=total_payslips
    )

@app.route('/employees')
@login_required
def view_employees():
    """View directory of all registered employees."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, emp_id, name, department, designation, basic_salary, created_at 
        FROM employees 
        ORDER BY id DESC
    ''')
    employees = cursor.fetchall()
    conn.close()
    return render_template('employees.html', employees=employees)

@app.route('/add-employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    """Add a new employee record with validation for required fields, positive salary, and duplicate ID."""
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        salary_str = request.form.get('basic_salary', '').strip()

        # Validation: Required fields
        if not emp_id or not name or not department or not designation or not salary_str:
            flash("All fields are required. Please fill in every detail.", "danger")
            return render_template('add_employee.html', form_data=request.form)

        # Validation: Positive salary
        try:
            basic_salary = float(salary_str)
            if basic_salary <= 0:
                flash("Basic salary must be a positive number greater than 0.", "danger")
                return render_template('add_employee.html', form_data=request.form)
        except ValueError:
            flash("Please enter a valid numeric salary.", "danger")
            return render_template('add_employee.html', form_data=request.form)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Validation: Employee ID must be unique
        cursor.execute('SELECT emp_id FROM employees WHERE UPPER(emp_id) = UPPER(%s)', (emp_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            flash(f"Employee ID '{emp_id}' already exists! Please use a unique Employee ID.", "danger")
            return render_template('add_employee.html', form_data=request.form)

        # Insert new employee
        try:
            cursor.execute('''
                INSERT INTO employees (emp_id, name, department, designation, basic_salary)
                VALUES (%s, %s, %s, %s, %s)
            ''', (emp_id, name, department, designation, basic_salary))
            conn.commit()
            conn.close()
            flash(f"Employee {name} ({emp_id}) added successfully!", "success")
            return redirect(url_for('view_employees'))
        except DBIntegrityError:
            conn.close()
            flash(f"Employee ID '{emp_id}' already exists! Please use a unique Employee ID.", "danger")
            return render_template('add_employee.html', form_data=request.form)
        except Exception:
            conn.close()
            flash("An unexpected error occurred while saving employee. Please try again.", "danger")
            return render_template('add_employee.html', form_data=request.form)

    return render_template('add_employee.html', form_data={})

@app.route('/payroll', methods=['GET', 'POST'])
@login_required
def payroll():
    """
    Payroll calculation & payslip generation view:
    Computes HRA (20%), DA (10%), Medical Allowance (1500), PF (12%), PT (200),
    Gross Salary, and Net Salary. Saves generated payslip record.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all employees for selection
    cursor.execute('SELECT emp_id, name, department, designation, basic_salary FROM employees ORDER BY name ASC')
    employees = cursor.fetchall()

    selected_emp_id = request.args.get('emp_id', '')
    selected_employee = None
    calculated_payroll = None
    payslip_id = None

    if selected_emp_id:
        cursor.execute('SELECT * FROM employees WHERE emp_id = %s', (selected_emp_id,))
        selected_employee = cursor.fetchone()
        if selected_employee:
            calculated_payroll = calculate_payroll_breakdown(selected_employee['basic_salary'])

    # Handle POST to generate & save payslip record
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip()
        pay_month = request.form.get('pay_month', '').strip()
        pay_year = request.form.get('pay_year', '').strip()

        if not emp_id or not pay_month or not pay_year:
            flash("Please select an employee, month, and year.", "warning")
        else:
            cursor.execute('SELECT * FROM employees WHERE emp_id = %s', (emp_id,))
            selected_employee = cursor.fetchone()

            if selected_employee:
                selected_emp_id = emp_id
                calc = calculate_payroll_breakdown(selected_employee['basic_salary'])
                calculated_payroll = calc

                try:
                    cursor.execute('''
                        INSERT INTO payroll_records (
                            emp_id, pay_month, pay_year, basic_salary, 
                            hra, da, medical, gross_salary, 
                            pf, tax, total_deductions, net_salary
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (
                        emp_id, pay_month, int(pay_year), calc['basic_salary'],
                        calc['hra'], calc['da'], calc['medical'], calc['gross_salary'],
                        calc['pf'], calc['tax'], calc['total_deductions'], calc['net_salary']
                    ))
                    returned_row = cursor.fetchone()
                    if returned_row:
                        payslip_id = returned_row['id'] if isinstance(returned_row, dict) else returned_row[0]
                    conn.commit()
                    flash(f"Payslip for {selected_employee['name']} ({pay_month} {pay_year}) generated successfully!", "success")
                except Exception as e:
                    flash("Unable to save payslip record. Please try again.", "danger")
            else:
                flash("Selected employee not found.", "danger")

    # Fetch recent payroll records
    cursor.execute('''
        SELECT p.*, e.name, e.department, e.designation
        FROM payroll_records p
        JOIN employees e ON p.emp_id = e.emp_id
        ORDER BY p.id DESC
        LIMIT 10
    ''')
    recent_payrolls = cursor.fetchall()
    conn.close()

    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    current_year = datetime.datetime.now().year
    current_month = months[datetime.datetime.now().month - 1]

    return render_template(
        'payroll.html',
        employees=employees,
        selected_emp_id=selected_emp_id,
        selected_employee=selected_employee,
        payroll=calculated_payroll,
        recent_payrolls=recent_payrolls,
        months=months,
        current_year=current_year,
        current_month=current_month,
        payslip_id=payslip_id
    )

@app.route('/payroll/slip/<int:record_id>')
@login_required
def view_payslip(record_id):
    """Dedicated printable and clean payslip document view."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, e.name, e.department, e.designation
        FROM payroll_records p
        JOIN employees e ON p.emp_id = e.emp_id
        WHERE p.id = %s
    ''', (record_id,))
    slip = cursor.fetchone()
    conn.close()

    if not slip:
        flash("Payslip record not found.", "danger")
        return redirect(url_for('payroll'))

    return render_template('payslip_view.html', slip=slip)

@app.route('/appraisal', methods=['GET', 'POST'])
@login_required
def appraisal():
    """
    Performance appraisal evaluation:
    Productivity, Quality, Teamwork, Attendance (each 0 - 100).
    Overall score = Average.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT emp_id, name, department, designation FROM employees ORDER BY name ASC')
    employees = cursor.fetchall()

    selected_emp_id = request.args.get('emp_id', '')
    evaluated_result = None

    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip()
        selected_emp_id = emp_id
        prod_str = request.form.get('productivity', '').strip()
        qual_str = request.form.get('quality', '').strip()
        team_str = request.form.get('teamwork', '').strip()
        att_str = request.form.get('attendance', '').strip()
        remarks = request.form.get('remarks', '').strip()

        # Validation: All fields required
        if not emp_id or not prod_str or not qual_str or not team_str or not att_str:
            flash("All performance scores (Productivity, Quality, Teamwork, Attendance) are required.", "danger")
        else:
            try:
                prod = float(prod_str)
                qual = float(qual_str)
                team = float(team_str)
                att = float(att_str)

                # Validation: 0 to 100
                if any(score < 0 or score > 100 for score in [prod, qual, team, att]):
                    flash("Each score must be a number between 0 and 100.", "danger")
                else:
                    overall = round((prod + qual + team + att) / 4.0, 2)
                    rating = get_performance_rating(overall)

                    cursor.execute('''
                        INSERT INTO appraisals (
                            emp_id, productivity, quality, teamwork, attendance, 
                            overall_score, rating, remarks
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (emp_id, prod, qual, team, att, overall, rating, remarks))
                    conn.commit()

                    cursor.execute('SELECT * FROM employees WHERE emp_id = %s', (emp_id,))
                    emp_details = cursor.fetchone()

                    evaluated_result = {
                        'employee': emp_details,
                        'productivity': prod,
                        'quality': qual,
                        'teamwork': team,
                        'attendance': att,
                        'overall_score': overall,
                        'rating': rating,
                        'remarks': remarks
                    }
                    flash(f"Performance appraisal submitted! Overall Score: {overall:.2f} ({rating})", "success")
            except ValueError:
                flash("Please enter valid numerical scores between 0 and 100.", "danger")

    # Fetch appraisal history
    cursor.execute('''
        SELECT a.*, e.name, e.department, e.designation
        FROM appraisals a
        JOIN employees e ON a.emp_id = e.emp_id
        ORDER BY a.id DESC
        LIMIT 10
    ''')
    recent_appraisals = cursor.fetchall()
    conn.close()

    return render_template(
        'appraisal.html',
        employees=employees,
        selected_emp_id=selected_emp_id,
        evaluated_result=evaluated_result,
        recent_appraisals=recent_appraisals,
        form_data=request.form if request.method == 'POST' else {}
    )

@app.route('/delete-employee/<string:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    """Deletes an employee from the system."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM employees WHERE emp_id = %s', (emp_id,))
    conn.commit()
    conn.close()
    flash(f"Employee {emp_id} has been removed.", "info")
    return redirect(url_for('view_employees'))

# API endpoint for interactive JavaScript preview
@app.route('/api/employee/<string:emp_id>')
@login_required
def api_get_employee(emp_id):
    """Returns employee details and computed payroll as JSON for dynamic client-side preview."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees WHERE emp_id = %s', (emp_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Employee not found'}), 404

    data = dict(row)
    data['basic_salary'] = float(data['basic_salary'])
    if 'created_at' in data and data['created_at']:
        data['created_at'] = str(data['created_at'])
    data['payroll'] = calculate_payroll_breakdown(data['basic_salary'])
    return jsonify(data)

@app.route('/favicon.ico')
def favicon():
    """Favicon endpoint returning 204 No Content to avoid browser 404 log warnings."""
    return '', 204

@app.route('/api/check-emp-id/<string:emp_id>')
@login_required
def api_check_emp_id(emp_id):
    """API endpoint to check if an Employee ID already exists (case-insensitive)."""
    clean_id = emp_id.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT emp_id FROM employees WHERE UPPER(emp_id) = UPPER(%s)', (clean_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return jsonify({'exists': exists, 'emp_id': clean_id})

if __name__ == '__main__':
    # Production-ready entry point listening on 0.0.0.0 and environment PORT
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
