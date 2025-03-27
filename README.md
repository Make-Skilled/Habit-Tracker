# Habit Tracker - Gamified Habit Building Platform

A modern, gamified habit tracking application built with Flask that helps users build and maintain good habits while breaking bad ones. The platform features a points system, achievements, streaks, and a beautiful user interface.

## 🌟 Features

### Core Features
- **Habit Tracking**: Track both good and bad habits with customizable points
- **Categories**: Organize habits into different categories (Health, Productivity, Learning, etc.)
- **Streak System**: Build momentum with daily streaks and multipliers
- **Points System**: Earn points for good habits, lose points for bad habits
- **Achievements**: Unlock various achievements as you progress
- **Progress Tracking**: Visual progress bars and statistics
- **Leaderboard**: Compete with other users
- **Admin Dashboard**: Manage habits, categories, and users

### Gamification Elements
- **Level System**: Level up as you earn more points
- **Streak Multipliers**: Earn bonus points for maintaining streaks
- **Achievement System**: 20+ unique achievements to unlock
- **Visual Feedback**: Confetti animations and sound effects
- **Progress Visualization**: Beautiful progress bars and statistics

### User Experience
- **Responsive Design**: Works on all devices
- **Category Filtering**: Filter habits by category
- **Search Functionality**: Find habits easily
- **Beautiful UI**: Modern, clean interface with animations
- **Real-time Updates**: Instant feedback on actions

## 🛠️ Technology Stack

- **Backend**: Python/Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML, CSS, Tailwind CSS
- **Authentication**: Flask-Login
- **Security**: CSRF Protection, Security Headers
- **Animations**: Party.js for confetti effects

## 🚀 Getting Started

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/habit-gamified-tech.git
cd habit-gamified-tech
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python app.py
```

5. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

### Default Admin Account
- Email: admin@example.com
- Password: admin123

## 📱 Features in Detail

### Habit Management
- Create and track multiple habits
- Categorize habits for better organization
- Set points for good and bad habits
- Track completion status and streaks

### Achievement System
- 20+ unique achievements to unlock
- Progress tracking for each achievement
- Visual feedback when achievements are unlocked
- Points rewards for achievements

### Gamification Elements
- Level system based on total points
- Streak multipliers for consistent completion
- Daily and weekly challenges
- Leaderboard for competitive motivation

### Admin Features
- Manage habits and categories
- View user statistics
- Monitor system activity
- Customize achievement requirements

## 🔒 Security Features

- CSRF protection
- Secure password hashing
- Content Security Policy headers
- Admin-only routes protection
- Input validation and sanitization

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Flask framework and its extensions
- Tailwind CSS for styling
- Party.js for animations
- All contributors and users of the application

## 📞 Support

For support, please open an issue in the GitHub repository or contact the maintainers.

---

Made with ❤️ by [Your Name/Organization] 