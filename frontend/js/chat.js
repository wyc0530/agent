/**
 * 聊天交互模块 - 集成文件上传、问答、下载功能
 */
var Chat = (function () {
  'use strict';

  var AGENT_ROLE_LABELS = {
    'auto': '自动识别', 'planner': '学习规划师', 'expert': '学习专家',
    'partner': '学习伙伴', 'quizzer': '出题官', 'reviewer': '复习助理',
    'examiner': '考试指导',
  };

  var _messagesEl = null;
  var _inputEl = null;
  var _sendBtn = null;
  var _attachBtn = null;
  var _fileInput = null;
  var _attachedFiles = null;
  var _streamingMsg = null;
  var _uploadedFiles = [];

  function $(id) { return document.getElementById(id); }

  function initChat() {
    _messagesEl = $('chat-messages');
    _inputEl = $('chat-input');
    _sendBtn = $('btn-send');
    _attachBtn = $('btn-attach');
    _fileInput = $('file-upload-input');
    _attachedFiles = $('attached-files');

    if (_sendBtn) { _sendBtn.addEventListener('click', sendMessage); }
    if (_inputEl) {
      _inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      });
      _inputEl.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      });
    }
    if (_attachBtn && _fileInput) {
      _attachBtn.addEventListener('click', function () { _fileInput.click(); });
      _fileInput.addEventListener('change', function () {
        if (_fileInput.files.length > 0) { handleFileUpload(_fileInput.files[0]); }
      });
    }
    renderHistory();
  }

  function handleFileUpload(file) {
    var allowedExts = ['.pdf', '.docx', '.doc', '.txt', '.md',
      '.py', '.java', '.cpp', '.c', '.h', '.js', '.ts',
      '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.csv'];
    // 处理无扩展名或只有扩展名的边界情况
    var nameParts = file.name.split('.');
    var ext = nameParts.length > 1 ? '.' + nameParts.pop().toLowerCase() : '';
    if (allowedExts.indexOf(ext) === -1) {
      Toast.show('不支持的文件格式: ' + ext + '，支持的格式: PDF, Word, TXT, 代码文件等', 'error');
      _resetFileInput();
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      Toast.show('文件大小超过限制 (最大 10MB)，当前文件: ' + (file.size / 1024 / 1024).toFixed(1) + 'MB', 'error');
      _resetFileInput();
      return;
    }

    if (_attachBtn) _attachBtn.classList.add('uploading');
    showUploadProgress(true);
    updateProgress(0, '上传中...');

    ApiClient.uploadFile(file, function (pct) {
      updateProgress(pct, '上传中 ' + pct + '%');
    }).then(function (data) {
      updateProgress(100, '完成');
      showUploadProgress(false);
      if (_attachBtn) _attachBtn.classList.remove('uploading');
      _uploadedFiles.push({ fileId: data.file_id, name: file.name, preview: data.content_preview });
      renderFileTags();
      _resetFileInput();
      Toast.show('文件上传成功: ' + file.name, 'success');
    }).catch(function (err) {
      showUploadProgress(false);
      if (_attachBtn) _attachBtn.classList.remove('uploading');
      _resetFileInput();
      var errMsg = err.message || '上传失败';
      if (err.status === 413) { errMsg = '文件过大，请选择小于 10MB 的文件'; }
      else if (err.status === 400) { errMsg = '文件格式不支持或文件为空'; }
      else if (err.status === 0) { errMsg = '网络连接失败，请检查服务器是否启动'; }
      Toast.show(errMsg, 'error');
    });
  }

  function _resetFileInput() {
    if (_fileInput) { _fileInput.value = ''; }
  }

  function showUploadProgress(show) {
    var el = $('upload-progress');
    if (el) el.classList.toggle('visible', show);
  }

  function updateProgress(pct, text) {
    var fill = document.querySelector('.progress-fill');
    var txt = document.querySelector('.progress-text');
    if (fill) fill.style.width = pct + '%';
    if (txt) txt.textContent = text || pct + '%';
  }

  function renderFileTags() {
    if (!_attachedFiles) return;
    _attachedFiles.innerHTML = '';
    _uploadedFiles.forEach(function (f, i) {
      var tag = document.createElement('span');
      tag.className = 'attached-file-tag';
      var nameSpan = document.createElement('span');
      nameSpan.className = 'tag-name';
      nameSpan.textContent = f.name;
      var removeBtn = document.createElement('button');
      removeBtn.className = 'tag-remove';
      removeBtn.innerHTML = '&#x2715;';
      removeBtn.title = '移除文件';
      (function (idx) {
        removeBtn.addEventListener('click', function () { removeFile(idx); });
      })(i);
      tag.appendChild(nameSpan);
      tag.appendChild(removeBtn);
      _attachedFiles.appendChild(tag);
    });
  }

  function removeFile(index) {
    _uploadedFiles.splice(index, 1);
    renderFileTags();
  }

  function renderHistory() {
    if (!_messagesEl) return;
    var messages = AppState.getMessages();
    if (messages.length === 0) { renderEmptyState(); return; }
    _messagesEl.innerHTML = '';
    messages.forEach(function (msg) { _messagesEl.appendChild(createMessageEl(msg)); });
    scrollToBottom(true);
  }

  function renderEmptyState() {
    if (!_messagesEl) return;
    _messagesEl.innerHTML =
      '<div class="empty-state" role="status">' +
      '<div class="icon"><svg width="48" height="48" viewBox="0 0 48 48" fill="none"><rect x="4" y="6" width="40" height="32" rx="4" stroke="currentColor" stroke-width="2.5"/><line x1="4" y1="14" x2="44" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="16" y1="6" x2="16" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="32" y1="6" x2="32" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="20" y1="22" x2="28" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="20" y1="28" x2="24" y2="28" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></div>' +
      '<h3>欢迎使用学习辅助系统</h3>' +
      '<p>我是你的 AI 学习助手，可以帮你：</p>' +
      '<ul>' +
      '<li>制定学习计划</li><li>推荐学习资料</li><li>解答学习问题</li><li>生成练习题目</li>' +
      '</ul>' +
      '<p style="margin-top:12px;font-size:0.875rem;color:var(--color-text-secondary)">在左侧边栏可以选择 Agent 来获得更专业的帮助。<br>点击输入框左侧的 📎 按钮上传文件，针对文件内容提问。</p>' +
      '</div>';
  }

  function createMessageEl(msg) {
    var role = msg.role || 'assistant';
    var avatar = msg.avatar || (role === 'user' ? 'U' : 'AI');
    var msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + role;

    var avatarEl = document.createElement('div');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = avatar;
    avatarEl.setAttribute('aria-label', role === 'user' ? '用户' : '助手');

    var bodyDiv = document.createElement('div');
    bodyDiv.className = 'message-body';

    var contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    contentEl.innerHTML = formatContent(msg.content || '');

    bodyDiv.appendChild(contentEl);

    if (msg.agent && role !== 'user') {
      var agentLabel = document.createElement('div');
      agentLabel.className = 'message-agent';
      agentLabel.textContent = '处理: ' + msg.agent;
      bodyDiv.appendChild(agentLabel);
    }

    // 用户消息的删除按钮
    if (role === 'user' && msg.id) {
      (function (msgId) {
        var actionsDiv = document.createElement('div');
        actionsDiv.className = 'message-actions';
        var delBtn = document.createElement('button');
        delBtn.className = 'btn-download-msg btn-delete-msg';
        delBtn.innerHTML = '&#x2715; 删除';
        delBtn.title = '删除此问答记录';
        delBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          if (confirm('确定要删除此问答记录吗？相应的 AI 回复也会被删除。')) {
            deleteMessagePair(msgId, msgDiv);
          }
        });
        actionsDiv.appendChild(delBtn);
        bodyDiv.appendChild(actionsDiv);
      })(msg.id);
    }

    if (role === 'assistant' && msg.content && msg.content.length > 0) {
      var actionsDiv = document.createElement('div');
      actionsDiv.className = 'message-actions';
      var downloadBtn = document.createElement('button');
      downloadBtn.className = 'btn-download-msg';
      downloadBtn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>' +
        '</svg> 下载 Word';
      downloadBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        downloadMessageAsWord(msg.content, msg.question || '');
      });
      actionsDiv.appendChild(downloadBtn);
      bodyDiv.appendChild(actionsDiv);
    }

    msgDiv.appendChild(avatarEl);
    msgDiv.appendChild(bodyDiv);
    return msgDiv;
  }

  function downloadMessageAsWord(content, question) {
    ApiClient.exportChatAnswer(question, content, '问答记录').then(function (data) {
      var url = ApiClient.getDownloadUrl(data.download_filename);
      var a = document.createElement('a');
      a.href = url;
      a.download = data.download_filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      Toast.show('文档下载成功', 'success');
    }).catch(function (err) {
      Toast.show('下载失败: ' + (err.message || '未知错误'), 'error');
    });
  }

  function deleteMessagePair(msgId, msgEl) {
    var convId = AppState.getConversationId();
    if (!convId) {
      Toast.show('无法删除：未关联对话', 'error');
      return;
    }
    ApiClient.deleteMessage(convId, msgId).then(function () {
      // 从 UI 移除用户消息及其后的 assistant 消息
      if (msgEl && msgEl.parentNode) {
        var nextEl = msgEl.nextElementSibling;
        msgEl.parentNode.removeChild(msgEl);
        // 移除紧随的 assistant 消息
        if (nextEl && nextEl.classList.contains('assistant')) {
          nextEl.parentNode.removeChild(nextEl);
        }
      }
      // 从 AppState 中移除对应消息
      var messages = AppState.getMessages();
      var filtered = [];
      var skipNext = false;
      for (var i = 0; i < messages.length; i++) {
        if (messages[i].id === msgId) {
          skipNext = true;
          continue;
        }
        if (skipNext && messages[i].role === 'assistant') {
          skipNext = false;
          continue;
        }
        filtered.push(messages[i]);
      }
      AppState.setMessages(filtered);
      // 如果对话变空，返回到空状态
      if (filtered.length === 0) {
        renderEmptyState();
        if (typeof Conversations !== 'undefined') {
          Conversations.loadConversations();
        }
      }
      Toast.show('问答记录已删除', 'success');
    }).catch(function (err) {
      Toast.show('删除失败: ' + (err.message || '未知错误'), 'error');
    });
  }

  function formatContent(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined' && marked.parse) {
      try { return marked.parse(text); }
      catch (e) { return escapeHtml(text).replace(/\n/g, '<br>'); }
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function sendMessage() {
    var message = (_inputEl ? _inputEl.value.trim() : '');
    if (!message && _uploadedFiles.length === 0) return;

    var hasFiles = _uploadedFiles.length > 0;
    var fileIds = _uploadedFiles.map(function (f) { return f.fileId; });
    var fileNames = _uploadedFiles.map(function (f) { return f.name; });

    if (_inputEl) {
      _inputEl.value = '';
      _inputEl.style.height = 'auto';
    }

    var convId = AppState.getConversationId();
    if (!convId && AppState.isLoggedIn()) {
      _sendWithNewConversation(message, hasFiles, fileIds, fileNames);
      return;
    }
    _doSendMessage(message, convId || '', hasFiles, fileIds, fileNames);
  }

  function _sendWithNewConversation(message, hasFiles, fileIds, fileNames) {
    ApiClient.createConversation('').then(function (data) {
      AppState.setConversationId(data.id);
      if (typeof Conversations !== 'undefined') { Conversations.loadConversations(); }
      _doSendMessage(message, data.id, hasFiles, fileIds, fileNames);
    }).catch(function () {
      _doSendMessage(message, '', hasFiles, fileIds, fileNames);
    });
  }

  function _doSendMessage(message, convId, hasFiles, fileIds, fileNames) {
    var displayText = message || '';
    if (hasFiles) {
      var filePrefix = '[已上传文件: ' + fileNames.join(', ') + ']';
      if (message) {
        displayText = message + '\n\n' + filePrefix;
      } else {
        displayText = filePrefix + ' 请分析这些文件的内容。';
      }
    }

    var userMsg = {
      role: 'user', content: displayText, avatar: 'U',
      timestamp: Date.now(), fileIds: hasFiles ? fileIds : null,
    };
    AppState.addMessage(userMsg);

    if (_messagesEl) {
      _messagesEl.appendChild(createMessageEl(userMsg));
      scrollToBottom(true);
    }

    _uploadedFiles = [];
    renderFileTags();

    var streamingDiv = document.createElement('div');
    streamingDiv.className = 'message assistant streaming';
    var avatarEl = document.createElement('div');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = 'AI';
    var bodyDiv = document.createElement('div');
    bodyDiv.className = 'message-body';
    var contentEl = document.createElement('div');
    contentEl.className = 'message-content streaming-waiting';
    contentEl.innerHTML = '正在等待助手响应... <span class="dot-pulse"></span>';
    bodyDiv.appendChild(contentEl);
    streamingDiv.appendChild(avatarEl);
    streamingDiv.appendChild(bodyDiv);

    if (_messagesEl) {
      _messagesEl.appendChild(streamingDiv);
      scrollToBottom(false);
    }

    _streamingMsg = {
      el: streamingDiv, contentEl: contentEl, bodyDiv: bodyDiv,
      fullText: '', agentRole: '', contentStarted: false,
    };

    if (hasFiles) {
      _handleFileQuestion(message, fileIds, fileNames, convId);
    } else {
      _handleChatQuestion(message, convId);
    }
  }

  function _handleFileQuestion(message, fileIds, fileNames, convId) {
    var question = message || '请分析文件内容并总结要点';
    ApiClient.askFileQuestion(fileIds[0], question, convId).then(function (data) {
      _streamingMsg.contentStarted = true;
      _streamingMsg.contentEl.classList.remove('streaming-waiting');
      _streamingMsg.fullText = data.answer;
      _streamingMsg.contentEl.innerHTML = formatContent(data.answer);
      finalizeMessage(null, question);
      scrollToBottom(true);
    }).catch(function (err) {
      _streamingMsg.contentEl.classList.remove('streaming-waiting');
      _streamingMsg.contentEl.innerHTML = '<span class="error-text">文件问答失败: ' + (err.message || '未知错误') + '</span>';
      finalizeMessage(err.message || '文件分析失败');
    });
  }

  function _handleChatQuestion(message, convId) {
    var history = AppState.getMessages().slice(0, -1).map(function (m) {
      return { role: m.role, content: m.content };
    });
    var agentRole = AppState.getCurrentAgent() || '';
    var payload = {
      message: message, user_id: AppState.getUserId(),
      conversation_id: convId, history: history.slice(-20),
    };
    if (agentRole && agentRole !== 'auto') { payload.agent_role = agentRole; }

    SSE.streamChat(payload, {
      onStart: function (data) { _streamingMsg.agentRole = data.agent_role || ''; },
      onChunk: function (chunk) {
        if (!_streamingMsg.contentStarted) {
          _streamingMsg.contentStarted = true;
          _streamingMsg.contentEl.classList.remove('streaming-waiting');
        }
        _streamingMsg.fullText += chunk;
        _streamingMsg.contentEl.innerHTML = formatContent(_streamingMsg.fullText);
        smartScrollToBottom(80);
      },
      onDone: function () { finalizeMessage(null, message); },
      onError: function (err) { finalizeMessage(err); },
    });
  }

  function finalizeMessage(errorMsg, question) {
    if (!_streamingMsg) return;
    _streamingMsg.el.classList.remove('streaming');

    if (errorMsg) {
      Toast.show(errorMsg, 'error');
      _streamingMsg.contentEl.textContent = '[错误] ' + errorMsg;
      AppState.addMessage({
        role: 'system', content: '[错误] ' + errorMsg, avatar: '!', timestamp: Date.now(),
      });
    } else {
      if (!_streamingMsg.fullText.trim()) {
        _streamingMsg.fullText = '[提示] 服务器响应超时，请稍后重试。';
        Toast.show(_streamingMsg.fullText, 'warning');
      }
      _streamingMsg.contentEl.innerHTML = formatContent(_streamingMsg.fullText);

      var agentLabel = _streamingMsg.agentRole
        ? AGENT_ROLE_LABELS[_streamingMsg.agentRole] || _streamingMsg.agentRole : '';

      var msgObj = {
        role: 'assistant', content: _streamingMsg.fullText, avatar: 'AI',
        agent: agentLabel, timestamp: Date.now(),
      };
      if (question) { msgObj.question = question; }
      AppState.addMessage(msgObj);

      if (_messagesEl) {
        var lastMsg = _messagesEl.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('assistant')) {
          _messagesEl.replaceChild(createMessageEl(msgObj), lastMsg);
        }
      }
    }
    _streamingMsg = null;
    if (typeof Conversations !== 'undefined') { Conversations.loadConversations(); }
    // 延迟刷新消息以获取数据库 ID，使删除按钮能立即显示
    _refreshMessagesWithIds();
  }

  /** 从服务端重新加载当前对话消息以获取数据库 ID */
  function _refreshMessagesWithIds() {
    var convId = AppState.getConversationId();
    if (!convId) return;
    setTimeout(function () {
      ApiClient.getConversationMessages(convId).then(function (data) {
        var msgs = (data.messages || []).map(function (m) {
          return {
            id: m.id, role: m.role, content: m.content,
            avatar: m.role === 'user' ? 'U' : 'AI',
            timestamp: Date.now(),
          };
        });
        if (msgs.length > 0) {
          AppState.setMessages(msgs);
          renderHistory();
        }
      }).catch(function () {
        // 静默失败，下次刷新时会自动恢复
      });
    }, 200); // 短暂延迟等待数据库写入完成
  }

  function scrollToBottom(instant) {
    if (!_messagesEl) return;
    _messagesEl.scrollTop = _messagesEl.scrollHeight;
  }

  function smartScrollToBottom(threshold) {
    if (!_messagesEl) return;
    var dist = _messagesEl.scrollHeight - _messagesEl.scrollTop - _messagesEl.clientHeight;
    if (dist < (threshold || 80)) {
      _messagesEl.scrollTop = _messagesEl.scrollHeight;
    }
  }

  function triggerQuickChat(message, agentRole) {
    AppState.setCurrentAgent(agentRole || '');
    if (typeof Sidebar !== 'undefined' && Sidebar.syncAgentSelector) {
      Sidebar.syncAgentSelector(agentRole);
    }
    if (_inputEl) {
      _inputEl.value = message;
      _inputEl.style.height = 'auto';
    }
    sendMessage();
  }

  return {
    initChat: initChat, renderHistory: renderHistory,
    sendMessage: sendMessage, triggerQuickChat: triggerQuickChat,
    AGENT_ROLE_LABELS: AGENT_ROLE_LABELS,
  };
})();