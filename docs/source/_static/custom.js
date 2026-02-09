document.addEventListener('DOMContentLoaded', function() {
    // Add version badge under sidebar brand text
    var brandText = document.querySelector('.sidebar-brand-text');
    if (brandText) {
        var badge = document.createElement('span');
        badge.className = 'sidebar-version-badge';
        if (typeof DOCUMENTATION_OPTIONS !== 'undefined' && DOCUMENTATION_OPTIONS.VERSION) {
            badge.textContent = 'v' + DOCUMENTATION_OPTIONS.VERSION;
            brandText.parentNode.insertBefore(badge, brandText.nextSibling);
        }
    }

    // Hide class prefix from method names in sidebar
    var methodLinks = document.querySelectorAll('li.toctree-l4 a code span.pre');
    methodLinks.forEach(function(span) {
        var fullText = span.textContent;
        var match = fullText.match(/\.([^.()]+\(\))/);
        if (match) {
            span.textContent = match[1];
        }
    });
});
