from django.urls import path
from .views import userSignupView, loginView, dashboardView, logoutView

urlpatterns = [
    # When Arjun clicks "Create Account", it uses this path
    path('signup/', userSignupView, name='signup'),
    
    # After signup, the view redirects Arjun here
    path('login/', loginView, name='login'),
    
    # After login, Arjun is transferred here
    path('dashboard/', dashboardView, name='dashboard'),
    
    # When Arjun clicks logout, he is sent back to 'login'
    path('logout/', logoutView, name='logout'),
]