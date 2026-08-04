document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('user-search-input');
    const searchResultsContainer = document.getElementById('search-results');

    if (!searchInput) return;

    searchInput.addEventListener('input', async (e) => {
        const query = e.target.value.trim();
        if (!query) {
            searchResultsContainer.innerHTML = '<p class="placeholder-text">Type a username above to search.</p>';
            return;
        }

        try {
            const res = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            searchResultsContainer.innerHTML = '';

            if (!data.results || data.results.length === 0) {
                searchResultsContainer.innerHTML = '<p class="placeholder-text">No users found.</p>';
                return;
            }

            for (const user of data.results) {
                const card = document.createElement('div');
                card.className = 'user-card';

                const statusRes = await fetch(`/api/connections/status/${encodeURIComponent(user.username)}`);
                const statusData = await statusRes.json();

                const actionBtn = createActionButton(user.username, statusData.status);

                const usernameLink = document.createElement('a');
                usernameLink.href = `/profile/${encodeURIComponent(user.username)}`;
                usernameLink.className = 'user-link';
                usernameLink.textContent = `@${user.username}`;

                card.appendChild(usernameLink);
                card.appendChild(actionBtn);
                searchResultsContainer.appendChild(card);
            }
        } catch (err) {
            console.error('Search error:', err);
            searchResultsContainer.innerHTML = '<p class="placeholder-text">Search failed.</p>';
        }
    });

    function createActionButton(username, status) {
        const btn = document.createElement('button');
        btn.className = 'message-btn';

        if (status === 'accepted') {
            btn.textContent = 'Connected ✓';
            btn.style.backgroundColor = '#333';
            btn.disabled = true;
        } else if (status === 'pending_outgoing') {
            btn.textContent = 'Pending...';
            btn.style.backgroundColor = '#666';
            btn.onclick = () => removeConnection(username, btn);
        } else if (status === 'pending_incoming') {
            btn.textContent = 'Accept Request';
            btn.style.backgroundColor = '#4CAF50';
            btn.onclick = () => acceptConnection(username, btn);
        } else {
            btn.textContent = 'Connect';
            btn.style.backgroundColor = '#4CAF50';
            btn.onclick = () => sendConnection(username, btn);
        }

        return btn;
    }

async function sendConnection(username, btn) {
        try {
            const res = await fetch(`/api/connections/${encodeURIComponent(username)}`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            if (data.status === 'accepted') {
                btn.textContent = 'Connected ✓';
                btn.style.backgroundColor = '#333';
                btn.disabled = true;
            } else {
                btn.textContent = 'Pending...';
                btn.style.backgroundColor = '#666';
                
                btn.onclick = () => removeConnection(username, btn);
            }
        } catch (err) {
            alert(err.message || 'Failed to send request.');
        }
    }
    
    async function acceptConnection(username, btn) {
        try {
            const res = await fetch(`/api/connections/${encodeURIComponent(username)}/accept`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            btn.textContent = 'Connected ✓';
            btn.style.backgroundColor = '#333';
            btn.disabled = true;
        } catch (err) {
            alert(err.message || 'Failed to accept request.');
        }
    }

    async function removeConnection(username, btn) {
        try {
            const res = await fetch(`/api/connections/${encodeURIComponent(username)}`, { method: 'DELETE' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail);

            btn.textContent = 'Connect';
            btn.style.backgroundColor = '#4CAF50';
            
            btn.onclick = () => sendConnection(username, btn);
        } catch (err) {
            alert(err.message || 'Failed to cancel request.');
        }
    }
});
