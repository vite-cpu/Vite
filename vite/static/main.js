        document.addEventListener("DOMContentLoaded", function () {
            // =================================================================
            // 1. تعريف جميع المتغيرات الأساسية مرة واحدة
            // =================================================================
            const chatBox = document.getElementById("chat-box");
            const messageInput = document.getElementById("message-input");
            const sendButton = document.getElementById("send-btn");
            const recordButton = document.getElementById("record-btn");
            const attachButton = document.getElementById("attach-btn");
            const fileInput = document.getElementById("file-input");
            const filePreviewContainer = document.getElementById("file-preview-container");
            const filePreviewImage = document.getElementById("file-preview-image");
            const removeFileButton = document.getElementById("remove-file-btn");

            const imageModal = document.getElementById("image-modal");
            const modalImage = document.getElementById("modal-image");
            const closeModal = document.getElementById("close-modal");
            const saveImageBtn = document.getElementById("save-image-btn");
            
            const recordTimer = document.getElementById("record-timer");

            const replyContainer = document.getElementById('reply-container');
            const replyCloseButton = document.querySelector('.reply-close');

            const otherUser = "{{ other_user.username }}";
            let lastMessageId = 0;
            let selectedFile = null;
            let replyingToMessage = null;

            // متغيرات خاصة بالتسجيل الصوتي
            let mediaRecorder;
            let audioChunks = [];
            let isRecording = false;
            let timerInterval;

            // =================================================================
            // 2. الدوال المساعدة
            // =================================================================
            function scrollToBottom() {
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            function formatTime(dateString) {
                if (!dateString) return '';
                const date = new Date(dateString);
                let hours = date.getHours();
                let minutes = date.getMinutes();
                minutes = minutes < 10 ? '0' + minutes : minutes;
                return hours + ':' + minutes;
            }

            // =================================================================
            // 3. منطق الواجهة الأمامية (UI Logic)
            // =================================================================
            
            messageInput.addEventListener('input', function() {
                const hasText = this.value.trim().length > 0;
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
                
                sendButton.style.display = hasText ? 'flex' : 'none';
                recordButton.style.display = hasText ? 'none' : 'flex';
                attachButton.style.display = hasText ? 'none' : 'flex';
            });
            messageInput.dispatchEvent(new Event('input'));

            attachButton.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', () => {
                if (fileInput.files.length > 0) {
                    selectedFile = fileInput.files[0];
                    const reader = new FileReader();
                    reader.onload = function(e) { filePreviewImage.src = e.target.result; }
                    reader.readAsDataURL(selectedFile);
                    filePreviewContainer.style.display = 'flex';
                }
            });
            removeFileButton.addEventListener('click', () => {
                selectedFile = null;
                fileInput.value = '';
                filePreviewContainer.style.display = 'none';
            });

            // =================================================================
            // 4. منطق الرد على الرسائل
            // =================================================================
            function setupReply(messageId, senderName, content, mediaType) {
                replyingToMessage = messageId;
                replyContainer.style.display = 'block';
                replyContainer.querySelector('.reply-sender').textContent = `رد على ${senderName}`;
                replyContainer.querySelector('.reply-content').textContent = content || '';
                replyContainer.querySelector('.reply-media').textContent = mediaType ? `[${mediaType}]` : '';
                messageInput.focus();
            }

            replyCloseButton.addEventListener('click', function(e) {
                e.stopPropagation();
                replyContainer.style.display = 'none';
                replyingToMessage = null;
            });

            // =================================================================
            // 5. منطق الرسائل الصوتية
            // =================================================================
            function startRecording() {
                navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(stream => {
                        isRecording = true;
                        recordButton.classList.add("recording");
                        recordTimer.style.display = 'inline';
                        messageInput.style.display = 'none';
                        
                        let seconds = 0;
                        recordTimer.textContent = '00:00';
                        timerInterval = setInterval(() => {
                            seconds++;
                            const min = Math.floor(seconds / 60).toString().padStart(2, '0');
                            const sec = (seconds % 60).toString().padStart(2, '0');
                            recordTimer.textContent = `${min}:${sec}`;
                        }, 1000);

                        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                        mediaRecorder.start();

                        mediaRecorder.addEventListener("dataavailable", event => audioChunks.push(event.data));
                        mediaRecorder.addEventListener("stop", () => {
                            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                            sendMessage(null, audioBlob); 
                            
                            isRecording = false;
                            recordButton.classList.remove("recording");
                            recordTimer.style.display = 'none';
                            messageInput.style.display = 'block';
                            clearInterval(timerInterval);
                            audioChunks = [];
                            stream.getTracks().forEach(track => track.stop());
                        });
                    })
                    .catch(err => {
                        console.error("Error accessing microphone:", err);
                        alert("لا يمكن الوصول للميكروفون. يرجى التأكد من إعطاء الإذن.");
                        isRecording = false;
                    });
            }

            function stopRecording() {
                if (mediaRecorder && mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
            }

            recordButton.addEventListener('click', () => {
                if (!isRecording) {
                    startRecording();
                } else {
                    stopRecording();
                }
            });

            // =================================================================
            // 6. دوال إرسال واستقبال الرسائل
            // =================================================================
            function sendMessage(contentOverride = null, audioBlob = null) {
    const content = contentOverride !== null ? contentOverride : messageInput.value.trim();
    if (!content && !selectedFile && !audioBlob) return;

    const sendingIndicator = document.getElementById("sending-indicator");
    sendingIndicator.style.display = 'block';
    
    // هذا هو السطر الذي يجب إضافته لتعطيل الزر
    sendButton.disabled = true;

    const formData = new FormData();
    formData.append('receiver', otherUser);
    formData.append('content', content);
    
    if (replyingToMessage) {
        formData.append('reply_to', replyingToMessage);
    }
    if (selectedFile) {
        if (selectedFile.type.startsWith('image/')) formData.append('image', selectedFile);
        else if (selectedFile.type.startsWith('video/')) formData.append('video', selectedFile);
    }
    if (audioBlob) {
        formData.append('voice_note', audioBlob, 'voicemessage.webm');
    }

    fetch("{% url 'send_message' %}", {
        method: "POST",
        headers: { "X-CSRFToken": "{{ csrf_token }}" },
        body: formData
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        if (ok) {
            addMessageToChat(data, true);
            messageInput.value = "";
            messageInput.style.height = 'auto';
            messageInput.dispatchEvent(new Event('input'));
            removeFileButton.click();
            replyCloseButton.click();
            scrollToBottom();
            
            const sendSuccess = document.getElementById("send-success");
            sendSuccess.style.display = 'block';
            setTimeout(() => { sendSuccess.style.display = 'none'; }, 2000);
        } else {
            throw new Error(data.error || "حدث خطأ غير معروف");
        }
    })
    .catch(error => {
        console.error("Error sending message:", error);
        alert("حدث خطأ في الإرسال: " + error.message);
    })
    .finally(() => {
        sendingIndicator.style.display = 'none';
        
        // هذا هو السطر الذي يجب إضافته لإعادة تفعيل الزر
        sendButton.disabled = false;
    });
}
            function addMessageToChat(msg, isNew) {
                const messageDiv = document.createElement("div");
                messageDiv.dataset.id = msg.id;

                if (msg.is_system_message) {
                    messageDiv.classList.add("system-message");
                    messageDiv.innerHTML = `<p>${msg.content}</p>`;
                } else {
                    messageDiv.classList.add("message");
                    const isSender = msg.sender === "{{ request.user.username }}";
                    messageDiv.classList.add(isSender ? "sent" : "received");

                    let replySection = '';
                    if (msg.reply_to) {
                        const replyTo = msg.reply_to;
                        let replyContent = replyTo.content || '';
                        let replyMedia = '';
                        if (replyTo.image_url) replyMedia = '📷 صورة';
                        else if (replyTo.video_url) replyMedia = '🎥 فيديو';
                        else if (replyTo.voice_note_url) replyMedia = '🎙️ رسالة صوتية';
                        
                        const replySenderName = replyTo.sender === "{{ request.user.username }}" ? 'أنت' : replyTo.sender;
                        replySection = `
                            <div class="reply-indicator">
                                <span class="reply-sender">${replySenderName}</span>
                                <span class="reply-content">${replyContent}</span>
                                ${replyMedia ? `<span class="reply-media">${replyMedia}</span>` : ''}
                            </div>`;
                    }

                    let mediaHTML = '';
                    let contentHTML = msg.content ? `<p>${msg.content.replace(/\n/g, '<br>')}</p>` : '';
                    let seenIcon = "";
                    if (isSender) {
                        const seenClass = msg.is_read ? 'fa-check-double' : 'fa-check';
                        const seenStyle = msg.is_read ? 'style="color: #4fc3f7;"' : '';
                        seenIcon = `<i class="fas ${seenClass}" ${seenStyle}></i>`;
                    }
                    
                    let timeAndSeenHTML = `<span class="message-time">${formatTime(msg.timestamp)} ${seenIcon}</span>`;

                    if (msg.voice_note_url) {
                        const uniqueId = `waveform-${msg.id}`;
                        messageDiv.innerHTML = `
                            ${replySection}
                            <div class="voice-message-container">
                                <button class="play-pause-btn" id="play-${uniqueId}"><i class="fas fa-play"></i></button>
                                <div id="${uniqueId}" class="waveform"></div>
                                <span id="duration-${uniqueId}" class="duration">00:00</span>
                            </div>
                            ${timeAndSeenHTML}`;
                    } else {
                        if (msg.image_url) mediaHTML = `<img src="${msg.image_url}" alt="Image" style="cursor:pointer;">`;
                        else if (msg.video_url) mediaHTML = `<video src="${msg.video_url}" controls></video>`;
                        messageDiv.innerHTML = `${replySection} ${mediaHTML} ${contentHTML} ${timeAndSeenHTML}`;
                    }
                }
                
                chatBox.appendChild(messageDiv);
                
                // Add event listener for replying
                if (!msg.is_system_message) {
                    messageDiv.addEventListener('click', (e) => {
                        if (e.target.tagName !== 'IMG' && e.target.tagName !== 'VIDEO' &&
                            !e.target.closest('.reply-indicator') && !e.target.closest('.play-pause-btn') &&
                            !e.target.closest('a')) {
                            
                            const senderName = msg.sender === "{{ request.user.username }}" ? 'أنت' : msg.sender;
                            let content = msg.content;
                            let mediaType = '';
                            if (msg.image_url) mediaType = 'صورة';
                            else if (msg.video_url) mediaType = 'فيديو';
                            else if (msg.voice_note_url) mediaType = 'رسالة صوتية';
                            
                            setupReply(msg.id, senderName, content, mediaType);
                        }
                    });
                }
                
                if (msg.voice_note_url) {
                    const uniqueId = `waveform-${msg.id}`;
                    const waveColor = msg.sender === "{{ request.user.username }}" ? 'rgba(255,255,255,0.5)' : '#A8A8A8';
                    const progressColor = msg.sender === "{{ request.user.username }}" ? '#ffffff' : '#3797f0';
                    const wavesurfer = WaveSurfer.create({
                        container: `#${uniqueId}`, waveColor: waveColor, progressColor: progressColor,
                        height: 40, barWidth: 2, responsive: true, cursorWidth: 0
                    });

                    wavesurfer.load(msg.voice_note_url);
                    const playBtn = document.getElementById(`play-${uniqueId}`);
                    playBtn.onclick = (e) => { e.stopPropagation(); wavesurfer.playPause(); };
                    wavesurfer.on('play', () => playBtn.innerHTML = '<i class="fas fa-pause"></i>');
                    wavesurfer.on('pause', () => playBtn.innerHTML = '<i class="fas fa-play"></i>');
                    wavesurfer.on('finish', () => playBtn.innerHTML = '<i class="fas fa-play"></i>');
                    wavesurfer.on('ready', () => {
                        const duration = wavesurfer.getDuration();
                        const min = Math.floor(duration / 60).toString().padStart(2, '0');
                        const sec = Math.floor(duration % 60).toString().padStart(2, '0');
                        document.getElementById(`duration-${uniqueId}`).textContent = `${min}:${sec}`;
                    });
                }

                if (isNew) {
                    lastMessageId = msg.id;
                }
            }
            
            // =================================================================
            // 7. جلب الرسائل والتحديث الدوري
            // =================================================================

            function fetchAndRenderMessages() {
                fetch(`/chat/${otherUser}/get-messages/`)
                    .then(response => response.json())
                    .then(messages => {
                        chatBox.innerHTML = "";
                        let latestId = 0;
                        messages.forEach(msg => {
                            addMessageToChat(msg, false);
                            if (msg.id > latestId) latestId = msg.id;
                        });
                        lastMessageId = latestId;
                        scrollToBottom();
                    });
            }

            function checkNewMessages() {
                fetch(`/chat/${otherUser}/get-messages/`)
                    .then(response => response.json())
                    .then(messages => {
                        messages.forEach(msg => {
                            const messageElement = chatBox.querySelector(`div[data-id='${msg.id}']`);
                            if (!messageElement) {
                                addMessageToChat(msg, true);
                                scrollToBottom();
                            } else {
                                if (msg.sender === "{{ request.user.username }}" && msg.is_read && !msg.is_system_message) {
                                    const icon = messageElement.querySelector('.message-time .fa-check');
                                    if (icon) {
                                        icon.classList.add('fa-check-double');
                                        icon.classList.remove('fa-check');
                                        icon.style.color = '#4fc3f7';
                                    }
                                }
                            }
                        });
                    });
            }
            
            // =================================================================
            // 8. ربط الأحداث وتشغيل الكود
            // =================================================================

            sendButton.addEventListener("click", () => sendMessage());
            messageInput.addEventListener("keypress", function(event) {
                if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                }
            });

            chatBox.addEventListener('click', function(event) {
                if (event.target.tagName === 'IMG' && event.target.closest('.message')) {
                    modalImage.src = event.target.src;
                    imageModal.style.display = "block";
                    saveImageBtn.href = event.target.src;
                }
            });
            closeModal.onclick = function() { imageModal.style.display = "none"; }

            

            fetchAndRenderMessages();
            setInterval(checkNewMessages, 3000);
        });
