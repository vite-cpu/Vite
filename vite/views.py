# views.py
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm, ProfileEditForm, PostEditForm, ReelForm
from .models import Post, Like, Comment, SavedPost, CustomUser, Notification, Message, Reel, ReelLike, ReelComment, Story, StoryLike
from django.http import JsonResponse, Http404, HttpResponseForbidden
import cloudinary.uploader
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST
from django.db import models as django_models
import json
from django.utils import timezone
import pytz
from django.utils.html import strip_tags, escape
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.db.models import F, Exists, OuterRef
import google.generativeai as genai
from django import forms
import random
from django.views.decorators.cache import cache_page


User = get_user_model()


# Helper Form for Story Upload - This would typically be in forms.py
class StoryForm(forms.ModelForm):
    class Meta:
        model = Story
        fields = ['image', 'video']

    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get("image")
        video = cleaned_data.get("video")
        if not image and not video:
            raise forms.ValidationError("يجب رفع صورة أو فيديو.")
        if image and video:
            raise forms.ValidationError("لا يمكن رفع صورة وفيديو في نفس القصة. يرجى اختيار واحد فقط.")
        return cleaned_data

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة
@login_required
def home(request):
    blocked_users = request.user.blocked_users.all()
    posts = Post.objects.exclude(user__in=blocked_users).order_by('-created_at')
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = SavedPost.objects.filter(user=request.user, post=post).exists()
    
    home_reels = Reel.objects.select_related('user').order_by('?')[:10]

    # --- Start of Stories Logic ---
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    story_user_ids = Story.objects.filter(
        created_at__gte=twenty_four_hours_ago
    ).exclude(
        user__in=blocked_users
    ).values_list('user_id', flat=True).distinct()

    all_story_users = list(CustomUser.objects.filter(id__in=story_user_ids))
    
    current_user_with_story = None
    for i, user in enumerate(all_story_users):
        if user.id == request.user.id:
            current_user_with_story = all_story_users.pop(i)
            break
            
    random.shuffle(all_story_users)
    
    sorted_story_users = []
    if current_user_with_story:
        sorted_story_users.append(current_user_with_story)
    sorted_story_users.extend(all_story_users)

    users_with_previews = []
    for user in sorted_story_users:
        try:
            latest_story = Story.objects.filter(
                user=user, created_at__gte=twenty_four_hours_ago
            ).latest('created_at')
            users_with_previews.append({
                'user': user,
                'preview_story': latest_story
            })
        except Story.DoesNotExist:
            continue
    # --- End of Stories Logic ---

    unread_messages_count = Message.objects.filter(
        receiver=request.user, is_read=False
    ).count()
    
    unread_notifications_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    
    context = {
        'posts': posts,
        'home_reels': home_reels,
        'stories_data': {
            'users_with_previews': users_with_previews
        },
        'unread_messages_count': unread_messages_count,
        'unread_count': unread_notifications_count,
    }
    return render(request, 'social/home.html', context)

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def upload_story(request):
    if request.method == 'POST':
        form = StoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.user = request.user
            story.save()
            messages.success(request, 'تم نشر قصتك بنجاح!')
            return redirect('home')
        else:
            # Pass the form with errors back to the template
            return render(request, 'social/upload_story.html', {'form': form})
    
    form = StoryForm()
    return render(request, 'social/upload_story.html', {'form': form})

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def view_stories(request, username):
    try:
        story_user = get_object_or_404(CustomUser, username=username)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)

        if story_user in request.user.blocked_users.all():
            raise Http404("User not found.")

        user_stories = Story.objects.filter(
            user=story_user,
            created_at__gte=twenty_four_hours_ago
        ).annotate(
            is_liked=Exists(StoryLike.objects.filter(story_id=OuterRef('pk'), user=request.user))
        ).order_by('created_at')

        if not user_stories.exists():
            messages.info(request, "لا توجد قصص نشطة لهذا المستخدم.")
            return redirect('profile', username=username)

        context = {
            'story_user': story_user,
            'stories': user_stories
        }
        return render(request, 'social/view_stories.html', context)
    except CustomUser.DoesNotExist:
        raise Http404("User not found.")


@login_required
@require_POST
def like_story(request, story_id):
    story = get_object_or_404(Story, id=story_id)
    like, created = StoryLike.objects.get_or_create(user=request.user, story=story)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if request.user != story.user:
            Notification.objects.create(
                recipient=story.user,
                sender=request.user,
                notification_type='story_like',
                content=f"أعجب {request.user.username} بقصتك",
                related_id=story.id
            )
    return JsonResponse({'liked': liked, 'likes_count': story.likes_count})


@login_required
@require_POST
def delete_story(request, story_id):
    story = get_object_or_404(Story, id=story_id)
    if story.user != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    
    story.delete()
    return JsonResponse({'success': True, 'message': 'Story deleted successfully.'})

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
@require_POST
def update_user_activity(request):
    request.user.last_active = timezone.now()
    request.user.save(update_fields=['last_active'])
    return JsonResponse({'status': 'success'})

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            if 'image' in request.FILES:
                upload_result = cloudinary.uploader.upload(request.FILES['image'])
                post.image = upload_result.get('secure_url', upload_result.get('url'))
            if 'video' in request.FILES:
                upload_result = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")
                post.video = upload_result.get('secure_url', upload_result.get('url'))
            post.save()
            request.user.points += 10
            request.user.save()
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'social/create_post.html', {'form': form})


@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if created:
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='like',
                content=f"{request.user.username} أعجب بمنشورك",
                related_id=post.id
            )
    else:
        like.delete()
    return JsonResponse({
        'liked': created,
        'likes_count': post.likes.count(),
        'post_id': post_id
    })

@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'التعليق لا يمكن أن يكون فارغًا.'})
        
        post = get_object_or_404(Post, id=post_id)
        comment = Comment.objects.create(user=request.user, post=post, content=content)
        
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='comment',
                content=f"{request.user.username} علق على منشورك",
                related_id=post.id
            )
        return JsonResponse({
            'success': True,
            'username': request.user.username,
            'content': comment.content,
            'profile_picture': request.user.profile_picture.url if request.user.profile_picture else '/media/profile_pics/default_profile.png'
        })
    return JsonResponse({'success': False, 'error': 'طلب غير صالح.'})


@login_required
def send_friend_request(request, username):
    receiver = get_object_or_404(CustomUser, username=username)
    if request.user != receiver and receiver not in request.user.friend_requests.all():
        request.user.friend_requests.add(receiver)
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='friend_request',
            content=f"{request.user.username} أرسل لك طلب صداقة",
            related_id=request.user.id
        )
    return redirect('profile', username=username)

@login_required
def accept_friend_request(request, username):
    sender = get_object_or_404(CustomUser, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.friends.add(sender)
        sender.friends.add(request.user)
        request.user.received_friend_requests.remove(sender)
        Notification.objects.create(
            recipient=sender,
            sender=request.user,
            notification_type='friend_accept',
            content=f"{request.user.username} قبل طلب صداقتك",
            related_id=request.user.id
        )
    return redirect('friends')

@login_required
def reject_friend_request(request, username):
    sender = get_object_or_404(CustomUser, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.received_friend_requests.remove(sender)
    return redirect('friends')
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def profile(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    posts = user_profile.posts.all().order_by('-created_at')
    is_friend = user_profile in request.user.friends.all()
    has_sent_request = user_profile in request.user.friend_requests.all()
    has_received_request = request.user in user_profile.friend_requests.all()
    context = {
        'profile_user': user_profile,
        'posts': posts,
        'is_friend': is_friend,
        'has_sent_request': has_sent_request,
        'has_received_request': has_received_request,
    }
    return render(request, 'social/profile.html', context)
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def qr_code_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    if not user_profile.qr_code:
        user_profile.generate_qr_code()
    return render(request, 'social/qr_code.html', {'profile_user': user_profile})
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def friends(request):
    user_friends = request.user.friends.all()
    received_requests = request.user.received_friend_requests.all()
    sent_requests = request.user.friend_requests.all()
    context = {
        'friends': user_friends,
        'received_requests': received_requests,
        'sent_requests': sent_requests,
    }
    return render(request, 'social/friends.html', context)
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def search_users(request):
    query = request.GET.get('q', '')
    users_results = CustomUser.objects.filter(username__icontains=query) | CustomUser.objects.filter(full_name__icontains=query)
    return render(request, 'social/search_results.html', {'users': users_results, 'query': query})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user_obj = form.save(commit=False)
            if 'profile_picture' in request.FILES:
                user_obj.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            user_obj.save()
            auth_login(request, user_obj)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'social/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user_auth = authenticate(username=username, password=password)
            if user_auth is not None:
                auth_login(request, user_auth)
                return redirect('home')
            else:
                messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة")
        else:
            messages.error(request, "يرجى تصحيح الأخطاء في النموذج")
    else:
        form = AuthenticationForm()
    return render(request, 'social/login.html', {'form': form})

@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def block_user(request, username):
    user_to_block = get_object_or_404(CustomUser, username=username)
    if request.user == user_to_block:
        return redirect('profile', username=username)
    request.user.blocked_users.add(user_to_block)
    request.user.friend_requests.remove(user_to_block)
    user_to_block.friend_requests.remove(request.user)
    request.user.friends.remove(user_to_block)
    user_to_block.friends.remove(request.user)
    return redirect('profile', username=username)

@login_required
def unblock_user(request, username):
    user_to_unblock = get_object_or_404(CustomUser, username=username)
    request.user.blocked_users.remove(user_to_unblock)
    return redirect('profile', username=username)
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def edit_profile(request, username):
    if request.user.username != username:
        return redirect('profile', username=username)
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user_instance = form.save(commit=False)
            if 'profile_picture' in request.FILES:
                user_instance.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            elif 'profile_picture-clear' in request.POST:
                user_instance.profile_picture = None
            if 'cover_photo' in request.FILES:
                user_instance.cover_photo = cloudinary.uploader.upload(request.FILES['cover_photo'])['url']
            elif 'cover_photo-clear' in request.POST:
                user_instance.cover_photo = None
            user_instance.save()
            return redirect('profile', username=username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'social/edit_profile.html', {'form': form})

@login_required
def edit_post(request, post_id):
    post_instance = get_object_or_404(Post, id=post_id)
    if request.user != post_instance.user:
        return redirect('home')
    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post_instance)
        if form.is_valid():
            post_to_edit = form.save(commit=False)
            if 'image' in request.FILES:
                post_to_edit.image = cloudinary.uploader.upload(request.FILES['image'])['url']
            if 'video' in request.FILES:
                post_to_edit.video = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")['url']
            post_to_edit.save()
            return redirect('profile', username=request.user.username)
    else:
        form = PostEditForm(instance=post_instance)
    return render(request, 'social/edit_post.html', {'form': form, 'post': post_instance})

@login_required
def delete_post(request, post_id):
    post_to_delete = get_object_or_404(Post, id=post_id)
    if request.user != post_to_delete.user:
        return redirect('home')
    if request.method == 'POST':
        request.user.points = max(0, request.user.points - 10)
        request.user.save()
        post_to_delete.delete()
        return redirect('profile', username=request.user.username)
    return render(request, 'social/confirm_delete.html', {'post': post_to_delete})

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def chat_view(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user not in request.user.friends.all():
        messages.error(request, "لا يمكنك بدء محادثة مع شخص ليس صديقك.")
        return redirect('home')
        
    unread_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    )
    for msg in unread_messages:
        msg.mark_as_seen()
    messages_qs = Message.objects.filter(
        sender__in=[request.user, other_user],
        receiver__in=[request.user, other_user]
    ).order_by("timestamp")
    return render(request, "chat.html", {
        "messages": messages_qs,
        "other_user": other_user
    })

# views.py (تعديل دالة send_message)
@login_required
@require_POST
def send_message(request):
    receiver_username = request.POST.get("receiver")
    if not receiver_username:
        return JsonResponse({"error": "المستلم غير محدد."}, status=400)

    receiver = get_object_or_404(CustomUser, username=receiver_username)

    if receiver not in request.user.friends.all():
        return JsonResponse({"error": "لا يمكنك إرسال رسائل إلى شخص ليس صديقك."}, status=403)

    content = request.POST.get("content", "").strip()
    image_file = request.FILES.get('image')
    video_file = request.FILES.get('video')
    voice_file = request.FILES.get('voice_note')
    reply_to_id = request.POST.get("reply_to")  # الحصول على معرف الرسالة المردود عليها

    if not content and not image_file and not video_file and not voice_file:
        return JsonResponse({"error": "لا يمكن إرسال رسالة فارغة"}, status=400)

    # الحصول على الرسالة المردود عليها إذا وجدت
    reply_to_message = None
    if reply_to_id:
        try:
            reply_to_message = Message.objects.get(id=reply_to_id, 
                                                 sender__in=[request.user, receiver],
                                                 receiver__in=[request.user, receiver])
        except Message.DoesNotExist:
            pass

    message = Message(
        sender=request.user,
        receiver=receiver,
        content=content,
        is_system_message=False,
        reply_to=reply_to_message  # تعيين الرسالة المردود عليها
    )

    if image_file:
        message.image = image_file

    if video_file:
        message.video = video_file
    
    if voice_file:
        message.voice_note = voice_file

    message.save()
    
    response_data = {
        "id": message.id,
        "sender": message.sender.username,
        "receiver": receiver.username,
        "content": message.content,
        "image_url": message.image.url if message.image else None,
        "video_url": message.video.url if message.video else None,
        "voice_note_url": message.voice_note.url if message.voice_note else None,
        "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "is_read": message.is_read,
        "seen_at": None,
        "is_system_message": message.is_system_message,
        "reply_to": None
    }

    # إضافة بيانات الرسالة المردود عليها إذا وجدت
    if reply_to_message:
        response_data["reply_to"] = {
            "id": reply_to_message.id,
            "sender": reply_to_message.sender.username,
            "content": reply_to_message.content,
            "image_url": reply_to_message.image.url if reply_to_message.image else None,
            "video_url": reply_to_message.video.url if reply_to_message.video else None,
            "voice_note_url": reply_to_message.voice_note.url if reply_to_message.voice_note else None,
        }

    return JsonResponse(response_data)

# views.py (تعديل دالة get_messages)
@login_required
def get_messages(request, username):
    other_user = get_object_or_404(CustomUser, username=username)
    if other_user not in request.user.friends.all():
        return JsonResponse({"error": "لا يمكنك عرض الرسائل مع شخص ليس صديقك."}, status=403)
        
    messages_qs = Message.objects.filter(
        (django_models.Q(sender=request.user, receiver=other_user) |
         django_models.Q(sender=other_user, receiver=request.user))
    ).select_related('reply_to').order_by("timestamp")

    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True, seen_at=timezone.now())

    return JsonResponse([
        {
            "id": msg.id,
            "sender": msg.sender.username,
            "receiver": msg.receiver.username,
            "content": msg.content,
            "image_url": msg.image.url if msg.image else None,
            "video_url": msg.video.url if msg.video else None,
            "voice_note_url": msg.voice_note.url if msg.voice_note else None,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": msg.is_read,
            "seen_at": msg.seen_at.strftime("%Y-%m-%d %H:%M:%S") if msg.seen_at else None,
            "is_system_message": msg.is_system_message,
            "reply_to": {
                "id": msg.reply_to.id,
                "sender": msg.reply_to.sender.username,
                "content": msg.reply_to.content,
                "image_url": msg.reply_to.image.url if msg.reply_to.image else None,
                "video_url": msg.reply_to.video.url if msg.reply_to.video else None,
                "voice_note_url": msg.reply_to.voice_note.url if msg.reply_to.voice_note else None,
            } if msg.reply_to else None
        }
        for msg in messages_qs
    ], safe=False)
# --- إضافة جديدة ---
@login_required
@require_POST
def delete_message(request, message_id):
    try:
        # ابحث عن الرسالة وتأكد أن طالب الحذف هو المرسل
        message = get_object_or_404(Message, id=message_id, sender=request.user)
        
        # قم بحذف الرسالة
        message.delete()
        
        return JsonResponse({'success': True, 'message_id': message_id})

    except Message.DoesNotExist:
        # إذا حاول مستخدم حذف رسالة لا يملكها، يتم رفض الطلب
        return JsonResponse({'success': False, 'error': 'Message not found or permission denied.'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
# ------------------
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def chat_list(request, username):
    try:
        current_user = request.user
        friends = current_user.friends.all() 
        query = request.GET.get('q', '')
        if query:
            friends = friends.filter(username__icontains=strip_tags(query))
            
        user_data = []
        for user_item in friends: 
            last_sent = Message.objects.filter(
                sender=current_user,
                receiver=user_item
            ).order_by('-timestamp').first()
            last_received = Message.objects.filter(
                sender=user_item,
                receiver=current_user
            ).order_by('-timestamp').first()
            last_message = None
            if last_sent and last_received:
                last_message = last_sent if last_sent.timestamp > last_received.timestamp else last_received
            else:
                last_message = last_sent or last_received
            is_new = False
            if last_message and last_message.receiver == current_user and not last_message.is_read:
                is_new = True
            
            last_message_content = "لا توجد رسائل"
            if last_message:
                if last_message.content:
                    last_message_content = strip_tags(last_message.content)
                elif last_message.image:
                    last_message_content = "📷 صورة"
                elif last_message.video:
                    last_message_content = "🎥 فيديو"

            user_data.append({
                'user': user_item,
                'last_message': last_message_content,
                'last_time': last_message.timestamp if last_message else None,
                'is_new': is_new
            })
        user_data.sort(key=lambda x: x['last_time'] or timezone.datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
        return render(request, 'chat_list.html', {
            'all_users': user_data,
            'current_user': current_user
        })
    except Exception as e:
        raise Http404(f"حدث خطأ: {str(e)}")

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def chat(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user not in request.user.friends.all():
        messages.error(request, "لا يمكنك بدء محادثة مع شخص ليس صديقك.")
        return redirect('home')
        
    context = {
        'other_user': other_user,
    }
    return render(request, 'chat.html', context)


def splash(request):
    return render(request, 'splash.html')

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def notifications(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    notifications_qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    return render(request, 'social/notifications.html', {
        'notifications': notifications_qs,
    })

@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def get_unread_notifications_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def get_unread_messages_count(request):
    count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user != comment.user and request.user != comment.post.user:
        return JsonResponse({'success': False, 'error': 'غير مسموح لك بحذف هذا التعليق'}, status=403)
    if request.method == 'POST':
        post_id = comment.post.id
        comment.delete()
        return JsonResponse({'success': True, 'post_id': post_id})
    return JsonResponse({'success': False, 'error': 'طريقة غير مسموحة'}, status=405)

def game_view(request):
    return render(request, 'game.html')
@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

@login_required
def reels_feed(request):
    featured_reel_id = request.GET.get('show_reel')
    reels_list = []

    if featured_reel_id:
        try:
            featured_reel = Reel.objects.select_related('user').prefetch_related(
                'reel_likes', 'reel_comments__user'
            ).get(id=featured_reel_id)
            reels_list.append(featured_reel)

            other_reels = Reel.objects.exclude(id=featured_reel_id).select_related('user').prefetch_related(
                'reel_likes', 'reel_comments__user'
            ).order_by('?')
            reels_list.extend(list(other_reels))

        except Reel.DoesNotExist:
            featured_reel_id = None
    
    if not featured_reel_id:
        time_threshold = timezone.now() - timedelta(hours=5)
        new_reels = Reel.objects.filter(created_at__gte=time_threshold).select_related('user').prefetch_related(
            'reel_likes', 'reel_comments__user'
        ).order_by('-created_at')
        old_reels = Reel.objects.filter(created_at__lt=time_threshold).select_related('user').prefetch_related(
            'reel_likes', 'reel_comments__user'
        ).order_by('?')
        reels_list = list(new_reels) + list(old_reels)

    reels_data = []
    for reel in reels_list:
        is_liked_by_user = reel.reel_likes.filter(user=request.user).exists()
        comments_for_reel = reel.reel_comments.all().order_by('created_at')
        reels_data.append({
            'reel': reel,
            'is_liked_by_user': is_liked_by_user,
            'comments_list': comments_for_reel,
        })
        
    user_profile_pic_url = request.user.profile_picture.url if request.user.profile_picture else \
                           '/static/images/default_profile.png'

    context = {
        'reels_data': reels_data,
        'user_profile_pic_url': user_profile_pic_url,
    }
    return render(request, 'social/reels_feed.html', context)


@login_required
def upload_reel(request):
    if request.method == 'POST':
        form = ReelForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.user = request.user
            reel.save()
            messages.success(request, 'تم نشر الريل بنجاح!')
            return redirect('reels_feed')
        else:
            messages.error(request, 'حدث خطأ أثناء رفع الريل. يرجى التحقق من النموذج.')
    else:
        form = ReelForm()
    return render(request, 'social/upload_reel.html', {'form': form})


@login_required
@require_POST
def like_reel(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)
    like, created = ReelLike.objects.get_or_create(user=request.user, reel=reel)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if request.user != reel.user:
            Notification.objects.create(
                recipient=reel.user,
                sender=request.user,
                notification_type='reel_like',
                content=f"أعجب {request.user.username} بالريل الخاص بك",
                related_id=reel.id
            )
    return JsonResponse({'liked': liked, 'likes_count': reel.likes_count})

@login_required
@require_POST
def add_reel_comment(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)
    content = request.POST.get('content', '').strip()

    if not content:
        return JsonResponse({'success': False, 'error': 'التعليق لا يمكن أن يكون فارغًا.'}, status=400)

    comment = ReelComment.objects.create(user=request.user, reel=reel, content=content)
    
    if request.user != reel.user:
        Notification.objects.create(
            recipient=reel.user,
            sender=request.user,
            notification_type='reel_comment',
            content=f"علق {request.user.username} على الريل الخاص بك",
            related_id=reel.id
        )
    
    profile_picture_url = request.user.profile_picture.url if request.user.profile_picture else \
                          '/static/images/default_profile.png'

    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'user': {
                'username': comment.user.username,
                'profile_picture_url': profile_picture_url
            },
            'content': escape(comment.content),
            'created_at': timezone.localtime(comment.created_at).strftime('%d %b, %Y %H:%M'),
            'timesince': timezone.now() - comment.created_at
        },
        'comments_count': reel.comments_count
    })


@login_required
@require_POST
def delete_reel(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)

    if reel.user != request.user:
        return HttpResponseForbidden(json.dumps({'success': False, 'error': 'ليس لديك صلاحية لحذف هذا الريل.'}), content_type='application/json')
    
    try:
        if reel.video and hasattr(reel.video, 'public_id'):
            cloudinary.uploader.destroy(reel.video.public_id, resource_type="video")

        reel.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        print(f"Error deleting reel {reel_id}: {e}")
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء محاولة حذف الريل.'}, status=500)

def reel_detail_view(request, reel_id):
    reel = get_object_or_404(Reel.objects.select_related('user').prefetch_related('reel_comments__user'), id=reel_id)

    is_liked_by_user = False
    if request.user.is_authenticated:
        is_liked_by_user = reel.reel_likes.filter(user=request.user).exists()

    comments_list = reel.reel_comments.all().order_by('-created_at')

    reel_data = {
        'reel': reel,
        'is_liked_by_user': is_liked_by_user,
        'comments_list': comments_list,
    }

    context = {
        'reel_data': reel_data,
    }
    return render(request, 'social/reel_detail.html', context)

@login_required
@require_POST
def record_reel_view(request, reel_id):
    try:
        reel = get_object_or_404(Reel, pk=reel_id)
        
        if request.user not in reel.viewers.all():
            reel.viewers.add(request.user)
            reel.views_count = F('views_count') + 1
            reel.save(update_fields=['views_count'])
            
            reel.refresh_from_db()
            
            return JsonResponse({
                'success': True, 
                'views_count': reel.views_count,
                'is_new_view': True
            })
        else:
            return JsonResponse({
                'success': True, 
                'views_count': reel.views_count,
                'is_new_view': False
            })
            
    except Exception as e:
        print(f"Error recording reel view: {e}")
        return JsonResponse({
            'success': False, 
            'error': 'An internal error occurred'
        }, status=500)

@login_required
@require_POST
def ask_gemini(request):
    try:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return JsonResponse({'error': 'مفتاح API الخاص بـ Gemini غير مهيأ في الإعدادات.'}, status=500)
        genai.configure(api_key=api_key)
    except AttributeError:
        return JsonResponse({'error': 'مفتاح API الخاص بـ Gemini غير موجود في ملف الإعدادات.'}, status=500)

    try:
        data = json.loads(request.body)
        prompt = data.get('prompt')
        history = data.get('history', [])
        if not prompt:
            return JsonResponse({'error': 'الطلب (prompt) فارغ.'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'طلب JSON غير صالح.'}, status=400)

    try:
        system_instruction = (
            "أنت مساعد ذكي اسمه Trimer AI. مهمتك هي فهم السياق وتقديم إجابات دقيقة بناءً على المحادثة السابقة.\n"
            "إرشادات:\n"
            "1. افترض أن الأسئلة المختصرة مرتبطة بالسياق السابق.\n"
            "2. إذا قال المستخدم 'هههه' أو 'اوك' أو 'xd'، رد برد لطيف وموجز.\n"

            "3. لا تكرر نفس الإجابة.\n"
            "4. لا تقل 'غامض' أو 'أخشى'، بل افترض.\n"
            "5. حافظ على نبرة ودودة واحترافية.\n"
            "6. Trimer هي منصة تواصل اجتماعي، وأنا Trimer AI طورتني سالم أحمد."
        )

        if prompt and len(prompt.split()) <= 3 and history:
            last_user_topic = next((msg["content"] for msg in reversed(history) if msg["role"] == "user" and len(msg["content"].split()) > 2), "")
            last_model_reply = next((msg["content"] for msg in reversed(history) if msg["role"] == "model" and len(msg["content"].split()) > 2), "")
            context_base = last_user_topic or last_model_reply
            if context_base:
                prompt = f"{context_base} - {prompt}"

        formatted_history = [
            {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]}
            for msg in history
        ]

        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=system_instruction
        )
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.5,
                "top_p": 0.9,
                "top_k": 40
            }
        )

        ai_response = response.text or ""

        if formatted_history and len(formatted_history) >= 2:
            last_model_msg = formatted_history[-1]["parts"][0]
            if ai_response.strip() == last_model_msg.strip():
                ai_response = "يبدو أنني أجبت على هذا مسبقًا. هل ننتقل لموضوع جديد؟ 😊"

        if any(word in prompt.lower() for word in ["هههه", "xd", "lol", "اوك", "تمام"]):
            ai_response = "😂 واضح أنك مستمتع! تحب تسألني عن شيء؟"
        elif not ai_response:
            ai_response = "عذرًا، لم أتمكن من فهم سؤالك."
        elif "غامض" in ai_response or "أخشى" in ai_response:
            last_user_q = next((msg["parts"][0] for msg in reversed(formatted_history) if msg["role"] == "user"), "")
            if last_user_q:
                ai_response = f"بناءً على سؤالك السابق عن '{last_user_q}'، {ai_response.replace('غامض', 'واضح').replace('أخشى', 'أفترض')}"

        return JsonResponse({
            'response': ai_response,
            'history': formatted_history + [
                {"role": "user", "parts": [prompt]},
                {"role": "model", "parts": [ai_response]}
            ]
        })

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return JsonResponse({
            'error': 'حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى لاحقًا.',
            'details': str(e)
        }, status=500)

@login_required
@require_POST
def screenshot_notification(request):
    try:
        data = json.loads(request.body)
        receiver_username = data.get("receiver")
        if not receiver_username:
            return JsonResponse({"error": "المستلم غير محدد."}, status=400)

        receiver = get_object_or_404(CustomUser, username=receiver_username)

        Message.objects.create(
            sender=request.user,
            receiver=receiver,
            content=f"لقد قام {request.user.username} بلقطة شاشة",
            is_system_message=True
        )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)