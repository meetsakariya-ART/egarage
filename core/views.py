from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from .forms import UserSignupForm, LoginForm

# -------------------------------
# SIGNUP: Save to PostgreSQL -> Redirect to Login
# -------------------------------
def userSignupView(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            # Save the new user to pgAdmin 4
            user = form.save() 
            # Redirect to login page so Arjun can sign in
            return redirect('login') 
        else:
            # If Arjun doesn't show up in Admin, check your terminal for these errors
            print(form.errors) 
    else:
        form = UserSignupForm()
    
    return render(request, 'core/signup.html', {'form': form})

# -------------------------------
# LOGIN: Check Database -> Go to Dashboard
# -------------------------------
def loginView(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard') 
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})

# -------------------------------
# DASHBOARD: Protected Area
# -------------------------------
def dashboardView(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'core/dashboard.html', {'user': request.user})

# -------------------------------
# LOGOUT
# -------------------------------
def logoutView(request):
    logout(request)
    return redirect('login')