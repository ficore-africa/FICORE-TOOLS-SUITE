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
// interactivity.js

document.addEventListener('DOMContentLoaded', () => {
    const journeyContainer = document.querySelector('.journey-container');
    const journeySteps = document.querySelectorAll('.journey-step');
    const totalSteps = journeySteps.length;

    // *** IMPORTANT: This needs to be dynamically set based on your actual user's progress. ***
    // For demonstration, let's assume it's stored in a data attribute on the journey container
    // or fetched from a backend/local storage.
    // Example: <div class="journey-container" data-current-step="1">...</div>
    let currentActiveStepIndex = parseInt(journeyContainer.dataset.currentStep || '0', 10);
    // Default to 0 if not set, or you can retrieve it from elsewhere

    function updateJourneyProgress(activeStepIndex) {
        journeySteps.forEach((step, index) => {
            step.classList.remove('active', 'completed'); // Clean slate

            if (index < activeStepIndex) {
                step.classList.add('completed');
            } else if (index === activeStepIndex) {
                step.classList.add('active');
            }
        });

        // Calculate progress for horizontal line (desktop)
        // These percentages need to be precise for your specific layout
        // They represent the center of each step.
        let desktopProgressPercentage = 0;
        if (activeStepIndex === 0) desktopProgressPercentage = 12.5; // Example: Halfway to step 1 center
        else if (activeStepIndex === 1) desktopProgressPercentage = 37.5;
        else if (activeStepIndex === 2) desktopProgressPercentage = 62.5;
        else if (activeStepIndex === 3) desktopProgressPercentage = 87.5;
        // You might need to adjust these percentages slightly for exact visual alignment

        // Calculate progress for vertical line (mobile)
        // This will depend on the height of each step + gap. You might need to measure.
        let mobileProgressPercentage = 0;
        if (activeStepIndex === 0) mobileProgressPercentage = 12.5;
        else if (activeStepIndex === 1) mobileProgressPercentage = 37.5;
        else if (activeStepIndex === 2) mobileProgressPercentage = 62.5;
        else if (activeStepIndex === 3) mobileProgressPercentage = 87.5;

        journeyContainer.style.setProperty('--journey-progress-width', `${desktopProgressPercentage}%`);
        journeyContainer.style.setProperty('--journey-progress-height', `${mobileProgressPercentage}%`);
    }

    // Initialize progress on load
    updateJourneyProgress(currentActiveStepIndex);

    // *** How to trigger updates: ***
    // If this journey is part of a user flow, you'll need a way to update
    // `currentActiveStepIndex` and call `updateJourneyProgress()`
    // For example, after a user completes a task or navigates to the next step.
    // This could be:
    // - A click event on a "Next Step" button
    // - A success callback from an API call
    // - Reading from local storage on page load (if the journey spans sessions)

    // Example: Add a click listener to the steps themselves for testing
    // journeySteps.forEach((step, index) => {
    //     step.addEventListener('click', () => {
    //         currentActiveStepIndex = index; // Set clicked step as active
    //         updateJourneyProgress(currentActiveStepIndex);
    //     });
    // });
});
