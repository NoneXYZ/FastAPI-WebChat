document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById('loginForm');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const username = document.getElementById('username').value.trim().toLowerCase();
            const password = document.getElementById('password').value;
            const responseMessage = document.getElementById('responseMessage');

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();

                if (response.ok) {
                    responseMessage.style.color = '#4CAF50';
                    responseMessage.innerText = data.message || "Login successful! Redirecting...";

                    setTimeout(() => {
                        window.location.href = "/";
                    }, 1000);
                } else {
                    responseMessage.style.color = '#ff5252';
                    responseMessage.innerText = data.detail || "Login failed.";
                }
            } catch (error) {
                responseMessage.style.color = '#ff5252';
                responseMessage.innerText = "A network error occurred.";
            }
        });
    }
});
