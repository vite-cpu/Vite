# urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .views import logout_view

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='social/login.html'), name='login'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('profile/<str:username>/edit/', views.edit_profile, name='edit_profile'),
    path('friends/', views.friends, name='friends'),
    path('friend_request/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('accept_request/<str:username>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject_request/<str:username>/', views.reject_friend_request, name='reject_friend_request'),
    path('search/', views.search_users, name='search_users'),
    path('block_user/<str:username>/', views.block_user, name='block_user'),
    path('unblock_user/<str:username>/', views.unblock_user, name='unblock_user'),
    path('logout/', logout_view, name='logout_view'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),

    path("chat/<str:username>/", views.chat_view, name="chat"),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path("send-message/", views.send_message, name="send_message"),
    path("chat/<str:username>/get-messages/", views.get_messages, name="get_messages"),
    path('chat/list/<str:username>/', views.chat_list, name='chat_list'),
    path('profile/<str:username>/qr/', views.qr_code_view, name='qr_code_view'),
    path('notifications/', views.notifications, name='notifications'),
    
    path('reels/', views.reels_feed, name='reels_feed'),
    path('reels/upload/', views.upload_reel, name='upload_reel'),
    path('reels/<int:reel_id>/like/', views.like_reel, name='like_reel'),
    path('reels/<int:reel_id>/comment/', views.add_reel_comment, name='add_reel_comment'),
    path('reels/<int:reel_id>/delete/', views.delete_reel, name='delete_reel'),
    path('reels/view/<int:reel_id>/', views.reel_detail_view, name='reel_detail'),
    path('reels/<int:reel_id>/view/', views.record_reel_view, name='record_reel_view'),
    path('ai/ask/', views.ask_gemini, name='ask_gemini'),

    path('notifications/unread_count/', views.get_unread_notifications_count, name='unread_notifications_count'),
    path('messages/unread_count/', views.get_unread_messages_count, name='unread_messages_count'),
    path('notifications/mark_as_read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('activity/update/', views.update_user_activity, name='update_user_activity'),
    
    path("chat/screenshot-notification/", views.screenshot_notification, name="screenshot_notification"),

    # URLs for Stories
    path('story/upload/', views.upload_story, name='upload_story'),
    path('stories/<str:username>/', views.view_stories, name='view_stories'),
    path('story/<int:story_id>/like/', views.like_story, name='like_story'),
    path('story/<int:story_id>/delete/', views.delete_story, name='delete_story'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)