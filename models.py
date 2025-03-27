from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import and_

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_habits = db.relationship('UserHabit', backref='user', lazy=True)

    @property
    def level(self):
        """Calculate user's level based on points (100 points per level)"""
        return (self.points // 100) + 1

    @property
    def level_progress(self):
        """Calculate progress towards next level (0-100)"""
        return self.points % 100

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def check_achievements(self):
        """Check and award achievements based on user's progress"""
        achievements = Achievement.query.all()
        for achievement in achievements:
            # Check if achievement is already unlocked
            if not UserAchievement.query.filter_by(user_id=self.id, achievement_id=achievement.id).first():
                if self._meets_achievement_requirement(achievement):
                    user_achievement = UserAchievement(self.id, achievement.id)
                    db.session.add(user_achievement)
                    self.points += achievement.points
                    db.session.commit()
                    return achievement
        return None

    def _meets_achievement_requirement(self, achievement):
        """Check if user meets the achievement requirement"""
        req_type, req_value = achievement.requirement.split(':')
        req_value = int(req_value)
        
        if req_type == 'complete_habits':
            # Count unique habits completed
            completed_habits = set(uh.habit_id for uh in self.user_habits if uh.last_completed)
            return len(completed_habits) >= req_value
        elif req_type == 'streak':
            return any(uh.current_streak >= req_value for uh in self.user_habits)
        elif req_type == 'points':
            return self.points >= req_value
        elif req_type == 'daily_completion':
            today = datetime.utcnow().date()
            completed_today = sum(1 for uh in self.user_habits 
                                if uh.last_completed and uh.last_completed.date() == today)
            return completed_today >= req_value
        return False

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#4F46E5')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    habits = db.relationship('Habit', backref='category', lazy=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_good = db.Column(db.Boolean, default=True)
    points = db.Column(db.Integer, default=10)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_habits = db.relationship('UserHabit', backref='habit', lazy=True)

    @property
    def completion_count(self):
        """Calculate the total number of completions for this habit across all users."""
        return HabitCompletion.query.join(
            UserHabit,
            and_(
                UserHabit.user_id == HabitCompletion.user_habit_user_id,
                UserHabit.habit_id == HabitCompletion.user_habit_habit_id
            )
        ).filter(UserHabit.habit_id == self.id).count()

class HabitCompletion(db.Model):
    __tablename__ = 'habit_completion'
    
    user_habit_user_id = db.Column(db.Integer, db.ForeignKey('user_habit.user_id'), primary_key=True)
    user_habit_habit_id = db.Column(db.Integer, db.ForeignKey('user_habit.habit_id'), primary_key=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_habit = db.relationship('UserHabit', 
                                primaryjoin="and_(HabitCompletion.user_habit_user_id==UserHabit.user_id, "
                                          "HabitCompletion.user_habit_habit_id==UserHabit.habit_id)")

class UserHabit(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), primary_key=True)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_completed = db.Column(db.DateTime)
    milestone_7_reached = db.Column(db.Boolean, default=False)
    milestone_30_reached = db.Column(db.Boolean, default=False)
    milestone_100_reached = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completions = db.relationship('HabitCompletion', 
                                lazy=True,
                                primaryjoin="and_(UserHabit.user_id==HabitCompletion.user_habit_user_id, "
                                          "UserHabit.habit_id==HabitCompletion.user_habit_habit_id)")

# Association table for many-to-many relationship between users and habits
user_habits = db.Table('user_habits',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('habit_id', db.Integer, db.ForeignKey('habit.id'), primary_key=True)
)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(50), nullable=False)  # emoji or icon name
    points = db.Column(db.Integer, default=0)  # bonus points for unlocking
    requirement = db.Column(db.String(100), nullable=False)  # e.g., "complete_habits:10"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('achievements', lazy=True))
    achievement = db.relationship('Achievement')

    def __init__(self, user_id, achievement_id):
        self.user_id = user_id
        self.achievement_id = achievement_id
        self.unlocked_at = datetime.utcnow() 