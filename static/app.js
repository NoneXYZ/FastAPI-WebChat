document.addEventListener('DOMContentLoaded', () => {
    const navSearch = document.getElementById('nav-search');
    const navPending = document.getElementById('nav-pending');
    const navMessages = document.getElementById('nav-messages');

    const searchView = document.getElementById('search-view');
    const pendingView = document.getElementById('pending-view');
    const messagesView = document.getElementById('messages-view');

    function setActiveTab(activeNav, activeView) {
        [navSearch, navPending, navMessages].forEach(nav => nav?.classList.remove('active'));
        [searchView, pendingView, messagesView].forEach(view => { if (view) view.style.display = 'none'; });

        if (activeNav) activeNav.classList.add('active');
        if (activeView) activeView.style.display = 'block';
    }

    if (navSearch) {
        navSearch.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveTab(navSearch, searchView);
        });
    }

    if (navPending) {
        navPending.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveTab(navPending, pendingView);
        });
    }

    if (navMessages) {
        navMessages.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveTab(navMessages, messagesView);
            if (window.loadMessagesInbox) {
                window.loadMessagesInbox();
            }
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/logout', {
                    method: 'POST',
                    credentials: 'same-origin'
                });

                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    console.warn(data.detail || 'Logout request failed.');
                }
            } catch (err) {
                console.warn('Logout request error:', err);
            } finally {
                document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
                window.location.href = '/login';
            }
        });
    }
});