from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, Float, Boolean, Enum, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from flask_login import UserMixin
import enum

Base = declarative_base()

class MoodLevel(enum.Enum):
    VERY_STRESSED = "Very Stressed"
    STRESSED = "Stressed"
    NEUTRAL = "Neutral"
    RELAXED = "Relaxed"
    VERY_RELAXED = "Very Relaxed"

class User(Base, UserMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_premium = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP)
    
    # Relationships
    study_sessions = relationship('StudySession', back_populates='user', cascade='all, delete-orphan')
    wellness_entries = relationship('WellnessEntry', back_populates='user', cascade='all, delete-orphan')
    study_goals = relationship('StudyGoal', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

class StudySession(Base):
    __tablename__ = 'study_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject = Column(String(100), nullable=False)
    duration = Column(Integer, nullable=False)  # in minutes
    pre_mood = Column(Enum(MoodLevel), nullable=True)
    post_mood = Column(Enum(MoodLevel), nullable=True)
    notes = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1 to 1, negative to positive
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationship
    user = relationship('User', back_populates='study_sessions')
    
    def __repr__(self):
        return f"<StudySession(id={self.id}, user_id={self.user_id}, subject='{self.subject}')>"

class WellnessEntry(Base):
    __tablename__ = 'wellness_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    mood_level = Column(Enum(MoodLevel), nullable=False)
    stress_level = Column(Integer, nullable=False)  # 1-10 scale
    energy_level = Column(Integer, nullable=False)  # 1-10 scale
    sleep_hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    sentiment_analysis = Column(JSON, nullable=True)  # Store full sentiment analysis results
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationship
    user = relationship('User', back_populates='wellness_entries')
    
    def __repr__(self):
        return f"<WellnessEntry(id={self.id}, user_id={self.user_id}, mood='{self.mood_level}')>"

class StudyGoal(Base):
    __tablename__ = 'study_goals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_hours = Column(Float, nullable=False)
    current_hours = Column(Float, default=0.0)
    deadline = Column(TIMESTAMP, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationship
    user = relationship('User', back_populates='study_goals')
    
    def __repr__(self):
        return f"<StudyGoal(id={self.id}, title='{self.title}', progress='{self.current_hours}/{self.target_hours}')>"

class WellnessTip(Base):
    __tablename__ = 'wellness_tips'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # e.g., 'stress', 'focus', 'sleep', 'motivation'
    min_stress_level = Column(Integer, default=0)  # 1-10 scale
    max_stress_level = Column(Integer, default=10)  # 1-10 scale
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __repr__(self):
        return f"<WellnessTip(id={self.id}, title='{self.title}')>"

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    study_reminder_enabled = Column(Boolean, default=True)
    break_reminder_interval = Column(Integer, default=50)  # minutes
    preferred_study_hours = Column(JSON)  # e.g., {'monday': [9, 17], 'tuesday': [9, 17], ...}
    theme = Column(String(20), default='light')
    
    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id})>"