from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from vite import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.splash, name='splash'),
    path('', include('vite.urls')),
    path('home/', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='social/login.html'), name='login'),
    path('vite/', include('vite.urls')),
]