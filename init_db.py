from app import app, mysql
from models import Base, User, StudySession, WellnessEntry, StudyGoal, WellnessTip, UserPreference, MoodLevel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def init_db():
    # Get database configuration from Flask app
    db_uri = f"mysql+pymysql://{app.config['MYSQL_USER']}:{app.config['MYSQL_PASSWORD']}@{app.config['MYSQL_HOST']}/{app.config['MYSQL_DB']}"
    
    # Create SQLAlchemy engine
    engine = create_engine(db_uri)
    
    # Create all tables
    print("Dropping existing tables...")
    Base.metadata.drop_all(engine)
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("Database tables created successfully!")
    
    # Create a configured "Session" class
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Add sample wellness tips
        wellness_tips = [
            WellnessTip(
                title="5-Minute Breathing Exercise",
                content="Take 5 minutes to focus on your breath. Inhale for 4 seconds, hold for 4 seconds, exhale for 6 seconds. Repeat.",
                category="stress",
                min_stress_level=5,
                max_stress_level=10
            ),
            WellnessTip(
                title="Pomodoro Technique",
                content="Try the Pomodoro technique: 25 minutes of focused work, then a 5-minute break. After 4 cycles, take a longer break.",
                category="focus",
                min_stress_level=1,
                max_stress_level=10
            ),
            WellnessTip(
                title="Evening Wind-Down Routine",
                content="Create a relaxing evening routine to improve sleep quality. Avoid screens 1 hour before bed and try light stretching or reading.",
                category="sleep",
                min_stress_level=1,
                max_stress_level=10
            ),
            WellnessTip(
                title="Gratitude Journaling",
                content="Write down 3 things you're grateful for today. This simple practice can improve your overall well-being and perspective.",
                category="motivation",
                min_stress_level=1,
                max_stress_level=10
            )
        ]
        
        session.add_all(wellness_tips)
        
        # Add a test user
        test_user = User(
            username="testuser",
            email="test@example.com",
            password_hash=generate_password_hash("test123"),
            full_name="Test User",
            is_premium=False
        )
        session.add(test_user)
        session.flush()  # To get the user ID
        
        # Add user preferences for test user
        preferences = UserPreference(
            user_id=test_user.id,
            study_reminder_enabled=True,
            break_reminder_interval=50,
            preferred_study_hours={
                'monday': [9, 17],
                'tuesday': [9, 17],
                'wednesday': [9, 17],
                'thursday': [9, 17],
                'friday': [9, 17],
                'saturday': [10, 15],
                'sunday': [10, 15]
            },
            theme='light'
        )
        session.add(preferences)
        
        # Add sample study sessions
        now = datetime.utcnow()
        study_sessions = [
            StudySession(
                user_id=test_user.id,
                subject="Mathematics",
                duration=45,
                pre_mood=MoodLevel.STRESSED,
                post_mood=MoodLevel.NEUTRAL,
                notes="Focused on calculus problems. It was challenging but made progress.",
                sentiment_score=0.2,
                created_at=now - timedelta(days=1)
            ),
            StudySession(
                user_id=test_user.id,
                subject="History",
                duration=30,
                pre_mood=MoodLevel.NEUTRAL,
                post_mood=MoodLevel.RELAXED,
                notes="Read about World War II. Found it very interesting!",
                sentiment_score=0.7,
                created_at=now - timedelta(days=2)
            )
        ]
        session.add_all(study_sessions)
        
        # Add sample wellness entries
        wellness_entries = [
            WellnessEntry(
                user_id=test_user.id,
                mood_level=MoodLevel.STRESSED,
                stress_level=7,
                energy_level=5,
                sleep_hours=6.5,
                notes="Had a busy day with lots of assignments due.",
                sentiment_analysis={"label": "NEGATIVE", "score": 0.85},
                created_at=now - timedelta(days=1)
            ),
            WellnessEntry(
                user_id=test_user.id,
                mood_level=MoodLevel.RELAXED,
                stress_level=3,
                energy_level=8,
                sleep_hours=8.0,
                notes="Good day today, felt productive and happy.",
                sentiment_analysis={"label": "POSITIVE", "score": 0.92},
                created_at=now - timedelta(days=2)
            )
        ]
        session.add_all(wellness_entries)
        
        # Add sample study goals
        study_goals = [
            StudyGoal(
                user_id=test_user.id,
                title="Complete Math Assignment",
                description="Finish all problems in chapter 5",
                target_hours=8.0,
                current_hours=3.5,
                deadline=now + timedelta(days=7),
                is_completed=False
            ),
            StudyGoal(
                user_id=test_user.id,
                title="Prepare for History Exam",
                description="Review all chapters and make summary notes",
                target_hours=10.0,
                current_hours=10.0,
                deadline=now - timedelta(days=2),
                is_completed=True
            )
        ]
        session.add_all(study_goals)
        
        # Commit all changes
        session.commit()
        print("Sample data added successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Error initializing database: {e}")
    finally:
        session.close()
        # Close any existing database connections
        if 'mysql' in app.extensions:
            app.mysql.connection.close()

if __name__ == '__main__':
    with app.app_context():
        init_db()
