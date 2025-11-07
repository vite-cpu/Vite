from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Post, Reel
from django.utils import timezone

class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True, label='الاسم الكامل')
    profile_picture = forms.ImageField(required=False, label='صورة الملف الشخصي')
    date_of_birth = forms.DateField(
        widget=forms.SelectDateWidget(years=range(timezone.now().year - 100, timezone.now().year - 5)), # Min age 5, max age 100
        required=False,
        label='تاريخ الميلاد'
    )
    gender = forms.ChoiceField(choices=CustomUser.GENDER_CHOICES, required=False, label='الجنس')
    relationship_status = forms.ChoiceField(choices=CustomUser.RELATIONSHIP_STATUS_CHOICES, required=False, label='الحالة الاجتماعية')

    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'password1', 'password2', 'profile_picture', 'date_of_birth', 'gender', 'relationship_status')

class ProfileEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.SelectDateWidget(years=range(timezone.now().year - 100, timezone.now().year - 5)),
        required=False,
        label='تاريخ الميلاد'
    )
    gender = forms.ChoiceField(choices=CustomUser.GENDER_CHOICES, required=False, label='الجنس')
    relationship_status = forms.ChoiceField(choices=CustomUser.RELATIONSHIP_STATUS_CHOICES, required=False, label='الحالة الاجتماعية')

    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'profile_picture', 'cover_photo', 'bio', 'date_of_birth', 'gender', 'relationship_status')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'profile_picture': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'cover_photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].required = False
        self.fields['cover_photo'].required = False
        self.fields['date_of_birth'].required = False
        self.fields['gender'].required = False
        self.fields['relationship_status'].required = False
        # Set labels for consistency if not already set via field definition
        self.fields['username'].label = 'اسم المستخدم'
        self.fields['full_name'].label = 'الاسم الكامل'
        self.fields['email'].label = 'البريد الإلكتروني'
        self.fields['profile_picture'].label = 'صورة الملف الشخصي'
        self.fields['cover_photo'].label = 'صورة الغلاف'
        self.fields['bio'].label = 'نبذة تعريفية'


class PostForm(forms.ModelForm):
    # إضافة حقل جديد للرسالة الصوتية
    voice_message = forms.FileField(required=False, label='رسالة صوتية')
    
    class Meta:
        model = Post
        fields = ['content', 'image', 'video', 'voice_message']
    
    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        image = cleaned_data.get('image')
        video = cleaned_data.get('video')
        voice_message = cleaned_data.get('voice_message')
        
        # التأكد من أن المنشور يحتوي على محتوى أو صورة أو فيديو أو رسالة صوتية
        if not content and not image and not video and not voice_message:
            raise forms.ValidationError("يجب أن يحتوي المنشور على محتوى كتابي، صورة، فيديو، أو رسالة صوتية.")
        
        # التأكد من عدم وجود أكثر من نوع وسائط (صورة/فيديو/صوت)
        media_count = sum(1 for item in [image, video, voice_message] if item)
        if media_count > 1:
            raise forms.ValidationError("لا يمكن نشر أكثر من نوع وسائط (صورة، فيديو، أو رسالة صوتية) في نفس المنشور.")
        
        return cleaned_data
    
class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('content', 'image', 'video')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3}),
        }

class FriendRequestForm(forms.Form):
    username = forms.CharField(max_length=150)

# ---------- Start of New ReelForm ----------
class ReelForm(forms.ModelForm):
    class Meta:
        model = Reel
        fields = ['video', 'caption']
        widgets = {
            'video': forms.ClearableFileInput(attrs={'accept': 'video/*', 'required': True}),
            'caption': forms.Textarea(attrs={'rows': 3, 'placeholder': 'اكتب تعليقًا وصفيًا (اختياري)...'}),
        }
        labels = {
            'video': 'اختر مقطع فيديو',
            'caption': 'الوصف',
        }
        help_texts = {
            'video': 'يجب أن يكون الفيديو بتنسيق مدعوم (مثل MP4, MOV).',
        }
# ---------- End of New ReelForm ----------