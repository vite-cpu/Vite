// اسم الكاش
const CACHE_NAME = 'trimer-cache-v1';

// قائمة بالملفات المراد تخزينها
// سأفترض هنا مسارات قياسية. يرجى تعديلها إذا كانت مختلفة.
const urlsToCache = [
    '/',
    '{% static "manifest.json" %}', // ملف المانيفيست الخاص بك
    '{% static "serviceworker.js" %}', // Service Worker نفسه
    
    // الأيقونات التي أرسلتها (مع تعديل المسار)
    '{% static "pwa-icons/apple-icon-57x57.png" %}',
    '{% static "pwa-icons/apple-icon-60x60.png" %}',
    '{% static "pwa-icons/apple-icon-72x72.png" %}',
    '{% static "pwa-icons/apple-icon-76x76.png" %}',
    '{% static "pwa-icons/apple-icon-114x114.png" %}',
    '{% static "pwa-icons/apple-icon-120x120.png" %}',
    '{% static "pwa-icons/apple-icon-144x144.png" %}',
    '{% static "pwa-icons/apple-icon-152x152.png" %}',
    '{% static "pwa-icons/apple-icon-180x180.png" %}',
    '{% static "pwa-icons/android-icon-192x192.png" %}',
    '{% static "pwa-icons/favicon-32x32.png" %}',
    '{% static "pwa-icons/favicon-96x96.png" %}',
    '{% static "pwa-icons/favicon-16x16.png" %}',

    // الملفات الخارجية الموجودة في base.html
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',

    // ملفات CSS و JS الخاصة بك (يرجى تعديل هذه المسارات)
    // '{% static "css/your-custom-styles.css" %}',
    // '{% static "js/your-custom-scripts.js" %}',

    // صورة الشعار الافتراضية
    'https://upload.wikimedia.org/wikipedia/commons/4/46/1000084215-removebg-preview.png',
];

self.addEventListener('install', function(event) {
    // تخطي مرحلة الانتظار حتى يمكن تفعيل Service Worker مباشرة
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('activate', function(event) {
    console.log('Service Worker activating...');
    // حذف أي كاش قديم
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', function(event) {
    // اعتراض طلبات الشبكة
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {
                // إذا تم العثور على استجابة في الكاش، قم بإرجاعها
                if (response) {
                    return response;
                }

                // إذا لم يتم العثور عليها، قم بطلبها من الشبكة
                return fetch(event.request).then(
                    function(response) {
                        // تأكد من أن الاستجابة صالحة
                        if(!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }

                        // قم بنسخ الاستجابة لأنها تيار ولا يمكن استخدامها مرتين
                        var responseToCache = response.clone();

                        // قم بتخزين الاستجابة في الكاش للمستقبل
                        caches.open(CACHE_NAME)
                            .then(function(cache) {
                                cache.put(event.request, responseToCache);
                            });

                        return response;
                    }
                );
            })
    );
});