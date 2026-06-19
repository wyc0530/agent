/**
 * 聊天交互模块
 * 消息渲染、流式对话、输入处理
 */
var Chat = (function () {
  'use strict';

  var AGENT_ROLE_LABELS = {
    'auto': '自动识别',
    'planner': '学习规划师',
    'expert': '学习专家',
    'partner': '学习伙伴',
    'quizzer': '出题官',
    'reviewer': '复习助理',
    'examiner': '考试指导',
  };

  var AVATAR_USER = 'U';       // 用户首字母
  var AVATAR_ASSISTANT = 'AI';  // 助手标识
  var AVATAR_SYSTEM = '!';      // 系统标识

  var _messagesEl = null;
  var _inputEl = null;
  var _sendBtn = null;
  var _streamingMsg = null;

  /** 初始化聊天界面 */
  function initChat() {
    _messagesEl = Utils.$('#chat-messages');
    _inputEl = Utils.$('#chat-input');
    _sendBtn = Utils.$('#btn-send');

    if (_sendBtn) {
      _sendBtn.addEventListener('click', sendMessage);
    }
    if (_inputEl) {
      _inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
      // 自动调整高度
      _inputEl.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      });
    }

    renderHistory();
  }

  /** 渲染历史消息 */
  function renderHistory() {
    if (!_messagesEl) return;
    var messages = AppState.getMessages();

    if (messages.length === 0) {
      renderEmptyState();
      return;
    }

    _messagesEl.innerHTML = '';
    messages.forEach(function (msg) {
      _messagesEl.appendChild(createMessageEl(msg));
    });
    Utils.scrollToBottom(_messagesEl, true);
  }

  /** 空态 */
  function renderEmptyState() {
    if (!_messagesEl) return;
    _messagesEl.innerHTML = ''
      + '<div class="empty-state" role="status">'
      + '<div class="icon"><svg width="48" height="48" viewBox="0 0 48 48" fill="none"><rect x="4" y="6" width="40" height="32" rx="4" stroke="currentColor" stroke-width="2.5"/><line x1="4" y1="14" x2="44" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="16" y1="6" x2="16" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="32" y1="6" x2="32" y2="14" stroke="currentColor" stroke-width="2.5"/><line x1="20" y1="22" x2="28" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="20" y1="28" x2="24" y2="28" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></div>'
      + '<h3>欢迎使用学习辅助系统</h3>'
      + '<p>我是你的 AI 学习助手，可以帮你：</p>'
      + '<ul>'
      + '<li>制定学习计划</li>'
      + '<li>推荐学习资料</li>'
      + '<li>解答学习问题</li>'
      + '<li>生成练习题目</li>'
      + '</ul>'
      + '<p style="margin-top:12px;font-size:0.875rem;">在左侧边栏可以选择指定的 Agent 来获得更专业的帮助。<br>试试输入你的第一个问题吧！</p>'
      + '</div>';
  }

  /** 创建消息元素 */
  function createMessageEl(msg) {
    var role = msg.role || 'assistant';
    var avatar = msg.avatar || (role === 'user' ? AVATAR_USER : AVATAR_ASSISTANT);

    var msgDiv = Utils.createEl('div', { className: 'message ' + role });

    var avatarEl = Utils.createEl('div', {
      className: 'message-avatar',
      textContent: avatar,
      'aria-label': role === 'user' ? '用户' : '助手',
    });

    var bodyDiv = Utils.createEl('div', { className: 'message-body' });

    var contentEl = Utils.createEl('div', {
      className: 'message-content',
      innerHTML: formatContent(msg.content || ''),
    });

    bodyDiv.appendChild(contentEl);

    if (msg.agent && role !== 'user') {
      var agentLabel = Utils.createEl('div', {
        className: 'message-agent',
        textContent: '处理: ' + msg.agent,
      });
      bodyDiv.appendChild(agentLabel);
    }

    msgDiv.appendChild(avatarEl);
    msgDiv.appendChild(bodyDiv);
    return msgDiv;
  }

  /** 格式化内容（Markdown + Math） */
  function formatContent(text) {
    if (!text) return '';

    var hasMath = /(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)/.test(text);
    var hasKaTeX = (typeof katex !== 'undefined');

    // 如果有数学公式且 KaTeX 可用，先提取公式再渲染 Markdown
    if (hasMath && hasKaTeX) {
      return formatWithMathProtected(text);
    }

    // 纯 Markdown 渲染
    if (typeof marked !== 'undefined' && marked.parse) {
      try {
        return marked.parse(text);
      } catch (e) {
        return Utils.escapeHtml(text).replace(/\n/g, '<br>');
      }
    }
    return Utils.escapeHtml(text).replace(/\n/g, '<br>');
  }

  /** 保护数学公式不被 marked.js 转义，然后渲染 */
  function formatWithMathProtected(text) {
    var mathBlocks = [];
    var counter = 0;

    // 检测末尾是否有未闭合的 $（流式输出中公式可能尚未完整）
    var trailing = '';
    var mainText = text;
    var dollarCount = (text.match(/\$/g) || []).length;
    if (dollarCount % 2 !== 0) {
      var lastDollar = text.lastIndexOf('$');
      trailing = text.substring(lastDollar);
      mainText = text.substring(0, lastDollar);
    }

    // 提取并替换所有完整数学公式为占位符
    var protectedText = mainText
      // 先处理块级公式 $$...$$
      .replace(/\$\$([\s\S]*?)\$\$/g, function (match, formula) {
        var id = 'MATH_BLOCK_' + (counter++);
        mathBlocks.push({ id: id, formula: formula.trim(), display: true });
        return id;
      })
      // 处理行内公式 $...$
      .replace(/\$([^$\n]+?)\$/g, function (match, formula) {
        var id = 'MATH_BLOCK_' + (counter++);
        mathBlocks.push({ id: id, formula: formula.trim(), display: false });
        return id;
      });

    // 尾部未闭合的公式片段：作为纯文本附加，不做 marked.js 处理
    if (trailing) {
      protectedText += trailing;
    }

    // 用 marked.js 渲染 Markdown（占位符不会被转义）
    var html;
    if (typeof marked !== 'undefined' && marked.parse) {
      try {
        html = marked.parse(protectedText);
      } catch (e) {
        html = Utils.escapeHtml(protectedText).replace(/\n/g, '<br>');
      }
    } else {
      html = Utils.escapeHtml(protectedText).replace(/\n/g, '<br>');
    }

    // 将占位符替换为 KaTeX 渲染的 HTML
    mathBlocks.forEach(function (block) {
      try {
        var rendered = katex.renderToString(block.formula, {
          displayMode: block.display,
          throwOnError: false,
        });
        if (block.display) {
          rendered = '<div class="math-block">' + rendered + '</div>';
        }
        // 替换占位符（可能被 marked.js 包裹在 <p> 中）
        html = html.replace(block.id, rendered);
        // 清理可能被 marked.js 在占位符周围生成的空 <p> 标签
        html = html.replace('<p><div class="math-block">', '<div class="math-block">');
        html = html.replace('</div></p>', '</div>');
      } catch (e) {
        html = html.replace(block.id, Utils.escapeHtml('$' + block.formula + '$'));
      }
    });

    return html;
  }

  /** 发送消息 */
  function sendMessage() {
    var message = (_inputEl ? _inputEl.value.trim() : '');
    if (!message) return;

    if (_inputEl) {
      _inputEl.value = '';
      _inputEl.style.height = 'auto';
    }

    // 确保存在活跃对话，否则自动创建
    var convId = AppState.getConversationId();
    if (!convId) {
      _sendWithNewConversation(message);
      return;
    }
    _doSendMessage(message, convId);
  }

  /** 没有活跃对话时，先创建再发送 */
  function _sendWithNewConversation(message) {
    if (!AppState.isLoggedIn()) {
      _doSendMessage(message, '');
      return;
    }
    ApiClient.createConversation('').then(function (data) {
      AppState.setConversationId(data.id);
      if (typeof Conversations !== 'undefined') {
        Conversations.loadConversations();
      }
      _doSendMessage(message, data.id);
    }).catch(function () {
      // 创建失败时仍尝试发送（不带 conversation_id）
      _doSendMessage(message, '');
    });
  }

  /** 实际发送消息 */
  function _doSendMessage(message, convId) {

    // 添加用户消息
    var userMsg = {
      role: 'user',
      content: message,
      avatar: AVATAR_USER,
      timestamp: Date.now(),
    };
    AppState.addMessage(userMsg);

    if (_messagesEl) {
      _messagesEl.appendChild(createMessageEl(userMsg));
      Utils.scrollToBottom(_messagesEl, true);
    }

    // 创建流式消息占位
    var streamingDiv = Utils.createEl('div', {
      className: 'message assistant streaming',
    });
    var avatarEl = Utils.createEl('div', {
      className: 'message-avatar',
      textContent: AVATAR_ASSISTANT,
    });
    var bodyDiv = Utils.createEl('div', { className: 'message-body' });
    var contentEl = Utils.createEl('div', {
      className: 'message-content',
      textContent: '',
    });
    bodyDiv.appendChild(contentEl);
    streamingDiv.appendChild(avatarEl);
    streamingDiv.appendChild(bodyDiv);

    if (_messagesEl) {
      _messagesEl.appendChild(streamingDiv);
      Utils.scrollToBottom(_messagesEl, false);
    }

    _streamingMsg = {
      el: streamingDiv,
      contentEl: contentEl,
      bodyDiv: bodyDiv,
      fullText: '',
      agentRole: '',
      contentStarted: false,
    };

    // 显示等待提示
    contentEl.textContent = '';
    contentEl.classList.add('streaming-waiting');
    contentEl.innerHTML = '<span class="streaming-waiting">正在等待助手响应... <span class="dot-pulse"></span></span>';

    // 发起 SSE 请求
    var history = AppState.getMessages().slice(0, -1).map(function (m) {
      return { role: m.role, content: m.content };
    });

    var agentRole = AppState.getCurrentAgent() || '';

    var payload = {
      message: message,
      user_id: AppState.getUserId(),
      conversation_id: convId,
      history: history.slice(-20),
    };
    if (agentRole && agentRole !== 'auto') {
      payload.agent_role = agentRole;
    }

    SSE.streamChat(payload, {
      onStart: function (data) {
        _streamingMsg.agentRole = data.agent_role || '';
      },
      onChunk: function (chunk) {
        if (!_streamingMsg.contentStarted) {
          _streamingMsg.contentStarted = true;
          _streamingMsg.contentEl.classList.remove('streaming-waiting');
        }
        _streamingMsg.fullText += chunk;
        _streamingMsg.contentEl.innerHTML = formatContent(_streamingMsg.fullText);
        Utils.smartScrollToBottom(_messagesEl, 80);
      },
      onDone: function () {
        finalizeMessage();
      },
      onError: function (err) {
        finalizeMessage(err);
      },
    });
  }

  /** 完成消息 */
  function finalizeMessage(errorMsg) {
    if (!_streamingMsg) return;

    _streamingMsg.el.classList.remove('streaming');

    if (errorMsg) {
      Toast.show(errorMsg, 'error');
      _streamingMsg.contentEl.textContent = '[错误] ' + errorMsg;
      var agentLabel = _streamingMsg.agentRole
        ? AGENT_ROLE_LABELS[_streamingMsg.agentRole] || _streamingMsg.agentRole
        : '系统';
      AppState.addMessage({
        role: 'system',
        content: '[错误] ' + errorMsg,
        avatar: AVATAR_SYSTEM,
        agent: agentLabel,
        timestamp: Date.now(),
      });
    } else {
      if (!_streamingMsg.fullText.trim()) {
        _streamingMsg.fullText = '[提示] 服务器响应超时，请稍后重试。';
        Toast.show(_streamingMsg.fullText, 'warning');
      }
      _streamingMsg.contentEl.innerHTML = formatContent(_streamingMsg.fullText);

      var agentLabel = _streamingMsg.agentRole
        ? AGENT_ROLE_LABELS[_streamingMsg.agentRole] || _streamingMsg.agentRole
        : '';

      AppState.addMessage({
        role: 'assistant',
        content: _streamingMsg.fullText,
        avatar: AVATAR_ASSISTANT,
        agent: agentLabel,
        timestamp: Date.now(),
      });
    }

    _streamingMsg = null;

    // 刷新侧边栏对话列表（更新时间和消息数）
    if (typeof Conversations !== 'undefined') {
      Conversations.loadConversations();
    }
  }

  /** 快捷聊天 */
  function triggerQuickChat(message, agentRole) {
    AppState.setCurrentAgent(agentRole || '');
    // 更新侧边栏 Agent 选择
    if (typeof Sidebar !== 'undefined' && Sidebar.syncAgentSelector) {
      Sidebar.syncAgentSelector(agentRole);
    }
    sendMessage();
    // 需要先设置输入框内容
    if (_inputEl) {
      _inputEl.value = message;
      _inputEl.style.height = 'auto';
    }
    sendMessage();
  }

  return {
    initChat: initChat,
    renderHistory: renderHistory,
    sendMessage: sendMessage,
    triggerQuickChat: triggerQuickChat,
    AGENT_ROLE_LABELS: AGENT_ROLE_LABELS,
  };
})();