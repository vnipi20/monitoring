// Базовий Service Worker для підтримки PWA
self.addEventListener('install', (e) => {
    console.log('[Service Worker] Встановлено');
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    console.log('[Service Worker] Активовано');
});

// Обов'язковий обробник для сучасного Chrome
self.addEventListener('fetch', (e) => {
    // Поки що просто пропускаємо всі запити через інтернет
    e.respondWith(fetch(e.request));
});