document.addEventListener('DOMContentLoaded', () => {
    const navPending = document.getElementById('nav-pending');
    const pendingResults = document.getElementById('pending-results');

    window.loadPendingRequests = loadPendingRequests;

    if (navPending) {
        navPending.addEventListener('click', async () => {
            await loadPendingRequests();
        });
    }

    async function loadPendingRequests() {
        if (!pendingResults) return;

        try {
            const res = await fetch('/api/connections/pending');
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Failed to load requests.');

            pendingResults.innerHTML = '';

            if (!data.requests || data.requests.length === 0) {
                pendingResults.innerHTML = '<p class="placeholder-text">No pending requests.</p>';
                return;
            }

            data.requests.forEach(req => {
                const card = document.createElement('div');
                card.className = 'user-card';
                card.innerHTML = `
                    <span>@${req.username}</span>
                    <div>
                        <button class="message-btn accept-btn" style="background-color: #4CAF50; margin-right: 5px;">Accept</button>
                        <button class="message-btn decline-btn" style="background-color: #d32f2f;">Decline</button>
                    </div>
                `;

                card.querySelector('.accept-btn').addEventListener('click', () => acceptRequest(req.username));
                card.querySelector('.decline-btn').addEventListener('click', () => declineRequest(req.username));

                pendingResults.appendChild(card);
            });
        } catch (err) {
            console.error(err);
            pendingResults.innerHTML = '<p class="placeholder-text" style="color: #d32f2f;">Error loading requests.</p>';
        }
    }

    async function acceptRequest(username) {
        try {
            const res = await fetch(`/api/connections/${encodeURIComponent(username)}/accept`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            alert(`Connected with @${username}!`);
            await loadPendingRequests();
        } catch (err) {
            alert(err.message || 'Error accepting request.');
        }
    }

    async function declineRequest(username) {
        try {
            const res = await fetch(`/api/connections/${encodeURIComponent(username)}`, { method: 'DELETE' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            await loadPendingRequests();
        } catch (err) {
            alert(err.message || 'Error declining request.');
        }
    }
});