# 🍽️ FoodLink - Food Waste Donation System

A web-based platform connecting surplus food donors (restaurants, hotels, households) with receivers (NGOs, shelters, volunteer organizations) to reduce food waste.

**Course:** CSE 3204 - Software Engineering Lab, Department of CSE, RMSTU

## Features

- Role-based authentication (Donor / Receiver / Admin)
- Donors can post, edit, and delete food donations with images
- Receivers can browse, search, filter, and request donations
- Full request workflow: Posted → Requested → Accepted → Completed
- Admin statistics dashboard
- Responsive UI with dark mode support

## Tech Stack

- **Backend:** Python, Django
- **Frontend:** HTML, CSS, Bootstrap 5, JavaScript
- **Database:** SQLite
- **Version Control:** Git, GitHub

## Setup Instructions

```bash
# Clone the repository
git clone https://github.com/tawheedul-islam/FoodLink-Food-Waste-Donation-System
cd foodlink

# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows

# Install dependencies
pip install django djangorestframework pillow

# Run migrations
python manage.py migrate

# Create superuser (admin)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.


## Project Structure

```text
foodlink/
├── accounts/       # User authentication & profiles
├── donations/      # Food donation management
├── requests_app/   # Donation request workflow
├── templates/      # HTML templates
├── static/         # CSS/JS files
└── media/          # Uploaded donation images