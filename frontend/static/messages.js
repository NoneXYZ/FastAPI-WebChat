document.addEventListener('DOMContentLoaded', () => {
    const messagesList = document.getElementById('messages-list');
    const chatBox = document.getElementById('chat-box');
    const chatHeader = document.getElementById('chat-header-username');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-message-btn');

    let activeChatUser = null;
    let activeChatUserId = null;
    let currentUserId = null;
    let socket = null;
    const sentClientMessageIds = new Set();

    function getCurrentUsername() {
        return document.getElementById('username-display')?.textContent?.trim() || '';
    }

    async function resolveUserByUsername(username) {
        if (!username) return null;

        try {
            const res = await fetch(`/api/users/search?q=${encodeURIComponent(username)}`);
            const data = await res.json();
            if (!res.ok) return null;

            const match = (data.results || []).find(user => user.username === username);
            return match || null;
        } catch (err) {
            console.warn('User lookup failed:', err);
            return null;
        }
    }

    async function ensureUserIds() {
        const currentUsername = getCurrentUsername();
        if (!currentUsername) return;

        const currentUser = await resolveUserByUsername(currentUsername);
        currentUserId = currentUser?.id ?? null;

        if (activeChatUser) {
            const targetUser = await resolveUserByUsername(activeChatUser);
            activeChatUserId = targetUser?.id ?? null;
        }
    }

    function setChatHeader(username) {
        if (chatHeader) {
            chatHeader.textContent = username ? `Chat with @${username}` : 'Select a contact';
        }
    }

    function renderChatMessages(messages) {
        if (!chatBox) return;
        chatBox.innerHTML = '';

        if (!messages || messages.length === 0) {
            chatBox.innerHTML = '<p class="placeholder-text">No messages yet. Say hi.</p>';
            return;
        }

        messages.forEach(msg => {
            const item = document.createElement('div');
            const senderName = msg.sender || 'You';
            const isOutgoing = senderName === 'You' || senderName === getCurrentUsername();
            item.className = `chat-message ${isOutgoing ? 'outgoing' : 'incoming'}`;

            const sender = document.createElement('span');
            sender.className = 'sender';
            sender.textContent = isOutgoing ? 'You' : senderName;

            const content = document.createElement('div');
            content.textContent = msg.content;

            item.appendChild(sender);
            item.appendChild(content);
            chatBox.appendChild(item);
        });

        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function loadMessagesInbox() {
        if (!messagesList) return;

        try {
            const res = await fetch('/api/connections/inbox');
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to load inbox');

            const contacts = data.inbox || [];
            messagesList.innerHTML = '';

            if (!contacts.length) {
                messagesList.innerHTML = '<p class="placeholder-text">No accepted connections yet.</p>';
                if (chatBox) {
                    chatBox.innerHTML = '<p class="placeholder-text">Connect with someone first.</p>';
                }
                setChatHeader(null);
                activeChatUser = null;
                activeChatUserId = null;
                return;
            }

            contacts.forEach(contact => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'contact-item';
                if (activeChatUser === contact.username) {
                    button.classList.add('active');
                }

                const nameLink = document.createElement('a');
                nameLink.href = `/profile/${encodeURIComponent(contact.username)}`;
                nameLink.className = 'user-link';
                nameLink.textContent = `@${contact.username}`;

                const preview = document.createElement('small');
                preview.textContent = contact.last_message ? contact.last_message : 'Start a conversation';

                button.appendChild(nameLink);
                button.appendChild(preview);
                button.addEventListener('click', async (event) => {
                    if (event.target.closest('a')) {
                        return;
                    }
                    activeChatUser = contact.username;
                    await ensureUserIds();
                    await loadChatHistory(contact.username);
                    bindSocket();
                    [...messagesList.querySelectorAll('.contact-item')].forEach(item => item.classList.remove('active'));
                    button.classList.add('active');
                });
                messagesList.appendChild(button);
            });

            if (!activeChatUser && contacts.length) {
                activeChatUser = contacts[0].username;
                await ensureUserIds();
                await loadChatHistory(activeChatUser);
                bindSocket();
                const firstContactButton = messagesList.querySelector('.contact-item');
                if (firstContactButton) firstContactButton.classList.add('active');
            }
        } catch (err) {
            console.error(err);
            messagesList.innerHTML = '<p class="placeholder-text">Could not load your messages.</p>';
        }
    }

    async function loadChatHistory(username) {
        setChatHeader(username);
        if (!chatBox) return;

        try {
            const res = await fetch(`/api/messages/${encodeURIComponent(username)}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to load chat history');
            renderChatMessages(data.messages || []);
        } catch (err) {
            console.error(err);
            chatBox.innerHTML = '<p class="placeholder-text">Unable to load messages.</p>';
        }
    }

    function appendChatBubble({ senderName, messageText, isOutgoing, clientMsgId = null }) {
        if (!chatBox) return;

        const existingMessage = [...chatBox.children].some(item => {
            const senderText = item.querySelector('.sender')?.textContent || '';
            const contentText = item.querySelector('div:last-child')?.textContent || '';
            const itemClientMsgId = item.dataset.clientMsgId;
            return (clientMsgId && itemClientMsgId === clientMsgId)
                || (senderText === senderName && contentText === messageText && !clientMsgId);
        });

        if (existingMessage) return;

        const item = document.createElement('div');
        item.className = `chat-message ${isOutgoing ? 'outgoing' : 'incoming'}`;
        if (clientMsgId) {
            item.dataset.clientMsgId = clientMsgId;
        }

        const sender = document.createElement('span');
        sender.className = 'sender';
        sender.textContent = isOutgoing ? 'You' : senderName;

        const content = document.createElement('div');
        content.textContent = messageText;

        item.appendChild(sender);
        item.appendChild(content);
        chatBox.appendChild(item);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function bindSocket() {
        if (!activeChatUser) return;

        if (socket) {
            try { socket.close(); } catch (e) {}
            socket = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${window.location.host}/api/ws/chat`;
        socket = new WebSocket(wsUrl);

        socket.addEventListener('open', () => {
            console.log('WebSocket connected');
        });

        socket.addEventListener('message', (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.error) {
                    alert(payload.error);
                    return;
                }

                const messageText = payload.content || payload.message || '';
                if (!messageText && payload.content !== '') return;

                const senderName = payload.sender || activeChatUser || 'Unknown';
                const isOutgoing = payload.sender_id ? Number(payload.sender_id) !== Number(activeChatUserId) : false;
                const clientMsgId = payload.client_msg_id || null;

                if (clientMsgId && sentClientMessageIds.has(clientMsgId)) {
                    sentClientMessageIds.delete(clientMsgId);
                    return;
                }

                appendChatBubble({
                    senderName,
                    messageText,
                    isOutgoing,
                    clientMsgId
                });
            } catch (err) {
                console.error('Chat message parse failed:', err);
            }
        });

        socket.addEventListener('close', () => {
            console.log('WebSocket closed');
        });
    }

    async function sendCurrentMessage() {
        if (!activeChatUser || !messageInput || !socket) return;

        const text = messageInput.value.trim();
        if (!text) return;

        await ensureUserIds();

        if (!activeChatUserId) {
            console.warn('Could not resolve target user id for websocket chat.');
            return;
        }

        const clientMsgId = crypto.randomUUID();
        sentClientMessageIds.add(clientMsgId);

        const payload = {
            receiver_id: activeChatUserId,
            content: text,
            client_msg_id: clientMsgId
        };

        socket.send(JSON.stringify(payload));
        messageInput.value = '';

        appendChatBubble({
            senderName: getCurrentUsername() || 'You',
            messageText: text,
            isOutgoing: true,
            clientMsgId
        });
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', () => sendCurrentMessage());
    }

    if (messageInput) {
        messageInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                sendCurrentMessage();
            }
        });
    }

    window.loadMessagesInbox = loadMessagesInbox;
    loadMessagesInbox();
});
