from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sathish_super_secret_key_2026'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///roofing_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

if not os.path.exists('static'):
    os.makedirs('static')

# ---------------------------------------------------------
# DATABASE MODELS
# ---------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)

class DailyWorkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    work_details = db.Column(db.Text, nullable=False)
    workers_count = db.Column(db.Integer, nullable=False)
    expenses = db.Column(db.Float, default=0.0)
    submitted_by = db.Column(db.String(50), nullable=False)

class CalculationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100),nullable=True)
    timestamp = db.Column(db.String(50), default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    length = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    total_area = db.Column(db.Float, nullable=False)
    roof_style = db.Column(db.String(50), nullable=False)
    sheet_type = db.Column(db.String(50), nullable=False)
    grand_total = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='owner_admin').first():
        db.session.add(User(username='owner_admin', password='owner@123', role='admin', full_name='Fabrication Owner'))
    if not User.query.filter_by(username='site_worker').first():
        db.session.add(User(username='site_worker', password='worker@123', role='worker', full_name='Site Fabricator'))
    db.session.commit()

# ---------------------------------------------------------
# HELPER FUNCTIONS (Site Photo Overlay Drawing & Blueprint)
# ---------------------------------------------------------
def process_site_drawing(uploaded_file, length, width, roof_type):
    output_path = os.path.join('static', 'roof_blueprint.png')
    
    if uploaded_file and uploaded_file.filename != '':
        # Site Photo மீது Structure மேலடுக்கு (Overlay) வரைதல்
        img = Image.open(uploaded_file).convert("RGBA")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        
        # Structure கோடுகள் வரைய
        line_color = (255, 215, 0, 255) # Gold
        pillar_color = (255, 0, 0, 255) # Red
        
        # Pillars
        draw.rectangle([w*0.2, h*0.4, w*0.22, h*0.8], fill=pillar_color)
        draw.rectangle([w*0.78, h*0.4, w*0.8, h*0.8], fill=pillar_color)
        
        if roof_type == 'double':
            # A-Type Roof Structure
            draw.line([(w*0.2, h*0.4), (w*0.5, h*0.25), (w*0.8, h*0.4)], fill=line_color, width=6)
            draw.line([(w*0.2, h*0.4), (w*0.8, h*0.4)], fill=line_color, width=4)
        else:
            # Single Slope Structure
            draw.line([(w*0.2, h*0.3), (w*0.8, h*0.4)], fill=line_color, width=6)
            draw.line([(w*0.2, h*0.4), (w*0.8, h*0.4)], fill=line_color, width=4)

        img.convert("RGB").save(output_path)
    else:
        # Standard 2D Blueprint Graphics
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.plot([0, width, width, 0, 0], [0, 0, length, length, 0], color='#1e3c72', linewidth=2.5)
        if roof_type == 'double':
            ax.plot([width/2, width/2], [0, length], color='#e74c3c', linestyle='--', label='Ridge Cap')
        ax.set_title(f"2D Structural Layout ({width}' x {length}')", fontsize=10)
        ax.grid(True, linestyle=':', alpha=0.5)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        
    return output_path

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def home():
    result = None
    if request.method == 'POST':
        try:
            customer_name = request.form.get('customer_name' , 'General Customer')
            location = request.form.get('location' , 'N/A')
            length = float(request.form.get('length', 0))
            width = float(request.form.get('width', 0))
            roof_type = request.form.get('roof_type')
            sheet_type = request.form.get('sheet_type')
            truss_pipe = request.form.get('truss_pipe')
            purlin_pipe = request.form.get('purlin_pipe')
            truss_spacing = float(request.form.get('truss_spacing', 8))
            site_photo = request.files.get('site_photo')

            # Calculations
            roof_type_name = "இரட்டைச் சாய்வு (A-Type)" if roof_type == 'double' else "ஒற்றைச் சாய்வு (Single Slope)"
            slope_length = round((width / 2) * 1.15 if roof_type == 'double' else width * 1.05, 2)
            inner_room_span = round(width - 1.5, 2)
            
            # Sheets & Ridge Cap
            total_sheets = int((length / 3.5) * (2 if roof_type == 'double' else 1)) + 1
            ridge_cap_length = length if roof_type == 'double' else 0
            
            # Pipes & Pillars
            truss_frames_count = int(length / truss_spacing) + 1
            total_truss_feet = round(truss_frames_count * slope_length * (2 if roof_type == 'double' else 1), 2)
            total_truss_full_pipes = int(total_truss_feet / 20) + 1

            total_purlin_lines = int(slope_length / 3) + 1
            total_purlin_feet = round(total_purlin_lines * length * (2 if roof_type == 'double' else 1), 2)
            total_purlin_full_pipes = int(total_purlin_feet / 20) + 1

            total_pillars = 4
            total_pillar_feet = total_pillars * 10
            total_pillar_full_pipes = int(total_pillar_feet / 20) + 1

            # Costings
            total_sheet_cost = round(total_sheets * 1200 + (ridge_cap_length * 150), 2)
            total_pipe_cost = round((total_truss_full_pipes + total_purlin_full_pipes + total_pillar_full_pipes) * 1800, 2)
            grand_total = total_sheet_cost + total_pipe_cost

            result = {
                'roof_type_name': roof_type_name,
                'slope_length': slope_length,
                'inner_room_span': inner_room_span,
                'sheet_name': "ஆஸ்பெஸ்டாஸ்" if sheet_type == 'asbestos' else "கூலிங் மெட்டல் ஷீட்",
                'total_sheets': total_sheets,
                'ridge_cap_length': ridge_cap_length,
                'truss_frames_count': truss_frames_count,
                'truss_pipe_name': truss_pipe,
                'total_truss_feet': total_truss_feet,
                'total_truss_full_pipes': total_truss_full_pipes,
                'total_purlin_lines': total_purlin_lines,
                'purlin_pipe_name': purlin_pipe,
                'total_purlin_feet': total_purlin_feet,
                'total_purlin_full_pipes': total_purlin_full_pipes,
                'total_pillars': total_pillars,
                'total_pillar_feet': total_pillar_feet,
                'total_pillar_full_pipes': total_pillar_full_pipes,
                'total_sheet_cost': total_sheet_cost,
                'total_pipe_cost': total_pipe_cost,
                'grand_total': grand_total
            }

            process_site_drawing(site_photo, length, width, roof_type)

            new_calc = CalculationLog(
                customer_name=customer_name,
                location=location,
                length=length, width=width, total_area=round(length*width, 2),
                roof_style=roof_type_name, sheet_type=sheet_type, grand_total=grand_total
            )
            db.session.add(new_calc)
            db.session.commit()

        except Exception as e:
            result = {'error': f'பிழை ஏற்பட்டது: {str(e)}'}

    history_logs = CalculationLog.query.order_by(CalculationLog.id.desc()).limit(20).all()

    return render_template('index.html', result=result, history_logs=history_logs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username'), password=request.form.get('password')).first()
        if user:
            session['loggedin'] = True
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'worker_entry'))
        msg = 'தவறான பயனர் பெயர் அல்லது கடவுச்சொல்!'
    return render_template('login.html', msg=msg)

@app.route('/history/<int:calc_id>')
def view_history_detail(calc_id):
    # குறிப்பிட்ட ID கொண்ட கணக்கீட்டை மட்டும் டேட்டாபேஸிலிருந்து எடுத்தல்
    log = CalculationLog.query.get_or_404(calc_id)
    return render_template('history_detail.html', log=log)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/worker-entry', methods=['GET', 'POST'])
def worker_entry():
    if not session.get('loggedin'): return redirect(url_for('login'))
    msg = ''
    if request.method == 'POST':
        log = DailyWorkLog(
            date=request.form.get('date'), location=request.form.get('location'),
            customer_name=request.form.get('customer_name'), work_details=request.form.get('work_details'),
            workers_count=int(request.form.get('workers_count', 1)), expenses=float(request.form.get('expenses', 0)),
            submitted_by=session.get('username')
        )
        db.session.add(log)
        db.session.commit()
        msg = 'பதிவு செய்யப்பட்டது!'
    return render_template('worker_entry.html', msg=msg)

@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('loggedin') or session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template('admin_dashboard.html', logs=DailyWorkLog.query.order_by(DailyWorkLog.id.desc()).all())

@app.route('/sathish-developer-control', methods=['GET', 'POST'])
def sathish_developer_control():
    auth = session.get('super_dev_auth', False)
    msg = ''
    if request.method == 'POST' and not auth:
        if request.form.get('master_key') == 'SathishDev2026@Pass':
            session['super_dev_auth'] = True
            auth = True
        else: msg = 'Invalid Key!'
    return render_template('developer_control.html', auth=auth, users=User.query.all() if auth else [],
                           logs=DailyWorkLog.query.all() if auth else [], calc_logs=CalculationLog.query.all() if auth else [], msg=msg)

if __name__ == '__main__':
    app.run(debug=True)