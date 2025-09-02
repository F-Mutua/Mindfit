from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from models import Base, User, StudySession, MoodLevel, WellnessEntry, StudyGoal
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import bcrypt
import os
from dotenv import load_dotenv
from functools import wraps
import re
import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# MySQL configurations
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'mindfit_user')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'supersecret')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'mindfit')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Initialize MySQL
mysql = MySQL(app)

# SQLAlchemy configuration
DB_URI = f"mysql+pymysql://{app.config['MYSQL_USER']}:{app.config['MYSQL_PASSWORD']}@{app.config['MYSQL_HOST']}/{app.config['MYSQL_DB']}"
engine = create_engine(DB_URI)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Email validation regex
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password', '').encode('utf-8')
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return redirect(url_for('login'))
            
        cur = mysql.connection.cursor()
        try:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
                session['user_id'] = user['id']
                session['name'] = user['name']
                session['email'] = user['email']
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password', 'error')
                return redirect(url_for('login'))
        finally:
            cur.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate inputs
        if not all([name, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return redirect(url_for('register'))
            
        if not is_valid_email(email):
            flash('Please enter a valid email address', 'error')
            return redirect(url_for('register'))
            
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
            
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        cur = mysql.connection.cursor()
        try:
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Email already registered', 'error')
                return redirect(url_for('register'))
            
            # Create new user
            cur.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            mysql.connection.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('register'))
            
        finally:
            cur.close()
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing study analytics and wellness overview."""
    try:
        # Get study analytics for the last 7 days
        analytics = get_study_analytics(session['user_id'], days=7)
        
        # Calculate productivity score
        productivity_score = calculate_productivity_score(session['user_id'], db_session)
        
        # Get recent study sessions
        recent_sessions = db_session.query(StudySession).filter(
            StudySession.user_id == session['user_id']
        ).order_by(StudySession.created_at.desc()).limit(5).all()
        
        # Get recent wellness entries
        recent_entries = db_session.query(WellnessEntry).filter(
            WellnessEntry.user_id == session['user_id']
        ).order_by(WellnessEntry.created_at.desc()).limit(5).all()
        
        # Get active study goals
        active_goals = db_session.query(StudyGoal).filter(
            StudyGoal.user_id == session['user_id'],
            StudyGoal.is_completed == False
        ).order_by(StudyGoal.deadline).all()
        
        # Get personalized recommendations
        recommendations = generate_study_recommendations(session['user_id'], db_session)
        
        # Calculate total study time this week (in hours)
        total_study_hours = analytics.get('total_study_hours', 0)
        
        # Calculate average stress level (1-10 scale, lower is better)
        avg_stress = analytics.get('avg_stress', 5)  # Default to neutral if no data
        
        return render_template(
            'dashboard.html',
            analytics=analytics,
            productivity_score=productivity_score,
            recent_sessions=recent_sessions,
            recent_entries=recent_entries,
            active_goals=active_goals,
            recommendations=recommendations,
            total_study_hours=total_study_hours,
            avg_stress=avg_stress,
            MoodLevel=MoodLevel
        )
        
    except Exception as e:
        app.logger.error(f'Dashboard error: {str(e)}')
        flash('An error occurred while loading the dashboard. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/study-session/new', methods=['GET', 'POST'])
@login_required
def new_study_session():
    """Create a new study session."""
    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '').strip()
            duration = int(request.form.get('duration', 0))
            pre_mood = request.form.get('pre_mood')
            post_mood = request.form.get('post_mood')
            notes = request.form.get('notes', '').strip()
            
            # Validate inputs
            if not subject or duration <= 0:
                flash('Please provide a subject and valid duration', 'error')
                return redirect(url_for('new_study_session'))
            
            # Analyze sentiment from notes if provided
            sentiment = {"label": "NEUTRAL", "score": 0.5}
            if notes:
                sentiment = analyze_sentiment(notes)
            
            # Create new study session
            session = StudySession(
                user_id=session['user_id'],
                subject=subject,
                duration=duration,
                pre_mood=MoodLevel(pre_mood) if pre_mood else None,
                post_mood=MoodLevel(post_mood) if post_mood else None,
                notes=notes,
                sentiment_score=sentiment['score'] if sentiment['label'] == 'POSITIVE' else -sentiment['score']
            )
            
            db_session.add(session)
            db_session.commit()
            
            flash('Study session logged successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except ValueError as ve:
            db_session.rollback()
            flash('Invalid input values. Please check your entries.', 'error')
            app.logger.error(f'ValueError in new_study_session: {str(ve)}')
        except Exception as e:
            db_session.rollback()
            flash('An error occurred while saving your study session.', 'error')
            app.logger.error(f'Error in new_study_session: {str(e)}')
    
    # For GET request or if there was an error
    return render_template('study_session/new.html', MoodLevel=MoodLevel)

@app.route('/study-session/<int:session_id>')
@login_required
def view_study_session(session_id):
    """View details of a specific study session."""
    session = db_session.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.user_id == session['user_id']
    ).first_or_404()
    
    return render_template('study_session/view.html', session=session)

@app.route('/study-session/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_study_session(session_id):
    """Delete a study session."""
    session = db_session.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.user_id == session['user_id']
    ).first_or_404()
    
    try:
        db_session.delete(session)
        db_session.commit()
        flash('Study session deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash('An error occurred while deleting the study session.', 'error')
        app.logger.error(f'Error deleting study session: {str(e)}')
    
    return redirect(url_for('dashboard'))

@app.route('/api/study-sessions')
@login_required
def get_study_sessions():
    """API endpoint to get study sessions for the current user (for charts)."""
    try:
        days = int(request.args.get('days', 7))  # Default to 7 days
        analytics = get_study_analytics(session['user_id'], days=days)
        
        return jsonify({
            'success': True,
            'data': {
                'dates': analytics['dates'],
                'study_hours': analytics['study_hours'],
                'stress_levels': analytics['stress_levels'],
                'energy_levels': analytics['energy_levels'],
                'subjects': analytics['subjects']
            }
        })
    except Exception as e:
        app.logger.error(f'Error in get_study_sessions: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Failed to fetch study sessions data.'
        }), 500

@app.route('/add_session', methods=['POST'])
@login_required
def add_session():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        duration = request.form.get('duration', 0, type=int)
        pre_mood = request.form.get('pre_mood', '').strip()
        post_mood = request.form.get('post_mood', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not subject or duration <= 0:
            flash('Subject and valid duration are required', 'error')
            return redirect(url_for('dashboard'))
            
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO study_sessions 
                (user_id, subject, duration, pre_mood, post_mood, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'], subject, duration, 
                pre_mood or None, post_mood or None, notes or None
            ))
            mysql.connection.commit()
            flash('Study session added successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Failed to add study session', 'error')
        finally:
            cur.close()
            
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/study-sessions')
@login_required
def study_sessions():
    """
    Display a paginated list of study sessions with filtering and sorting options.
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query
    query = db_session.query(StudySession).filter(StudySession.user_id == session['user_id'])
    
    # Apply filters
    subject_filter = request.args.get('subject', '').strip()
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    if subject_filter:
        query = query.filter(StudySession.subject.ilike(f'%{subject_filter}%'))
    
    if date_from:
        query = query.filter(StudySession.date >= datetime.datetime.strptime(date_from, '%Y-%m-%d').date())
    
    if date_to:
        query = query.filter(StudySession.date <= datetime.datetime.strptime(date_to, '%Y-%m-%d').date())
    
    # Apply sorting
    sort_by = request.args.get('sort', 'date_desc')
    if sort_by == 'date_asc':
        query = query.order_by(StudySession.date.asc(), StudySession.start_time.asc())
    elif sort_by == 'duration_desc':
        query = query.order_by(StudySession.duration_minutes.desc())
    elif sort_by == 'duration_asc':
        query = query.order_by(StudySession.duration_minutes.asc())
    else:  # Default: date_desc
        query = query.order_by(StudySession.date.desc(), StudySession.start_time.desc())
    
    # Paginate the results
    sessions = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate statistics
    stats = {
        'total_sessions': query.count(),
        'total_hours': query.with_entities(db_session.func.sum(StudySession.duration_minutes)).scalar() or 0 // 60,
        'total_minutes': query.with_entities(db_session.func.sum(StudySession.duration_minutes)).scalar() or 0 % 60,
    }
    
    # Calculate average mood (if available)
    avg_mood = query.with_entities(db_session.func.avg(StudySession.mood_level)).scalar()
    if avg_mood is not None:
        if avg_mood <= 1.5:
            stats['average_mood'] = 'Very Stressed'
        elif avg_mood <= 2.5:
            stats['average_mood'] = 'Stressed'
        elif avg_mood <= 3.5:
            stats['average_mood'] = 'Neutral'
        elif avg_mood <= 4.5:
            stats['average_mood'] = 'Relaxed'
        else:
            stats['average_mood'] = 'Very Relaxed'
    else:
        stats['average_mood'] = 'N/A'
    
    return render_template('study_sessions.html', 
                         sessions=sessions, 
                         stats=stats,
                         sort_by=sort_by)

@app.route('/sessions/<int:session_id>')
@login_required
def view_study_session(session_id):
    """View details of a specific study session."""
    session_data = db_session.query(StudySession).filter(
        StudySession.id == session_id,
        StudySession.user_id == session['user_id']
    ).first()
    
    if not session_data:
        flash('Session not found or access denied.', 'danger')
        return redirect(url_for('study_sessions'))
    
    # Convert mood level to text for display
    mood_texts = {
        1: 'Very Stressed',
        2: 'Stressed',
        3: 'Neutral',
        4: 'Relaxed',
        5: 'Very Relaxed'
    }
    
    # Get subject icon based on subject or default to 'book'
    subject_icons = {
        'math': 'calculator',
        'science': 'flask',
        'history': 'landmark',
        'english': 'book-open',
        'programming': 'code',
        'art': 'palette',
        'music': 'music'
    }
    
    session_data.mood_text = mood_texts.get(session_data.mood_level, 'N/A')
    session_data.subject_icon = subject_icons.get(session_data.subject.lower(), 'book')
    
    # Parse tags if they exist
    session_data.tags = session_data.tags.split(',') if session_data.tags else []
    
    return render_template('view_session.html', session=session_data)

@app.route('/sessions/new', methods=['GET', 'POST'])
@login_required
def new_study_session():
    """Create a new study session."""
    if request.method == 'POST':
        # Extract form data
        subject = request.form.get('subject')
        duration = int(request.form.get('duration', 0))
        date = datetime.datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        start_time = datetime.datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        mood_level = int(request.form.get('mood_level', 3))
        notes = request.form.get('notes', '').strip()
        tags = request.form.get('tags', '').strip()
        completed = 'completed' in request.form
        
        # Create new session
        new_session = StudySession(
            user_id=session['user_id'],
            subject=subject,
            duration_minutes=duration,
            date=date,
            start_time=start_time,
            mood_level=mood_level,
            notes=notes,
            tags=tags,
            completed=completed,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )
        
        db_session.add(new_session)
        db_session.commit()
        
        flash('Study session logged successfully!', 'success')
        return redirect(url_for('study_sessions'))
    
    # Default values for the form
    today = datetime.date.today()
    default_time = datetime.datetime.now().strftime('%H:%M')
    
    return render_template('study_session_form.html', 
                         session=None,
                         default_date=today,
                         default_time=default_time)

# API Endpoints
@app.route('/api/sessions', methods=['GET'])
@login_required
def api_get_sessions():
    """
    API endpoint to get paginated list of study sessions with filtering
    Query params:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10, max: 50)
    - subject: Filter by subject (partial match)
    - date_from: Filter by start date (YYYY-MM-DD)
    - date_to: Filter by end date (YYYY-MM-DD)
    - sort: Sort field (date, duration)
    - order: Sort order (asc, desc)
    """
    try:
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)
        
        # Base query
        query = db_session.query(StudySession).filter(StudySession.user_id == session['user_id'])
        
        # Apply filters
        if 'subject' in request.args:
            query = query.filter(StudySession.subject.ilike(f'%{request.args["subject"]}%'))
            
        if 'date_from' in request.args:
            query = query.filter(StudySession.date >= datetime.datetime.strptime(
                request.args['date_from'], '%Y-%m-%d'
            ).date())
            
        if 'date_to' in request.args:
            query = query.filter(StudySession.date <= datetime.datetime.strptime(
                request.args['date_to'], '%Y-%m-%d'
            ).date())
        
        # Apply sorting
        sort_field = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')
        
        sort_mapping = {
            'date': StudySession.date,
            'duration': StudySession.duration_minutes,
            'mood': StudySession.mood_level
        }
        
        sort_field = sort_mapping.get(sort_field, StudySession.date)
        sort_field = sort_field.desc() if sort_order == 'desc' else sort_field.asc()
        query = query.order_by(sort_field)
        
        # Paginate results
        paginated_sessions = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response
        sessions_data = [{
            'id': session.id,
            'subject': session.subject,
            'date': session.date.isoformat(),
            'start_time': session.start_time.isoformat() if session.start_time else None,
            'duration_minutes': session.duration_minutes,
            'mood_level': session.mood_level,
            'mood_text': {
                1: 'Very Stressed',
                2: 'Stressed',
                3: 'Neutral',
                4: 'Relaxed',
                5: 'Very Relaxed'
            }.get(session.mood_level, 'Unknown'),
            'notes': session.notes,
            'tags': session.tags.split(',') if session.tags else [],
            'completed': session.completed,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'updated_at': session.updated_at.isoformat() if session.updated_at else None
        } for session in paginated_sessions.items]
        
        response = {
            'success': True,
            'data': sessions_data,
            'pagination': {
                'page': paginated_sessions.page,
                'per_page': paginated_sessions.per_page,
                'total_pages': paginated_sessions.pages,
                'total_items': paginated_sessions.total,
                'has_prev': paginated_sessions.has_prev,
                'has_next': paginated_sessions.has_next,
                'prev_num': paginated_sessions.prev_num,
                'next_num': paginated_sessions.next_num
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/sessions/<int:session_id>', methods=['GET'])
@login_required
def api_get_session(session_id):
    """API endpoint to get a single study session by ID"""
    try:
        session_data = db_session.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == session['user_id']
        ).first()
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or access denied'
            }), 404
            
        response = {
            'success': True,
            'data': {
                'id': session_data.id,
                'subject': session_data.subject,
                'date': session_data.date.isoformat(),
                'start_time': session_data.start_time.isoformat() if session_data.start_time else None,
                'duration_minutes': session_data.duration_minutes,
                'mood_level': session_data.mood_level,
                'mood_text': {
                    1: 'Very Stressed',
                    2: 'Stressed',
                    3: 'Neutral',
                    4: 'Relaxed',
                    5: 'Very Relaxed'
                }.get(session_data.mood_level, 'Unknown'),
                'notes': session_data.notes,
                'tags': session_data.tags.split(',') if session_data.tags else [],
                'completed': session_data.completed,
                'created_at': session_data.created_at.isoformat() if session_data.created_at else None,
                'updated_at': session_data.updated_at.isoformat() if session_data.updated_at else None
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/sessions', methods=['POST'])
@login_required
def api_create_session():
    """API endpoint to create a new study session"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['subject', 'date', 'duration_minutes']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Create new session
        new_session = StudySession(
            user_id=session['user_id'],
            subject=data['subject'],
            date=datetime.datetime.strptime(data['date'], '%Y-%m-%d').date(),
            start_time=datetime.datetime.strptime(data.get('start_time', '00:00'), '%H:%M').time() if 'start_time' in data else None,
            duration_minutes=data['duration_minutes'],
            mood_level=data.get('mood_level', 3),  # Default to neutral
            notes=data.get('notes', ''),
            tags=','.join(data.get('tags', [])),
            completed=data.get('completed', False),
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )
        
        db_session.add(new_session)
        db_session.commit()
        
        response = {
            'success': True,
            'message': 'Session created successfully',
            'id': new_session.id
        }
        
        return jsonify(response), 201
        
    except Exception as e:
        db_session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/sessions/<int:session_id>', methods=['PUT'])
@login_required
def api_update_session(session_id):
    """API endpoint to update an existing study session"""
    try:
        session_data = db_session.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == session['user_id']
        ).first()
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or access denied'
            }), 404
            
        data = request.get_json()
        
        # Update fields if provided
        if 'subject' in data:
            session_data.subject = data['subject']
        if 'date' in data:
            session_data.date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'start_time' in data:
            session_data.start_time = datetime.datetime.strptime(data['start_time'], '%H:%M').time()
        if 'duration_minutes' in data:
            session_data.duration_minutes = data['duration_minutes']
        if 'mood_level' in data:
            session_data.mood_level = data['mood_level']
        if 'notes' in data:
            session_data.notes = data['notes']
        if 'tags' in data:
            session_data.tags = ','.join(data['tags']) if isinstance(data['tags'], list) else data['tags']
        if 'completed' in data:
            session_data.completed = data['completed']
            
        session_data.updated_at = datetime.datetime.now()
        
        db_session.commit()
        
        response = {
            'success': True,
            'message': 'Session updated successfully'
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        db_session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def api_delete_session(session_id):
    """API endpoint to delete a study session"""
    try:
        session_data = db_session.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.user_id == session['user_id']
        ).first()
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or access denied'
            }), 404
            
        db_session.delete(session_data)
        db_session.commit()
        
        response = {
            'success': True,
            'message': 'Session deleted successfully'
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        db_session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/sessions/stats', methods=['GET'])
@login_required
def api_get_session_stats():
    """API endpoint to get statistics about study sessions"""
    try:
        # Base query for current user's sessions
        query = db_session.query(StudySession).filter(
            StudySession.user_id == session['user_id']
        )
        
        # Apply date filter if provided
        if 'date_from' in request.args:
            query = query.filter(StudySession.date >= datetime.datetime.strptime(
                request.args['date_from'], '%Y-%m-%d'
            ).date())
            
        if 'date_to' in request.args:
            query = query.filter(StudySession.date <= datetime.datetime.strptime(
                request.args['date_to'], '%Y-%m-%d'
            ).date())
        
        # Get total sessions and time
        total_sessions = query.count()
        total_minutes = query.with_entities(
            db_session.func.sum(StudySession.duration_minutes)
        ).scalar() or 0
        
        # Calculate average mood
        avg_mood = query.with_entities(
            db_session.func.avg(StudySession.mood_level)
        ).scalar()
        
        # Get sessions by day of week
        sessions_by_day = db_session.query(
            db_session.func.dayofweek(StudySession.date).label('day_of_week'),
            db_session.func.count(StudySession.id).label('count')
        ).filter(
            StudySession.user_id == session['user_id']
        ).group_by('day_of_week').all()
        
        # Format day of week data
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        sessions_by_day_formatted = [0] * 7
        for day in sessions_by_day:
            # SQLite uses 1-7 for Sunday-Saturday, convert to 0-6 Monday-Sunday
            idx = (day[0] - 2) % 7
            sessions_by_day_formatted[idx] = day[1]
        
        response = {
            'success': True,
            'data': {
                'total_sessions': total_sessions,
                'total_hours': total_minutes // 60,
                'total_minutes': total_minutes % 60,
                'average_mood': float(avg_mood) if avg_mood else None,
                'sessions_by_day': {
                    'labels': days,
                    'data': sessions_by_day_formatted
                },
                'sessions_by_subject': [
                    {'subject': s[0], 'count': s[1]}
                    for s in query.with_entities(
                        StudySession.subject,
                        db_session.func.count(StudySession.id)
                    ).group_by(StudySession.subject).all()
                ]
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    with app.app_context():
        Base.metadata.create_all(engine)
    app.run(debug=True)