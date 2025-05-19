document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.form');
    const coverLetter = document.querySelector('.cover-letter');
    const modal = document.getElementById('previewModal');
    const closeBtn = document.querySelector('.close');
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const body = document.body;

    if (coverLetter) {
        coverLetter.classList.add('fade-in');
    }

    form.addEventListener('submit', () => {
        form.classList.add('loading');
    });

    document.querySelector('.form').addEventListener('submit', (event) => {
        const emailField = document.getElementById('email');
        if (!emailField.value.trim()) {
            alert('Please provide your email address.');
            event.preventDefault(); // Prevent form submission
        }
    });

    document.querySelector('.btn.preview-btn').addEventListener('click', () => {
        modal.style.display = 'block';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    document.getElementById('sample-job-desc').addEventListener('change', (event) => {
        document.getElementById('job_description').value = event.target.value;
    });

    // Check if dark mode is already enabled in localStorage
    if (localStorage.getItem('darkMode') === 'enabled') {
        body.classList.add('dark-mode');
    }

    // Toggle dark mode on button click
    darkModeToggle.addEventListener('click', () => {
        body.classList.toggle('dark-mode');

        // Save the dark mode state in localStorage
        if (body.classList.contains('dark-mode')) {
            localStorage.setItem('darkMode', 'enabled');
        } else {
            localStorage.setItem('darkMode', 'disabled');
        }
    });

    const feedbackBtn = document.getElementById('feedback-btn');
    const feedbackModal = document.getElementById('feedback-modal');
    const feedbackContent = document.getElementById('feedback-content');

    // Open the modal and fetch feedback when the button is clicked
    feedbackBtn.addEventListener('click', () => {
        feedbackModal.style.display = 'block';
        feedbackContent.textContent = 'Loading feedback...';

        // Send an AJAX request to fetch AI feedback
        fetch('/get_feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ cover_letter: feedbackBtn.dataset.coverLetter }),
        })
            .then((response) => response.json())
            .then((data) => {
                feedbackContent.textContent = data.feedback;
            })
            .catch((error) => {
                feedbackContent.textContent = 'Error fetching feedback. Please try again.';
                console.error('Error:', error);
            });
    });

    // Close the modal when the close button is clicked
    closeBtn.addEventListener('click', () => {
        feedbackModal.style.display = 'none';
    });

    // Close the modal when clicking outside the modal content
    window.addEventListener('click', (event) => {
        if (event.target === feedbackModal) {
            feedbackModal.style.display = 'none';
        }
    });
});