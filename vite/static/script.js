        function searchChats(query) {
            let items = document.querySelectorAll('.user-item');
            items.forEach(item => {
                let name = item.querySelector('.user-name').innerText;
                if (name.toLowerCase().includes(query.toLowerCase()) || query === "") {
                    item.style.display = "flex";
                } else {
                    item.style.display = "none";
                }
            });
        }

        document.addEventListener("DOMContentLoaded", function() {
            // تحديث قائمة المحادثات كل 5 ثواني
            setInterval(updateChatList, 5000);
            
            function updateChatList() {
                fetch(`{% url 'chat_list' request.user.username %}`)
                    .then(response => response.text())
                    .then(html => {
                        const parser = new DOMParser();
                        const newDoc = parser.parseFromString(html, 'text/html');
                        const newChatList = newDoc.getElementById('chatList').innerHTML;
                        const currentChatList = document.getElementById('chatList');
                        
                        // حفظ العناصر النشطة الحالية
                        const activeItems = currentChatList.querySelectorAll('.user-item.new-message');
                        
                        // تحديث القائمة
                        currentChatList.innerHTML = newChatList;
                        
                        // إضافة علامة "جديد" للرسائل الجديدة
                        activeItems.forEach(item => {
                            const username = item.querySelector('.user-name').innerText.replace('جديد', '').trim();
                            const newItem = Array.from(currentChatList.querySelectorAll('.user-item')).find(item => {
                                return item.querySelector('.user-name').innerText.replace('جديد', '').trim() === username;
                            });
                            if (newItem) {
                                newItem.classList.add('new-message');
                                const nameElement = newItem.querySelector('.user-name');
                                if (!nameElement.innerHTML.includes('new-message-badge')) {
                                    nameElement.insertAdjacentHTML('afterbegin', '<span class="new-message-badge">جديد</span>');
                                }
                            }
                        });
                    })
                    .catch(error => console.error('Error updating chat list:', error));
            }
            
            // إزالة التمييز عند النقر على المحادثة
            document.getElementById('chatList').addEventListener('click', function(e) {
                const item = e.target.closest('.user-item');
                if (item) {
                    item.classList.remove('new-message');
                    const badge = item.querySelector('.new-message-badge');
                    if (badge) badge.remove();
                }
            });
        });
  
// منع تدوير الشاشة على الأجهزة المحمولة
function lockOrientation() {
    if (window.screen.orientation && window.screen.orientation.lock) {
        window.screen.orientation.lock('portrait').catch(function(error) {
            console.log('Orientation lock failed: ', error);
        });
    } else if (window.screen.lockOrientation) {
        window.screen.lockOrientation('portrait');
    } else if (window.screen.mozLockOrientation) {
        window.screen.mozLockOrientation('portrait');
    } else if (window.screen.msLockOrientation) {
        window.screen.msLockOrientation('portrait');
    }
}

// استدعاء الدالة عند تحميل الصفحة وعند تغيير الحجم
window.addEventListener('load', lockOrientation);
window.addEventListener('resize', lockOrientation);
