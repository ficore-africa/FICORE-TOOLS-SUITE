document.addEventListener('DOMContentLoaded', function() {
    const toolsLink = document.getElementById('toolsLink');
    if (toolsLink) {
        toolsLink.addEventListener('click', function(event) {
            event.preventDefault();
            const toolsSection = document.getElementById('tools-section');
            if (toolsSection) {
                toolsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                // Fallback: redirect to index if not on index.html
                window.location.href = '/';
            }
        });
    }
});
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        if (message.textContent.includes('successfully')) {
            const duration = 5 * 1000;
            const end = Date.now() + duration;
            const colors = ['#ff0a54', '#ff477e', '#ff7096', '#ff85a1', '#fbb1bd', '#f9bec7'];

            (function frame() {
                confetti({
                    particleCount: 7,
                    angle: 60,
                    spread: 70,
                    origin: { x: 0 },
                    colors: colors
                });
                confetti({
                    particleCount: 7,
                    angle: 120,
                    spread: 70,
                    origin: { x: 1 },
                    colors: colors
                });

                if (Date.now() < end) {
                    requestAnimationFrame(frame);
                }
            })();
        }
    });
});
