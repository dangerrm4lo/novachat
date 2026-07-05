// app.js — NovaChat v4.3
(function() {
    'use strict';

    // ===== ПРОВЕРКА АВТОРИЗАЦИИ =====
    const userId = localStorage.getItem('nova-user-id');
    if (!userId) {
        window.location.href = '/login.html';
        return;
    }

    const state = {
        userId: userId,
        currentChat: null,
        isDark: localStorage.getItem('nova-theme') === 'dark',
        ws: null
    };

    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    const dom = {
        chatList: $('#chatList'),
        messages: $('#messages'),
        msgInput: $('#msgInput'),
        sendBtn: $('#sendBtn'),
        backBtn: $('#backBtn'),
        chatName: $('#chatName'),
        chatStatus: $('#chatStatus'),
        themeToggle: $('#themeToggle'),
        themeIcon: $('#themeIcon'),
        searchInput: $('#searchInput'),
        toast: $('#toast'),
        toastMessage: $('#toastMessage'),
        dialogUserInfo: $('#dialogUserInfo'),
        settingsToggle: $('#settingsToggle'),
        changelogToggle: $('#changelogToggle'),
        logoutBtn: $('#logoutBtn')
    };

    // ===== ВЫХОД =====
    function logout() {
        localStorage.removeItem('nova-user-id');
        localStorage.removeItem('nova-token');
        window.location.href = '/login.html';
    }

    if (dom.logoutBtn) {
        dom.logoutBtn.addEventListener('click', logout);
    }

    // ===== API =====
    function getApiBase() {
        if (window.location.protocol === 'file:') return 'http://localhost:8000';
        const host = window.location.hostname;
        if (host === 'localhost' || host === '127.0.0.1' || host === '') return 'http://localhost:8000';
        return `http://${host}:8000`;
    }

    const API_BASE = getApiBase();

    async function apiFetch(endpoint, options = {}) {
        const url = `${API_BASE}/api${endpoint}`;
        const response = await fetch(url, {
            ...options,
            headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
        });
        if (!response.ok) {
            let msg = `HTTP ${response.status}`;
            try { const err = await response.json(); msg = err.detail || msg; } catch {}
            throw new Error(msg);
        }
        return response.json();
    }

    // ===== THEME =====
    function setTheme(dark) {
        state.isDark = dark;
        document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
        dom.themeIcon.innerHTML = dark
            ? '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
            : '<path d="M12 3a6 6 0 0 0 9 9 6 6 0 1 1-9-9"/>';
        localStorage.setItem('nova-theme', dark ? 'dark' : 'light');
    }
    setTheme(state.isDark);
    dom.themeToggle.addEventListener('click', () => setTheme(!state.isDark));

    // ===== TOAST =====
    let toastTimer;

    function showToast(message, type = 'info', duration = 2500) {
        const toast = dom.toast;
        const msg = dom.toastMessage;
        toast.className = 'toast ' + type;
        msg.textContent = message;
        clearTimeout(toastTimer);
        void toast.offsetWidth;
        toast.classList.add('show');
        toastTimer = setTimeout(() => toast.classList.remove('show'), duration);
    }

    // ===== CHANGELOG =====
    dom.changelogToggle?.addEventListener('click', () => {
        showToast('📋 Changelog v4.3\n• Новый стиль чата\n• Группировка сообщений\n• Цветные имена\n• Регистрация и вход', 'info', 4000);
    });

    // ===== SETTINGS =====
    dom.settingsToggle?.addEventListener('click', () => {
        showToast('⚙️ Настройки будут доступны в следующем обновлении', 'info', 3000);
    });

    // ===== SEARCH =====
    dom.searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        const items = document.querySelectorAll('.chat-item');
        items.forEach(item => {
            const name = item.querySelector('.name')?.textContent?.toLowerCase() || '';
            const lastMsg = item.querySelector('.last-msg')?.textContent?.toLowerCase() || '';
            const match = name.includes(query) || lastMsg.includes(query);
            item.style.display = match || !query ? 'flex' : 'none';
        });
    });

    // ===== CHAT SELECTION =====
    function selectChat(item) {
        const name = item.querySelector('.name').textContent;
        const avatarText = item.querySelector('.avatar').textContent.trim();
        const bg = item.querySelector('.avatar').style.background;
        const statusDot = item.querySelector('.status-dot');
        const statusText = statusDot ? statusDot.className.replace('status-dot ', '') : 'online';
        const statusMap = { online: 'В сети', away: 'Отошёл', busy: 'Занят', offline: 'Не в сети' };

        state.currentChat = item.dataset.chat;
        dom.chatName.textContent = name;
        dom.chatStatus.textContent = statusMap[statusText] || 'В сети';
        dom.chatStatus.className = 'dialog-status ' + statusText;
        dom.dialogUserInfo.querySelector('.dialog-avatar').textContent = avatarText;
        dom.dialogUserInfo.querySelector('.dialog-avatar').style.background = bg;

        messageGroup = [];
        dom.messages.innerHTML = '<div class="date-divider">Сегодня</div>';
        loadChatHistory(state.currentChat);

        $$('.chat-item').forEach(c => c.classList.remove('active'));
        item.classList.add('active');

        if (window.innerWidth <= 640) dom.chatList.classList.remove('active');

        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'join', chat_id: state.currentChat }));
        }
    }

    $$('.chat-item').forEach(item => {
        item.addEventListener('click', () => selectChat(item));
    });

    dom.backBtn.addEventListener('click', () => dom.chatList.classList.add('active'));

    // ===== ГРУППИРОВКА СООБЩЕНИЙ =====
    let messageGroup = [];

    function renderMessages() {
        if (messageGroup.length === 0) return;
        
        const divider = dom.messages.querySelector('.date-divider');
        dom.messages.innerHTML = '';
        if (divider) dom.messages.appendChild(divider);
        
        let i = 0;
        while (i < messageGroup.length) {
            const current = messageGroup[i];
            const next = messageGroup[i + 1];
            const prev = messageGroup[i - 1];
            
            const isFirstInGroup = !prev || prev.sender !== current.sender;
            const isLastInGroup = !next || next.sender !== current.sender;
            
            let groupClass = 'single';
            if (!isFirstInGroup && !isLastInGroup) groupClass = 'middle';
            else if (isFirstInGroup && !isLastInGroup) groupClass = 'first';
            else if (!isFirstInGroup && isLastInGroup) groupClass = 'last';
            
            const wrapper = document.createElement('div');
            wrapper.className = `message-wrapper ${current.isSelf ? 'self' : 'other'} ${groupClass}`;
            
            let senderHtml = '';
            if (!current.isSelf && isFirstInGroup && current.senderName) {
                senderHtml = `
                    <div class="message-sender">
                        <span class="sender-name" style="color:${current.senderColor}">${escapeHtml(current.senderName)}</span>
                    </div>
                `;
            }
            
            wrapper.innerHTML = `
                ${senderHtml}
                <div class="message ${current.isSelf ? 'self' : 'other'}">
                    <div class="content">${escapeHtml(current.text)}</div>
                </div>
                <div class="message-time">${current.time} ${current.isSelf ? '✓' : ''}</div>
            `;
            
            dom.messages.appendChild(wrapper);
            i++;
        }
        
        dom.messages.scrollTop = dom.messages.scrollHeight;
    }

    function addMessage(text, isSelf = true, senderName = '', senderColor = '') {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const sender = isSelf ? 'self' : (senderName || 'other');
        
        const colors = ['#ff6b6b', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00', '#ff6b6b'];
        const color = senderColor || colors[Math.floor(Math.random() * colors.length)];
        
        messageGroup.push({
            text,
            isSelf,
            senderName: isSelf ? '' : senderName,
            senderColor: color,
            time,
            sender
        });
        
        renderMessages();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ===== LOAD HISTORY =====
    async function loadChatHistory(chatId) {
        try {
            const data = await apiFetch(`/messages/${chatId}?limit=50`);
            messageGroup = [];
            const reversed = data.reverse();
            for (const msg of reversed) {
                const isSelf = msg.sender_id === state.userId;
                const senderName = msg.full_name || msg.username || 'Пользователь';
                const colors = ['#ff6b6b', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00'];
                const color = colors[Math.floor(Math.random() * colors.length)];
                const time = new Date(msg.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                messageGroup.push({
                    text: msg.content,
                    isSelf: isSelf,
                    senderName: isSelf ? '' : senderName,
                    senderColor: color,
                    time: time,
                    sender: isSelf ? 'self' : senderName
                });
            }
            renderMessages();
        } catch (e) {
            console.warn('Load history error:', e);
        }
    }

    // ===== SEND =====
    function sendMessage() {
        const text = dom.msgInput.value.trim();
        if (!text) return;
        
        addMessage(text, true, '', '');
        dom.msgInput.value = '';
        dom.sendBtn.disabled = true;

        if (state.ws && state.ws.readyState === WebSocket.OPEN && state.currentChat) {
            state.ws.send(JSON.stringify({
                type: 'message',
                to: state.currentChat,
                content: text
            }));
        }

        setTimeout(() => { dom.sendBtn.disabled = false; }, 400);
    }

    dom.sendBtn.addEventListener('click', sendMessage);
    dom.msgInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // ===== WEBSOCKET =====
    function connectWS() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname || 'localhost';
        const port = window.location.port || '8000';
        const wsUrl = `${protocol}//${host}:${port}/ws/${state.userId}`;
        state.ws = new WebSocket(wsUrl);
        state.ws.onopen = () => {
            console.log('[WS] Connected');
            state.ws.send(JSON.stringify({ type: 'auth', userId: state.userId }));
        };
        state.ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'message') {
                    const isSelf = data.from === state.userId;
                    const senderName = data.username || data.from || 'Пользователь';
                    const colors = ['#ff6b6b', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00'];
                    const color = colors[Math.floor(Math.random() * colors.length)];
                    addMessage(data.content, isSelf, senderName, color);
                } else if (data.type === 'history') {
                    messageGroup = [];
                    for (const msg of data.messages) {
                        const isSelf = msg.from === state.userId;
                        const senderName = msg.username || msg.from || 'Пользователь';
                        const colors = ['#ff6b6b', '#34c759', '#ff9500', '#af52de', '#ff2d55', '#5ac8fa', '#ffcc00'];
                        const color = colors[Math.floor(Math.random() * colors.length)];
                        const time = new Date(msg.timestamp || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        messageGroup.push({
                            text: msg.content,
                            isSelf: isSelf,
                            senderName: isSelf ? '' : senderName,
                            senderColor: color,
                            time: time,
                            sender: isSelf ? 'self' : senderName
                        });
                    }
                    renderMessages();
                }
            } catch (e) {
                console.warn('WS parse error:', e);
            }
        };
        state.ws.onclose = () => {
            console.log('[WS] Disconnected');
            setTimeout(connectWS, 2000);
        };
    }

    // ===== SUPPORT CHAT =====
    async function createSupportChat() {
        try {
            const result = await apiFetch(`/system/create-support-chat/${state.userId}`, { method: 'POST' });
            if (result.status === 'success') {
                const exists = document.querySelector(`.chat-item[data-chat="${result.chat_id}"]`);
                if (!exists) {
                    const item = document.createElement('div');
                    item.className = 'chat-item';
                    item.dataset.chat = result.chat_id;
                    item.innerHTML = `
                        <div class="avatar" style="background:#ff6b6b;">★<span class="status-dot online"></span></div>
                        <div class="info"><div class="name">Поддержка NovaChat</div><div class="last-msg">Напишите ваш вопрос...</div></div>
                        <div class="meta"><span class="time">сейчас</span></div>
                    `;
                    const header = dom.chatList.querySelector('.chat-list-header');
                    if (header) header.after(item);
                    else dom.chatList.prepend(item);
                    item.addEventListener('click', () => selectChat(item));
                }
                return result.chat_id;
            }
        } catch (e) {
            console.error('Support chat error:', e);
            showToast('❌ Ошибка создания чата поддержки', 'error', 3000);
        }
        return null;
    }

    // ===== INIT =====
    if (window.innerWidth <= 640) dom.chatList.classList.add('active');
    connectWS();

    setTimeout(async () => {
        const chatId = await createSupportChat();
        if (chatId) {
            const items = document.querySelectorAll('.chat-item');
            for (const item of items) {
                if (item.dataset.chat === chatId) {
                    selectChat(item);
                    break;
                }
            }
        }
    }, 800);

    showToast('Добро пожаловать в NovaChat', 'info', 2500);
    console.log('[NovaChat] v4.3, user:', state.userId);

})();