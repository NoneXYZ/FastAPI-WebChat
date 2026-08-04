document.addEventListener('DOMContentLoaded', () => {
    const messagesList = document.getElementById('messages-list');
    const chatBox = document.getElementById('chat-box');
    const chatHeader = document.getElementById('chat-header-username');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-message-btn');

    let activeChatUser = null;
    let socket = null;

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
            item.className = `chat-message ${msg.sender === activeChatUser ? 'incoming' : 'outgoing'}`;

            const sender = document.createElement('span');
            sender.className = 'sender';
            sender.textContent = msg.sender === activeChatUser ? msg.sender : 'You';

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
                    await loadChatHistory(contact.username);
                    bindSocket();
                    [...messagesList.querySelectorAll('.contact-item')].forEach(item => item.classList.remove('active'));
                    button.classList.add('active');
                });
                messagesList.appendChild(button);
            });

            if (!activeChatUser && contacts.length) {
                activeChatUser = contacts[0].username;
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

    function bindSocket() {
        if (!activeChatUser) return;

        if (socket) {
            try { socket.close(); } catch (e) {}
            socket = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${window.location.host}/ws/chat`;
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

                if (!payload.sender || !payload.content) return;

                const currentMessages = chatBox ? Array.from(chatBox.children).map(item => ({
                    sender: item.querySelector('.sender')?.textContent || '',
                    content: item.querySelector('div:last-child')?.textContent || ''
                })) : [];

                const normalized = currentMessages.filter(msg => msg.sender && msg.content);
                const senderName = payload.sender;
                const messageText = payload.content;

                if (!activeChatUser) return;

                if (senderName === activeChatUser || senderName === 'You') {
                    const isIncoming = senderName === activeChatUser;
                    const item = document.createElement('div');
                    item.className = `chat-message ${isIncoming ? 'incoming' : 'outgoing'}`;

                    const sender = document.createElement('span');
                    sender.className = 'sender';
                    sender.textContent = isIncoming ? senderName : 'You';

                    const content = document.createElement('div');
                    content.textContent = messageText;

                    item.appendChild(sender);
                    item.appendChild(content);
                    chatBox.appendChild(item);
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            } catch (err) {
                console.error('Chat message parse failed:', err);
            }
        });

        socket.addEventListener('close', () => {
            console.log('WebSocket closed');
        });
    }

    function sendCurrentMessage() {
        if (!activeChatUser || !messageInput || !socket) return;

        const text = messageInput.value.trim();
        if (!text) return;

        const payload = {
            receiver: activeChatUser,
            content: text
        };

        socket.send(JSON.stringify(payload));
        messageInput.value = '';

        const item = document.createElement('div');
        item.className = 'chat-message outgoing';

        const sender = document.createElement('span');
        sender.className = 'sender';
        sender.textContent = 'You';

        const content = document.createElement('div');
        content.textContent = text;

        item.appendChild(sender);
        item.appendChild(content);
        if (chatBox) {
            chatBox.appendChild(item);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', sendCurrentMessage);
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
