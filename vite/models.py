# models.py
import cloudinary
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from cloudinary.models import CloudinaryField
import qrcode
from io import BytesIO
from django.core.files import File


class CustomUser(AbstractUser):
    GENDER_CHOICES = [
        ('male', 'ذكر'),
        ('female', 'أنثى'),
        ('other', 'آخر'),
        ('', 'أفضل عدم القول'),
    ]
    RELATIONSHIP_STATUS_CHOICES = [
        ('single', 'أعزب/عزباء'),
        ('in_relationship', 'في علاقة'),
        ('engaged', 'مخطوب/مخطوبة'),
        ('married', 'متزوج/متزوجة'),
        ('complicated', 'معقد'),
        ('open_relationship', 'علاقة مفتوحة'),
        ('', 'أفضل عدم القول'),
    ]

    is_verified = models.BooleanField(default=False)
    full_name = models.CharField(max_length=100, blank=True)
    profile_picture = CloudinaryField('image', blank=True, null=True, default='profile_pics/default_profile.png')
    cover_photo = CloudinaryField('image', blank=True, null=True, default='cover_photos/default_cover.jpg')
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    relationship_status = models.CharField(max_length=20, choices=RELATIONSHIP_STATUS_CHOICES, blank=True, default='')
    friends = models.ManyToManyField('self', symmetrical=False, blank=True)
    friend_requests = models.ManyToManyField('self', symmetrical=False, blank=True,
                                           related_name='received_friend_requests')
    blocked_users = models.ManyToManyField('self', symmetrical=False, blank=True,
                                         related_name='blocked_by')
    points = models.IntegerField(default=0)
    qr_code = CloudinaryField('image', blank=True, null=True)
    last_active = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"@{self.username}"

    @property
    def has_blue_badge(self):
        return self.is_verified or self.friends.count() > 10

    @property
    def is_online(self):
        if self.last_active:
            return (timezone.now() - self.last_active) < timezone.timedelta(minutes=3)
        return False

    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        profile_url = f"https://yourdomain.com/profile/{self.username}" # Replace with your actual domain
        qr.add_data(profile_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        result = cloudinary.uploader.upload(
            buffer.getvalue(),
            folder="qr_codes",
            public_id=f"user_{self.id}_qr",
            overwrite=True
        )

        self.qr_code = result['secure_url']
        self.save(update_fields=['qr_code'])

        return self.qr_code

    def save(self, *args, **kwargs):
        is_new = not self.pk
        generating_qr = is_new and not self.qr_code
        if 'update_fields' in kwargs and 'qr_code' in kwargs['update_fields'] and generating_qr:
             fields = list(kwargs['update_fields'])
             if 'qr_code' in fields:
                 fields.remove('qr_code')
             kwargs['update_fields'] = tuple(fields) if fields else None

        super().save(*args, **kwargs)
        if generating_qr:
            self.generate_qr_code()


class Story(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='stories')
    image = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', resource_type="video", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Story"
        verbose_name_plural = "Stories"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Story by {self.user.username} from {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def preview_url(self):
        """
        Returns a thumbnail URL for videos or the direct URL for images.
        """
        if self.video and hasattr(self.video, 'public_id'):
            try:
                return cloudinary.CloudinaryVideo(self.video.public_id).build_url(
                    transformation=[
                        {'width': 300, 'height': 500, 'crop': 'fill'},
                        {'quality': 'auto', 'fetch_format': 'auto', 'format': 'jpg'}
                    ],
                    resource_type="video"
                )
            except Exception:
                return "/static/images/default_profile.png" # Fallback image
        if self.image:
            return self.image.url
        return "/static/images/default_profile.png" # Fallback image
        
    @property
    def likes_count(self):
        return self.story_likes.count()


class StoryLike(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='story_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'story')

    def __str__(self):
        return f"{self.user.username} likes Story {self.story.id}"


# models.py (داخل كلاس Message)

class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField(default="", blank=True)
    image = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', resource_type="video", blank=True, null=True)
    voice_note = CloudinaryField('video', resource_type="video", blank=True, null=True, folder="voice_notes")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)
    is_system_message = models.BooleanField(default=False)
    # إضافة حقل الرد على الرسالة
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"من {self.sender} إلى {self.receiver}: {self.content[:30]}"

    def mark_as_seen(self):
        if not self.is_read:
            self.is_read = True
            self.seen_at = timezone.now()
            self.save()
            
class Chat(models.Model):
    participants = models.ManyToManyField(CustomUser, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Chat {self.id}"

class Post(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    image = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', resource_type="video", blank=True, null=True)
    voice_note = CloudinaryField('video', resource_type="video", blank=True, null=True, folder="voice_notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post by {self.user.username}"

class Like(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} likes {self.post.id}"

class Comment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}"

class SavedPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} saved {self.post.id}"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('message', 'رسالة جديدة'),
        ('like', 'إعجاب'),
        ('comment', 'تعليق'),
        ('friend_request', 'طلب صداقة'),
        ('friend_accept', 'قبول الصداقة'),
        ('reel_like', 'إعجاب على ريل'),
        ('reel_comment', 'تعليق على ريل'),
        ('story_like', 'إعجاب على القصة'),
    )

    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    related_id = models.PositiveIntegerField(null=True, blank=True) # Can be Post ID, User ID, Reel ID etc.

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} لـ {self.recipient.username}"

class Reel(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reels')
    video = CloudinaryField('video', resource_type="video")
    caption = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views_count = models.PositiveIntegerField(default=0)
    viewers = models.ManyToManyField(CustomUser, related_name='viewed_reels', blank=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reel by {self.user.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def likes_count(self):
        return self.reel_likes.count()

    @property
    def comments_count(self):
        return self.reel_comments.count()

    @property
    def thumbnail_url(self):
        if self.video and hasattr(self.video, 'public_id'):
            try:
                thumbnail_url = cloudinary.CloudinaryVideo(self.video.public_id).build_url(
                    transformation=[
                        {'width': 300, 'height': 500, 'crop': 'fill'},
                        {'quality': 'auto'},
                        {'format': 'jpg'},
                        {'fetch_format': 'auto'},
                ],
                resource_type="video",
                )
                return thumbnail_url
            except Exception as e:
                print(f"Error generating thumbnail: {e}")
                return ""
        return ""


class ReelLike(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='reel_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reel')

    def __str__(self):
        return f"{self.user.username} likes Reel {self.reel.id}"

class ReelComment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='reel_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on Reel {self.reel.id}: {self.content[:20]}"