# Mindfit
# 🌱 MindFit Learn

MindFit Learn is a **mental health + learning companion** web application.  
It helps users track moods, analyze wellbeing with AI, and improve study habits — all in one platform.  

Built with **Flask, MySQL, Hugging Face NLP, and IntaSend Payments**, MindFit Learn bridges the gap between **health and education**, empowering this generation with tools for self-growth.  

---

## 🚀 Features

- 🧠 **Mood Tracking** – Log your daily emotions & habits  
- 🤖 **AI Sentiment Analysis** – Hugging Face NLP model for mood insights  
- 📊 **Dashboard & Charts** – Visualize your progress over time  
- 🎓 **Learning Companion** – Track productivity & study routines  
- 💳 **Premium Upgrade** – IntaSend-powered payments (KES, USD) for advanced insights  
- 🔐 **User Authentication** – Secure login & sessions  

---

## 🛠️ Tech Stack

- **Backend:** Flask 3, SQLAlchemy, PyMySQL  
- **Frontend:** Jinja2, HTML5, CSS3 (Hospital-theme UI/UX)  
- **AI Model:** Hugging Face (twitter-roberta-base-sentiment-latest)  
- **Database:** MySQL  
- **Payments:** IntaSend API  
- **Environment:** Python 3.11+, Virtualenv  

---

## 📂 Project Structure


mindfit/
│── app.py # Flask app entry point
│── models.py # Database models
│── routes.py # App routes
│── requirements.txt # Dependencies
│── .env # Environment variables
│── static/ # CSS, JS, images
│── templates/ # HTML templates


---

## ⚙️ Installation

1. Clone repo:
   ```bash
   git clone https://github.com/yourusername/mindfit.git
   cd mindfit


Create virtual environment:

python -m venv .venv
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows


Install requirements:

pip install -r requirements.txt


Create .env file:

FLASK_SECRET=change-me-please
DATABASE_URL=mysql+pymysql://mindfit_user:supersecret@localhost:3306/mindfit
HF_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest
HF_API_KEY=hf_xxxxxxxxx
INTASEND_PUBLISHABLE_KEY=pk_test_xxxxx
INTASEND_SECRET_KEY=sk_test_xxxxx
INTASEND_TEST=true
PREMIUM_PRICE=5.00
PREMIUM_CURRENCY=KES


Run the app:

flask run
