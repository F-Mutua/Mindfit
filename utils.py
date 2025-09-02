# utils.py
import os
import json
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import MoodLevel, WellnessTip, StudySession, WellnessEntry

# Sentiment analysis setup
try:
    from transformers import pipeline
    sentiment_analyzer = pipeline("sentiment-analysis")
except ImportError:
    sentiment_analyzer = None

def analyze_sentiment(text: str) -> Dict[str, float]:
    """
    Analyze the sentiment of a given text using Hugging Face's sentiment analysis.
    Returns a dictionary with 'label' (POSITIVE/NEGATIVE) and 'score' (confidence).
    """
    if not text or not sentiment_analyzer:
        return {"label": "NEUTRAL", "score": 0.5}
    
    try:
        result = sentiment_analyzer(text)[0]
        return {
            "label": result["label"],
            "score": result["score"] if result["label"] == "POSITIVE" else 1 - result["score"]
        }
    except Exception as e:
        print(f"Error in sentiment analysis: {e}")
        return {"label": "NEUTRAL", "score": 0.5}

def get_wellness_tips(stress_level: int, category: str = None) -> List[Dict]:
    """
    Get wellness tips based on stress level and optional category.
    """
    tips = []
    with Session(engine) as session:
        query = session.query(WellnessTip).filter(
            WellnessTip.min_stress_level <= stress_level,
            WellnessTip.max_stress_level >= stress_level
        )
        
        if category:
            query = query.filter(WellnessTip.category == category.lower())
        
        tips = [{
            "id": tip.id,
            "title": tip.title,
            "content": tip.content,
            "category": tip.category
        } for tip in query.all()]
    
    # If no tips found for the specific category, try without category filter
    if not tips and category:
        return get_wellness_tips(stress_level)
        
    return tips

def generate_study_recommendations(user_id: int, session: Session) -> List[Dict]:
    """
    Generate personalized study recommendations based on user's study patterns and mood.
    """
    recommendations = []
    
    # Get user's recent study sessions
    recent_sessions = session.query(StudySession).filter(
        StudySession.user_id == user_id
    ).order_by(StudySession.created_at.desc()).limit(5).all()
    
    # Get user's recent wellness entries
    recent_wellness = session.query(WellnessEntry).filter(
        WellnessEntry.user_id == user_id
    ).order_by(WellnessEntry.created_at.desc()).limit(5).all()
    
    # Analyze study patterns
    if recent_sessions:
        avg_duration = sum(s.duration for s in recent_sessions) / len(recent_sessions)
        
        if avg_duration > 60:
            recommendations.append({
                "type": "break",
                "title": "Take Regular Breaks",
                "message": "Your study sessions are quite long. Consider taking a 5-10 minute break every 50 minutes to maintain focus.",
                "priority": "high"
            })
    
    # Analyze mood patterns
    if recent_wellness:
        avg_stress = sum(w.stress_level for w in recent_wellness) / len(recent_wellness)
        
        if avg_stress > 7:
            recommendations.append({
                "type": "wellness",
                "title": "High Stress Detected",
                "message": "Your stress levels have been high. Try some relaxation techniques or take a short break.",
                "priority": "high"
            })
    
    # Add general study tips if no specific recommendations
    if not recommendations:
        general_tips = [
            {
                "type": "study",
                "title": "Use Active Recall",
                "message": "Try testing yourself on the material instead of just re-reading it. This improves retention.",
                "priority": "medium"
            },
            {
                "type": "study",
                "title": "Space Out Your Study Sessions",
                "message": "Studying a little bit each day is more effective than cramming. Try the spacing effect!",
                "priority": "medium"
            }
        ]
        recommendations.extend(general_tips)
    
    return recommendations

def calculate_productivity_score(user_id: int, session: Session) -> float:
    """
    Calculate a productivity score (0-100) based on study time, consistency, and mood.
    """
    # Get data from the last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    # Calculate study time score (max 50 points)
    study_time = session.query(
        func.sum(StudySession.duration).label('total_duration')
    ).filter(
        StudySession.user_id == user_id,
        StudySession.created_at >= week_ago
    ).scalar() or 0
    
    # Convert minutes to hours and cap at 20 hours per week (2.85 hours/day)
    study_hours = min(study_time / 60, 20)
    study_score = (study_hours / 20) * 50  # 50 points max
    
    # Calculate consistency score (max 30 points)
    study_days = session.query(
        func.count(func.distinct(func.date(StudySession.created_at)))
    ).filter(
        StudySession.user_id == user_id,
        StudySession.created_at >= week_ago
    ).scalar() or 0
    
    consistency_score = (study_days / 7) * 30  # 30 points max
    
    # Calculate mood score (max 20 points)
    avg_mood = session.query(
        func.avg(WellnessEntry.stress_level)
    ).filter(
        WellnessEntry.user_id == user_id,
        WellnessEntry.created_at >= week_ago
    ).scalar() or 5  # Default to neutral if no data
    
    # Convert stress (1-10) to score (1 = least stressed = better)
    mood_score = (1 - (avg_mood - 1) / 9) * 20  # 20 points max
    
    # Calculate total score (0-100)
    total_score = study_score + consistency_score + mood_score
    
    return min(100, max(0, round(total_score, 2)))

def get_study_analytics(user_id: int, days: int = 7) -> Dict:
    """
    Get analytics data for the user's study sessions over the specified number of days.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days-1)
    
    with Session(engine) as session:
        # Get daily study time
        daily_data = session.query(
            func.date(StudySession.created_at).label('date'),
            func.sum(StudySession.duration).label('total_duration'),
            func.avg(StudySession.sentiment_score).label('avg_sentiment')
        ).filter(
            StudySession.user_id == user_id,
            StudySession.created_at >= start_date,
            StudySession.created_at <= end_date
        ).group_by('date').order_by('date').all()
        
        # Get mood data
        mood_data = session.query(
            func.date(WellnessEntry.created_at).label('date'),
            func.avg(WellnessEntry.stress_level).label('avg_stress'),
            func.avg(WellnessEntry.energy_level).label('avg_energy')
        ).filter(
            WellnessEntry.user_id == user_id,
            WellnessEntry.created_at >= start_date,
            WellnessEntry.created_at <= end_date
        ).group_by('date').order_by('date').all()
        
        # Get subject distribution
        subjects = session.query(
            StudySession.subject,
            func.sum(StudySession.duration).label('total_duration')
        ).filter(
            StudySession.user_id == user_id,
            StudySession.created_at >= start_date,
            StudySession.created_at <= end_date
        ).group_by(StudySession.subject).order_by(func.sum(StudySession.duration).desc()).all()
        
        # Format data for charts
        dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
        study_data = {row.date.strftime('%Y-%m-%d'): row.total_duration / 60 for row in daily_data}  # Convert to hours
        mood_data_dict = {row.date.strftime('%Y-%m-%d'): row.avg_stress for row in mood_data}
        energy_data_dict = {row.date.strftime('%Y-%m-%d'): row.avg_energy for row in mood_data}
        
        # Fill in missing dates with zeros/None
        study_hours = [study_data.get(date, 0) for date in dates]
        stress_levels = [mood_data_dict.get(date, None) for date in dates]
        energy_levels = [energy_data_dict.get(date, None) for date in dates]
        
        # Calculate subject distribution
        subject_labels = [row.subject for row in subjects]
        subject_hours = [round(row.total_duration / 60, 1) for row in subjects]  # Convert to hours
        
        return {
            'dates': dates,
            'study_hours': study_hours,
            'stress_levels': stress_levels,
            'energy_levels': energy_levels,
            'subjects': {
                'labels': subject_labels,
                'data': subject_hours
            },
            'total_study_hours': round(sum(study_hours), 1),
            'avg_stress': round(sum(filter(None, stress_levels)) / len([s for s in stress_levels if s is not None]), 1) if any(stress_levels) else None,
            'avg_energy': round(sum(filter(None, energy_levels)) / len([e for e in energy_levels if e is not None]), 1) if any(energy_levels) else None
        }

# --- IntaSend helpers (SDK first, REST fallback)
USE_SDK = True
try:
    from intasend import APIService
except Exception:
    USE_SDK = False

def create_checkout(user_email: str, api_ref: str):
    """Create an IntaSend Checkout link and return a dict with url and invoice_id."""
    if USE_SDK:
        service = APIService(token=INTASEND_SECRET_KEY, publishable_key=INTASEND_PUBLISHABLE_KEY, test=INTASEND_TEST)
        resp = service.collect.checkout(email=user_email, amount=PREMIUM_PRICE, currency=PREMIUM_CURRENCY, comment="MindFit Premium", redirect_url=f"{REDIRECT_HOST}/payment/callback")
        return {"url": resp.get("url"), "invoice_id": resp.get("invoice", {}).get("invoice_id") or resp.get("invoice_id")}
    else:
        # REST fallback
        url = "https://api.intasend.com/api/v1/checkout/"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {INTASEND_SECRET_KEY}"} if INTASEND_SECRET_KEY else {"Content-Type": "application/json"}
        payload = {
            "email": user_email,
            "amount": PREMIUM_PRICE,
            "currency": PREMIUM_CURRENCY,
            "comment": "MindFit Premium",
            "redirect_url": f"{REDIRECT_HOST}/payment/callback"
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {"url": data.get("url"), "invoice_id": data.get("invoice", {}).get("invoice_id") or data.get("invoice_id")}

def check_payment_status(invoice_id: str):
    if USE_SDK:
        service = APIService(token=INTASEND_SECRET_KEY, publishable_key=INTASEND_PUBLISHABLE_KEY, test=INTASEND_TEST)
        resp = service.collect.status(invoice_id=invoice_id)
        return resp
    else:
        # If using REST, hit the status endpoint (requires auth)
        url = f"https://api.intasend.com/api/v1/checkout/{invoice_id}/"
        headers = {"Authorization": f"Bearer {INTASEND_SECRET_KEY}"}
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()