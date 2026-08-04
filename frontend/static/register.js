const USERNAME_REGEX = /^[a-zA-Z0-9_-]{3,20}$/;
const PASSWORD_REGEX = /^.{8,64}$/;

function validateForm(username, password, confirmPassword) {
    const errorDisplay = document.getElementById("responseMessage");

    if (!USERNAME_REGEX.test(username)) {
        errorDisplay.style.color = "#f44336";
        errorDisplay.textContent = "Username must be 3-20 characters (letters, numbers, _ or - only).";
        return false;
    }

    if (!PASSWORD_REGEX.test(password)) {
        errorDisplay.style.color = "#f44336";
        errorDisplay.textContent = "Password must be 8+ chars.";
        return false;
    }

    if (password !== confirmPassword) {
        errorDisplay.style.color = "#f44336";
        errorDisplay.textContent = "Passwords do not match.";
        return false;
    }

    return true;
}

document.addEventListener("DOMContentLoaded", () => {
    const registerForm = document.getElementById("registerForm");

    if (registerForm) {
        registerForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const username = document.getElementById("username").value.trim().toLowerCase();
            const password = document.getElementById("password").value;
            const confirmPassword = document.getElementById("confirm_password").value;

            if (!validateForm(username, password, confirmPassword)) {
                return; // Stop execution if invalid
            }

            try {
                const response = await fetch("/api/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();
                const errorDisplay = document.getElementById("responseMessage");

                if (!response.ok) {
                    errorDisplay.style.color = "#f44336";
                    errorDisplay.textContent = data.detail[0]?.msg || data.detail || "Registration failed.";
                } else {
                    errorDisplay.style.color = "#4CAF50";
                    errorDisplay.textContent = "Account created! Redirecting...";
                    setTimeout(() => window.location.href = "/login", 1500);
                }
            } catch (error) {
                const errorDisplay = document.getElementById("responseMessage");
                errorDisplay.style.color = "#f44336";
                errorDisplay.textContent = "A network error occurred.";
            }
        });
    }
});
