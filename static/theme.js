// Theme: dark (default) or light, persisted in localStorage, respects system preference
(function() {
    var saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.classList.add('light');
    } else if (!saved && window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.documentElement.classList.add('light');
    }
})();

function toggleTheme() {
    var html = document.documentElement;
    if (html.classList.contains('light')) {
        html.classList.remove('light');
        localStorage.setItem('theme', 'dark');
    } else {
        html.classList.add('light');
        localStorage.setItem('theme', 'light');
    }
}
