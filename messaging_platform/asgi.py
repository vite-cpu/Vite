import os
from django.core.asgi import get_asgi_application

# تعيين إعدادات Django الافتراضية
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'messaging_platform.settings')

# الحصول على تطبيق ASGI الأساسي
application = get_asgi_application()