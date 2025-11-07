from django.apps import AppConfig

class NewNameConfig(AppConfig):  # تغيير اسم الكلاس
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vite'  # تغيير هنا
    label = 'vite'  # إضافة هذا السطر لتجنب التكرار