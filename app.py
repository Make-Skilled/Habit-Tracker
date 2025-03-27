from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import func, and_, or_
from models import db, User, Habit, HabitCompletion, UserHabit, Category, Achievement
import pytz
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set timezone to IST (GMT+5:30)
IST = pytz.timezone('Asia/Kolkata')

db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            email=email,
            is_admin=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid email or password.', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's habits
    user_habits = UserHabit.query.filter_by(user_id=current_user.id).all()
    
    # Get all categories for filtering
    categories = Category.query.all()
    
    # Get selected category from query parameters
    selected_category = request.args.get('category', type=int)
    
    # Filter habits by category if selected
    if selected_category:
        user_habits = [uh for uh in user_habits if uh.habit.category_id == selected_category]
    
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.utcnow().astimezone(ist)
    
    # Get all achievements with user's progress
    achievements = Achievement.query.all()
    user_achievements = {ua.achievement_id for ua in current_user.achievements}
    
    # Calculate progress for each achievement
    for achievement in achievements:
        achievement.unlocked = achievement.id in user_achievements
        if not achievement.unlocked:
            req_type, req_value = achievement.requirement.split(':')
            req_value = int(req_value)
            
            if req_type == 'complete_habits':
                current = len(current_user.user_habits)
            elif req_type == 'streak':
                current = max((uh.current_streak for uh in current_user.user_habits), default=0)
            elif req_type == 'points':
                current = current_user.points
            elif req_type == 'daily_completion':
                today = datetime.utcnow().date()
                current = sum(1 for uh in current_user.user_habits 
                            if uh.last_completed and uh.last_completed.date() == today)
            else:
                current = 0
            
            achievement.progress = min(100, (current / req_value) * 100)
    
    return render_template('dashboard.html',
                         user_habits=user_habits,
                         categories=categories,
                         selected_category=selected_category,
                         now=now,
                         achievements=achievements)

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.order_by(User.points.desc()).all()
    return render_template('leaderboard.html', users=users)

@app.route('/add_habit', methods=['GET', 'POST'])
@login_required
@admin_required
def add_habit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        is_good = request.form.get('is_good') == 'true'
        points = int(request.form.get('points', 0))

        if not name:
            flash('Habit name is required.', 'error')
            return redirect(url_for('add_habit'))

        habit = Habit(
            name=name,
            description=description,
            category_id=category_id if category_id else None,
            is_good=is_good,
            points=points
        )

        db.session.add(habit)
        db.session.commit()

        flash('Habit added successfully!', 'success')
        return redirect(url_for('admin_habits'))

    categories = Category.query.all()
    return render_template('admin/add_habit.html', categories=categories)

@app.route('/select_habits', methods=['GET', 'POST'])
@login_required
def select_habits():
    if request.method == 'POST':
        selected_habits = request.form.getlist('habits')
        for habit_id in selected_habits:
            habit_id = int(habit_id)
            # Check if user already has this habit
            if not UserHabit.query.filter_by(user_id=current_user.id, habit_id=habit_id).first():
                user_habit = UserHabit(user_id=current_user.id, habit_id=habit_id)
                db.session.add(user_habit)
        db.session.commit()
        flash('Habits selected successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    # Get search query
    search_query = request.args.get('search', '').strip()
    
    # Get all habits that the user hasn't selected yet
    selected_habit_ids = [uh.habit_id for uh in current_user.user_habits]
    query = Habit.query.filter(~Habit.id.in_(selected_habit_ids))
    
    # Apply search filter if search query exists
    if search_query:
        query = query.filter(
            db.or_(
                Habit.name.ilike(f'%{search_query}%'),
                Habit.description.ilike(f'%{search_query}%')
            )
        )
    
    available_habits = query.all()
    return render_template('select_habits.html', habits=available_habits, search_query=search_query)

@app.route('/complete_habit/<int:habit_id>', methods=['POST'])
@login_required
def complete_habit(habit_id):
    user_habit = UserHabit.query.filter_by(user_id=current_user.id, habit_id=habit_id).first_or_404()
    
    # Update completion
    user_habit.last_completed = datetime.utcnow()
    
    # Create HabitCompletion record
    completion = HabitCompletion(
        user_habit_user_id=current_user.id,
        user_habit_habit_id=habit_id,
        completed_at=datetime.utcnow()
    )
    db.session.add(completion)
    
    # Calculate points with streak multiplier
    base_points = user_habit.habit.points
    streak_multiplier = min(math.floor(user_habit.current_streak / 7) + 1, 3)
    points_earned = base_points * streak_multiplier
    
    # Update streak and points
    user_habit.current_streak += 1
    if user_habit.current_streak > user_habit.longest_streak:
        user_habit.longest_streak = user_habit.current_streak
    
    current_user.points += points_earned
    
    # Check for achievements
    achievement = current_user.check_achievements()
    if achievement:
        flash(f'🏆 Achievement Unlocked: {achievement.name}! +{achievement.points} points', 'success')
    
    db.session.commit()
    
    return redirect(url_for('dashboard', success='true', points=points_earned))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get total users and habits
    total_users = User.query.count()
    total_habits = Habit.query.count()
    
    # Get total completions using a subquery
    completion_counts = db.session.query(
        Habit.id,
        db.func.count('*').label('completion_count')
    ).join(
        UserHabit,
        and_(
            UserHabit.user_id == HabitCompletion.user_habit_user_id,
            UserHabit.habit_id == HabitCompletion.user_habit_habit_id
        )
    ).join(
        HabitCompletion,
        and_(
            HabitCompletion.user_habit_user_id == UserHabit.user_id,
            HabitCompletion.user_habit_habit_id == UserHabit.habit_id
        )
    ).group_by(Habit.id).all()
    
    # Create a dictionary of habit completion counts
    habit_completion_counts = {habit_id: count for habit_id, count in completion_counts}
    
    # Get all habits
    habits = Habit.query.all()
    
    # Get total points earned
    total_points = db.session.query(db.func.sum(User.points)).scalar() or 0
    
    # Get recent activity
    recent_completions = HabitCompletion.query.order_by(HabitCompletion.completed_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_habits=total_habits,
                         total_points=total_points,
                         habits=habits,
                         habit_completion_counts=habit_completion_counts,
                         recent_completions=recent_completions)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/habits')
@login_required
@admin_required
def admin_habits():
    habits = Habit.query.all()
    return render_template('admin/habits.html', habits=habits)

@app.route('/admin/habits/<int:habit_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    categories = Category.query.all()  # Get all categories for the dropdown
    
    if request.method == 'POST':
        habit.name = request.form.get('name')
        habit.description = request.form.get('description')
        habit.is_good = request.form.get('is_good') == 'true'
        habit.points = int(request.form.get('points', 10))
        
        # Handle category assignment
        category_id = request.form.get('category')
        if category_id:
            habit.category_id = int(category_id)
        else:
            habit.category_id = None
        
        db.session.commit()
        flash('Habit updated successfully!', 'success')
        return redirect(url_for('admin_habits'))
    
    return render_template('admin/edit_habit.html', habit=habit, categories=categories)

@app.route('/admin/habits/<int:habit_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    db.session.delete(habit)
    db.session.commit()
    flash('Habit deleted successfully!', 'success')
    return redirect(url_for('admin_habits'))

def create_admin_user():
    admin = User.query.filter_by(email='admin@example.com').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

def create_default_habits():
    # Create default categories with expanded color scheme
    categories = {
        # Core Categories
        'Health & Fitness': '#4CAF50',    # Green
        'Productivity': '#2196F3',        # Blue
        'Learning': '#9C27B0',            # Purple
        'Lifestyle': '#FF9800',           # Orange
        'Finance': '#4CAF50',             # Green
        'Social': '#E91E63',              # Pink
        'Mental Health': '#00BCD4',       # Cyan
        'Career': '#3F51B5',              # Indigo
        'Personal Growth': '#FF5722',     # Deep Orange
        'Hobbies': '#795548',             # Brown
        
        # New Categories
        'Nutrition': '#FFC107',           # Amber
        'Sleep': '#673AB7',               # Deep Purple
        'Technology': '#03A9F4',          # Light Blue
        'Creativity': '#F44336',          # Red
        'Environment': '#009688',         # Teal
        'Spirituality': '#8BC34A',        # Light Green
        'Travel': '#FF5722',              # Deep Orange
        'Communication': '#E91E63',       # Pink
        'Time Management': '#3F51B5',     # Indigo
        'Wellness': '#00BCD4'             # Cyan
    }
    
    for name, color in categories.items():
        if not Category.query.filter_by(name=name).first():
            category = Category(name=name, color=color)
            db.session.add(category)
    
    db.session.commit()
    
    # Get category references
    categories_ref = {name: Category.query.filter_by(name=name).first() 
                     for name in categories.keys()}

    # Define habits with their categories
    habits = [
        # Health & Fitness (Expanded)
        {'name': 'Exercise', 'description': '30 minutes of physical activity', 'is_good': True, 'points': 20, 'category': categories_ref['Health & Fitness']},
        {'name': 'Meditation', 'description': '10 minutes of mindfulness meditation', 'is_good': True, 'points': 15, 'category': categories_ref['Health & Fitness']},
        {'name': 'Drink Water', 'description': 'Drink 8 glasses of water', 'is_good': True, 'points': 10, 'category': categories_ref['Health & Fitness']},
        {'name': 'Eat Junk Food', 'description': 'Consume unhealthy processed food', 'is_good': False, 'points': -15, 'category': categories_ref['Health & Fitness']},
        {'name': 'Skip Exercise', 'description': 'Miss planned workout session', 'is_good': False, 'points': -20, 'category': categories_ref['Health & Fitness']},
        {'name': 'Strength Training', 'description': '30 minutes of weight training', 'is_good': True, 'points': 25, 'category': categories_ref['Health & Fitness']},
        {'name': 'Cardio Workout', 'description': '20 minutes of cardio exercise', 'is_good': True, 'points': 20, 'category': categories_ref['Health & Fitness']},
        {'name': 'Stretching', 'description': '15 minutes of flexibility exercises', 'is_good': True, 'points': 10, 'category': categories_ref['Health & Fitness']},
        {'name': 'Skip Warm-up', 'description': 'Exercise without proper warm-up', 'is_good': False, 'points': -15, 'category': categories_ref['Health & Fitness']},
        {'name': 'Overexertion', 'description': 'Push beyond safe limits', 'is_good': False, 'points': -20, 'category': categories_ref['Health & Fitness']},
        
        # Nutrition (New Category)
        {'name': 'Eat Vegetables', 'description': 'Include vegetables in every meal', 'is_good': True, 'points': 15, 'category': categories_ref['Nutrition']},
        {'name': 'Meal Prep', 'description': 'Prepare healthy meals in advance', 'is_good': True, 'points': 20, 'category': categories_ref['Nutrition']},
        {'name': 'Track Calories', 'description': 'Track daily calorie intake', 'is_good': True, 'points': 10, 'category': categories_ref['Nutrition']},
        {'name': 'Eat Processed Food', 'description': 'Consume highly processed foods', 'is_good': False, 'points': -15, 'category': categories_ref['Nutrition']},
        {'name': 'Skip Meals', 'description': 'Skip regular meals', 'is_good': False, 'points': -10, 'category': categories_ref['Nutrition']},
        {'name': 'Eat Protein', 'description': 'Include protein in every meal', 'is_good': True, 'points': 10, 'category': categories_ref['Nutrition']},
        {'name': 'Limit Sugar', 'description': 'Stay under daily sugar limit', 'is_good': True, 'points': 15, 'category': categories_ref['Nutrition']},
        {'name': 'Eat Out', 'description': 'Eat at restaurants/fast food', 'is_good': False, 'points': -10, 'category': categories_ref['Nutrition']},
        {'name': 'Drink Soda', 'description': 'Consume sugary beverages', 'is_good': False, 'points': -10, 'category': categories_ref['Nutrition']},
        {'name': 'Eat Late', 'description': 'Eat close to bedtime', 'is_good': False, 'points': -10, 'category': categories_ref['Nutrition']},
        
        # Sleep (New Category)
        {'name': 'Sleep Early', 'description': 'Go to bed before 11 PM', 'is_good': True, 'points': 15, 'category': categories_ref['Sleep']},
        {'name': 'Sleep 8 Hours', 'description': 'Get 8 hours of sleep', 'is_good': True, 'points': 20, 'category': categories_ref['Sleep']},
        {'name': 'No Screens', 'description': 'Avoid screens 1 hour before bed', 'is_good': True, 'points': 10, 'category': categories_ref['Sleep']},
        {'name': 'Stay Up Late', 'description': 'Stay up past midnight', 'is_good': False, 'points': -15, 'category': categories_ref['Sleep']},
        {'name': 'Skip Sleep', 'description': 'Get less than 6 hours of sleep', 'is_good': False, 'points': -20, 'category': categories_ref['Sleep']},
        {'name': 'Regular Schedule', 'description': 'Maintain consistent sleep schedule', 'is_good': True, 'points': 15, 'category': categories_ref['Sleep']},
        {'name': 'Bedtime Routine', 'description': 'Follow bedtime routine', 'is_good': True, 'points': 10, 'category': categories_ref['Sleep']},
        {'name': 'Caffeine Late', 'description': 'Consume caffeine after 2 PM', 'is_good': False, 'points': -10, 'category': categories_ref['Sleep']},
        {'name': 'Nap Late', 'description': 'Take nap after 3 PM', 'is_good': False, 'points': -10, 'category': categories_ref['Sleep']},
        {'name': 'Irregular Sleep', 'description': 'Vary sleep schedule significantly', 'is_good': False, 'points': -15, 'category': categories_ref['Sleep']},
        
        # Technology (New Category)
        {'name': 'Digital Detox', 'description': '1 hour without electronic devices', 'is_good': True, 'points': 15, 'category': categories_ref['Technology']},
        {'name': 'Screen Breaks', 'description': 'Take regular screen breaks', 'is_good': True, 'points': 10, 'category': categories_ref['Technology']},
        {'name': 'Update Software', 'description': 'Keep software up to date', 'is_good': True, 'points': 5, 'category': categories_ref['Technology']},
        {'name': 'Excessive Screen Time', 'description': 'Spend too much time on screens', 'is_good': False, 'points': -15, 'category': categories_ref['Technology']},
        {'name': 'Social Media', 'description': 'Excessive social media use', 'is_good': False, 'points': -10, 'category': categories_ref['Technology']},
        {'name': 'Backup Data', 'description': 'Back up important data', 'is_good': True, 'points': 10, 'category': categories_ref['Technology']},
        {'name': 'Learn Tech', 'description': 'Learn new technology skill', 'is_good': True, 'points': 15, 'category': categories_ref['Technology']},
        {'name': 'Check Phone', 'description': 'Check phone first thing in morning', 'is_good': False, 'points': -5, 'category': categories_ref['Technology']},
        {'name': 'Tech Before Bed', 'description': 'Use technology before sleep', 'is_good': False, 'points': -10, 'category': categories_ref['Technology']},
        {'name': 'Ignore Updates', 'description': 'Ignore important updates', 'is_good': False, 'points': -5, 'category': categories_ref['Technology']},
        
        # Creativity (New Category)
        {'name': 'Write', 'description': 'Write creatively for 30 minutes', 'is_good': True, 'points': 15, 'category': categories_ref['Creativity']},
        {'name': 'Draw', 'description': 'Draw or sketch for 20 minutes', 'is_good': True, 'points': 15, 'category': categories_ref['Creativity']},
        {'name': 'Play Music', 'description': 'Practice musical instrument', 'is_good': True, 'points': 15, 'category': categories_ref['Creativity']},
        {'name': 'Avoid Creativity', 'description': 'Skip creative activities', 'is_good': False, 'points': -10, 'category': categories_ref['Creativity']},
        {'name': 'Creative Block', 'description': 'Let creative block persist', 'is_good': False, 'points': -15, 'category': categories_ref['Creativity']},
        {'name': 'Photography', 'description': 'Take creative photos', 'is_good': True, 'points': 10, 'category': categories_ref['Creativity']},
        {'name': 'Craft', 'description': 'Work on craft project', 'is_good': True, 'points': 15, 'category': categories_ref['Creativity']},
        {'name': 'Dance', 'description': 'Practice dancing', 'is_good': True, 'points': 15, 'category': categories_ref['Creativity']},
        {'name': 'Skip Practice', 'description': 'Skip creative practice', 'is_good': False, 'points': -10, 'category': categories_ref['Creativity']},
        {'name': 'Ignore Ideas', 'description': 'Ignore creative ideas', 'is_good': False, 'points': -5, 'category': categories_ref['Creativity']},
        
        # Environment (New Category)
        {'name': 'Recycle', 'description': 'Properly recycle items', 'is_good': True, 'points': 10, 'category': categories_ref['Environment']},
        {'name': 'Reduce Waste', 'description': 'Minimize waste production', 'is_good': True, 'points': 15, 'category': categories_ref['Environment']},
        {'name': 'Use Reusables', 'description': 'Use reusable items', 'is_good': True, 'points': 10, 'category': categories_ref['Environment']},
        {'name': 'Litter', 'description': 'Dispose of waste improperly', 'is_good': False, 'points': -15, 'category': categories_ref['Environment']},
        {'name': 'Waste Energy', 'description': 'Leave lights/appliances on', 'is_good': False, 'points': -10, 'category': categories_ref['Environment']},
        {'name': 'Compost', 'description': 'Compost organic waste', 'is_good': True, 'points': 15, 'category': categories_ref['Environment']},
        {'name': 'Walk/Bike', 'description': 'Use sustainable transport', 'is_good': True, 'points': 15, 'category': categories_ref['Environment']},
        {'name': 'Use Plastic', 'description': 'Use single-use plastics', 'is_good': False, 'points': -10, 'category': categories_ref['Environment']},
        {'name': 'Waste Water', 'description': 'Leave water running', 'is_good': False, 'points': -10, 'category': categories_ref['Environment']},
        {'name': 'Ignore Recycling', 'description': 'Ignore recycling guidelines', 'is_good': False, 'points': -10, 'category': categories_ref['Environment']},
        
        # Spirituality (New Category)
        {'name': 'Meditate', 'description': 'Daily meditation practice', 'is_good': True, 'points': 15, 'category': categories_ref['Spirituality']},
        {'name': 'Pray', 'description': 'Daily prayer or reflection', 'is_good': True, 'points': 10, 'category': categories_ref['Spirituality']},
        {'name': 'Read Scripture', 'description': 'Read spiritual texts', 'is_good': True, 'points': 10, 'category': categories_ref['Spirituality']},
        {'name': 'Skip Practice', 'description': 'Skip spiritual practice', 'is_good': False, 'points': -10, 'category': categories_ref['Spirituality']},
        {'name': 'Ignore Values', 'description': 'Act against personal values', 'is_good': False, 'points': -15, 'category': categories_ref['Spirituality']},
        {'name': 'Gratitude', 'description': 'Practice gratitude', 'is_good': True, 'points': 10, 'category': categories_ref['Spirituality']},
        {'name': 'Mindfulness', 'description': 'Practice mindfulness', 'is_good': True, 'points': 15, 'category': categories_ref['Spirituality']},
        {'name': 'Service', 'description': 'Perform service to others', 'is_good': True, 'points': 20, 'category': categories_ref['Spirituality']},
        {'name': 'Negative Thoughts', 'description': 'Engage in negative thinking', 'is_good': False, 'points': -10, 'category': categories_ref['Spirituality']},
        {'name': 'Skip Reflection', 'description': 'Skip daily reflection', 'is_good': False, 'points': -5, 'category': categories_ref['Spirituality']},
        
        # Travel (New Category)
        {'name': 'Plan Trip', 'description': 'Plan future travel', 'is_good': True, 'points': 15, 'category': categories_ref['Travel']},
        {'name': 'Learn Language', 'description': 'Learn travel destination language', 'is_good': True, 'points': 15, 'category': categories_ref['Travel']},
        {'name': 'Research Culture', 'description': 'Research destination culture', 'is_good': True, 'points': 10, 'category': categories_ref['Travel']},
        {'name': 'Ignore Safety', 'description': 'Ignore travel safety guidelines', 'is_good': False, 'points': -20, 'category': categories_ref['Travel']},
        {'name': 'Waste Money', 'description': 'Overspend on travel', 'is_good': False, 'points': -15, 'category': categories_ref['Travel']},
        {'name': 'Pack Early', 'description': 'Pack for trip in advance', 'is_good': True, 'points': 10, 'category': categories_ref['Travel']},
        {'name': 'Travel Insurance', 'description': 'Review travel insurance', 'is_good': True, 'points': 10, 'category': categories_ref['Travel']},
        {'name': 'Ignore Documents', 'description': 'Forget important documents', 'is_good': False, 'points': -15, 'category': categories_ref['Travel']},
        {'name': 'Jet Lag', 'description': 'Ignore jet lag recovery', 'is_good': False, 'points': -10, 'category': categories_ref['Travel']},
        {'name': 'Cultural Insensitivity', 'description': 'Be culturally insensitive', 'is_good': False, 'points': -15, 'category': categories_ref['Travel']},
        
        # Communication (New Category)
        {'name': 'Active Listening', 'description': 'Practice active listening', 'is_good': True, 'points': 15, 'category': categories_ref['Communication']},
        {'name': 'Express Feelings', 'description': 'Express feelings clearly', 'is_good': True, 'points': 10, 'category': categories_ref['Communication']},
        {'name': 'Give Feedback', 'description': 'Provide constructive feedback', 'is_good': True, 'points': 10, 'category': categories_ref['Communication']},
        {'name': 'Interrupt', 'description': 'Interrupt others while speaking', 'is_good': False, 'points': -10, 'category': categories_ref['Communication']},
        {'name': 'Avoid Conflict', 'description': 'Avoid important conversations', 'is_good': False, 'points': -15, 'category': categories_ref['Communication']},
        {'name': 'Public Speaking', 'description': 'Practice public speaking', 'is_good': True, 'points': 20, 'category': categories_ref['Communication']},
        {'name': 'Write Clearly', 'description': 'Write clear messages', 'is_good': True, 'points': 10, 'category': categories_ref['Communication']},
        {'name': 'Gossip', 'description': 'Engage in gossip', 'is_good': False, 'points': -10, 'category': categories_ref['Communication']},
        {'name': 'Ignore Messages', 'description': 'Ignore important messages', 'is_good': False, 'points': -10, 'category': categories_ref['Communication']},
        {'name': 'Poor Body Language', 'description': 'Use negative body language', 'is_good': False, 'points': -5, 'category': categories_ref['Communication']},
        
        # Time Management (New Category)
        {'name': 'Set Priorities', 'description': 'Set daily priorities', 'is_good': True, 'points': 15, 'category': categories_ref['Time Management']},
        {'name': 'Use Calendar', 'description': 'Use calendar effectively', 'is_good': True, 'points': 10, 'category': categories_ref['Time Management']},
        {'name': 'Time Blocking', 'description': 'Practice time blocking', 'is_good': True, 'points': 15, 'category': categories_ref['Time Management']},
        {'name': 'Procrastinate', 'description': 'Procrastinate important tasks', 'is_good': False, 'points': -15, 'category': categories_ref['Time Management']},
        {'name': 'Overcommit', 'description': 'Overcommit to activities', 'is_good': False, 'points': -10, 'category': categories_ref['Time Management']},
        {'name': 'Review Schedule', 'description': 'Review and adjust schedule', 'is_good': True, 'points': 10, 'category': categories_ref['Time Management']},
        {'name': 'Set Boundaries', 'description': 'Set time boundaries', 'is_good': True, 'points': 15, 'category': categories_ref['Time Management']},
        {'name': 'Ignore Deadlines', 'description': 'Ignore project deadlines', 'is_good': False, 'points': -20, 'category': categories_ref['Time Management']},
        {'name': 'Multitask', 'description': 'Attempt too much multitasking', 'is_good': False, 'points': -10, 'category': categories_ref['Time Management']},
        {'name': 'Waste Time', 'description': 'Waste time on unimportant tasks', 'is_good': False, 'points': -10, 'category': categories_ref['Time Management']},
        
        # Wellness (New Category)
        {'name': 'Self Care', 'description': 'Practice self-care activities', 'is_good': True, 'points': 15, 'category': categories_ref['Wellness']},
        {'name': 'Stress Management', 'description': 'Practice stress management', 'is_good': True, 'points': 15, 'category': categories_ref['Wellness']},
        {'name': 'Check Health', 'description': 'Monitor health metrics', 'is_good': True, 'points': 10, 'category': categories_ref['Wellness']},
        {'name': 'Ignore Health', 'description': 'Ignore health concerns', 'is_good': False, 'points': -20, 'category': categories_ref['Wellness']},
        {'name': 'Poor Posture', 'description': 'Maintain poor posture', 'is_good': False, 'points': -10, 'category': categories_ref['Wellness']},
        {'name': 'Regular Check-up', 'description': 'Schedule health check-up', 'is_good': True, 'points': 15, 'category': categories_ref['Wellness']},
        {'name': 'Mental Health', 'description': 'Practice mental health care', 'is_good': True, 'points': 15, 'category': categories_ref['Wellness']},
        {'name': 'Skip Vitamins', 'description': 'Skip daily vitamins', 'is_good': False, 'points': -5, 'category': categories_ref['Wellness']},
        {'name': 'Ignore Symptoms', 'description': 'Ignore health symptoms', 'is_good': False, 'points': -15, 'category': categories_ref['Wellness']},
        {'name': 'Poor Hygiene', 'description': 'Skip hygiene routines', 'is_good': False, 'points': -10, 'category': categories_ref['Wellness']}
    ]

    for habit_data in habits:
        if not Habit.query.filter_by(name=habit_data['name']).first():
            habit = Habit(
                name=habit_data['name'],
                description=habit_data['description'],
                is_good=habit_data['is_good'],
                points=habit_data['points'],
                category=habit_data['category']
            )
            db.session.add(habit)
    
    db.session.commit()

def create_default_achievements():
    achievements = [
        {
            'name': 'Getting Started',
            'description': 'Complete your first habit',
            'icon': '🎯',
            'points': 50,
            'requirement': 'complete_habits:1'
        },
        {
            'name': 'Habit Master',
            'description': 'Complete 10 habits',
            'icon': '🌟',
            'points': 200,
            'requirement': 'complete_habits:10'
        },
        {
            'name': 'Streak Champion',
            'description': 'Maintain a 7-day streak',
            'icon': '🔥',
            'points': 150,
            'requirement': 'streak:7'
        },
        {
            'name': 'Daily Warrior',
            'description': 'Complete all habits in a day',
            'icon': '⚔️',
            'points': 100,
            'requirement': 'daily_completion:5'
        },
        {
            'name': 'Point Collector',
            'description': 'Earn 1000 points',
            'icon': '💎',
            'points': 300,
            'requirement': 'points:1000'
        },
        {
            'name': 'Consistency King',
            'description': 'Maintain a 30-day streak',
            'icon': '👑',
            'points': 500,
            'requirement': 'streak:30'
        },
        {
            'name': 'Habit Explorer',
            'description': 'Try 5 different habits',
            'icon': '🌍',
            'points': 250,
            'requirement': 'complete_habits:5'
        },
        {
            'name': 'Early Bird',
            'description': 'Complete a habit before 9 AM',
            'icon': '🌅',
            'points': 150,
            'requirement': 'daily_completion:1'
        },
        {
            'name': 'Point Millionaire',
            'description': 'Earn 10,000 points',
            'icon': '💰',
            'points': 1000,
            'requirement': 'points:10000'
        },
        {
            'name': 'Perfect Week',
            'description': 'Complete all habits every day for a week',
            'icon': '📅',
            'points': 400,
            'requirement': 'daily_completion:7'
        },
        {
            'name': 'Habit Legend',
            'description': 'Maintain a 100-day streak',
            'icon': '🏆',
            'points': 1000,
            'requirement': 'streak:100'
        },
        {
            'name': 'Social Butterfly',
            'description': 'Complete 20 different habits',
            'icon': '🦋',
            'points': 600,
            'requirement': 'complete_habits:20'
        },
        {
            'name': 'Night Owl',
            'description': 'Complete a habit after 10 PM',
            'icon': '🦉',
            'points': 150,
            'requirement': 'daily_completion:1'
        },
        {
            'name': 'Weekend Warrior',
            'description': 'Complete all habits on a weekend',
            'icon': '🎉',
            'points': 200,
            'requirement': 'daily_completion:5'
        },
        {
            'name': 'Habit Mastermind',
            'description': 'Complete 50 different habits',
            'icon': '🧠',
            'points': 1000,
            'requirement': 'complete_habits:50'
        },
        {
            'name': 'Point Billionaire',
            'description': 'Earn 100,000 points',
            'icon': '💎',
            'points': 5000,
            'requirement': 'points:100000'
        },
        {
            'name': 'Perfect Month',
            'description': 'Complete all habits every day for a month',
            'icon': '📆',
            'points': 2000,
            'requirement': 'daily_completion:30'
        },
        {
            'name': 'Habit Immortal',
            'description': 'Maintain a 365-day streak',
            'icon': '🌟',
            'points': 5000,
            'requirement': 'streak:365'
        },
        {
            'name': 'Category Explorer',
            'description': 'Complete habits from 5 different categories',
            'icon': '🎨',
            'points': 300,
            'requirement': 'complete_habits:5'
        },
        {
            'name': 'Morning Master',
            'description': 'Complete 3 habits before noon',
            'icon': '🌞',
            'points': 200,
            'requirement': 'daily_completion:3'
        }
    ]
    
    for achievement_data in achievements:
        if not Achievement.query.filter_by(name=achievement_data['name']).first():
            achievement = Achievement(**achievement_data)
            db.session.add(achievement)
    
    db.session.commit()

def init_db():
    with app.app_context():
        db.create_all()
        create_admin_user()
        create_default_habits()
        create_default_achievements()

@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_categories():
    if request.method == 'POST':
        name = request.form['name']
        color = request.form.get('color', '#4F46E5')
        
        # Check if category already exists
        if Category.query.filter_by(name=name).first():
            flash('A category with this name already exists.', 'error')
            return redirect(url_for('admin_categories'))
        
        category = Category(name=name, color=color)
        db.session.add(category)
        db.session.commit()
        
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        category.name = request.form['name']
        category.color = request.form.get('color', category.color)
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/edit_category.html', category=category)

@app.route('/admin/categories/<int:category_id>/delete')
@login_required
@admin_required
def admin_delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    # Remove category from all habits
    for habit in category.habits:
        habit.category_id = None
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('admin_categories'))

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 