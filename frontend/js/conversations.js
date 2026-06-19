/**
 * 历史对话管理模块
 * 管理多对话的创建、切换、删除，数据持久化到后端
 */
var Conversations = (function () {
  'use strict';

  var _listEl = null;
  var _newBtn = null;
  var _conversations = [];
  var _loading = false;       // 防止并发加载
  var _loadPromise = null;    // 当前加载的 Promise

  /** 格式化时间（兼容 ISO 字符串和 Unix 时间戳） */
  function _formatTime(ts) {
    if (!ts) return '';
    var d;
    if (typeof ts === 'string') {
      d = new Date(ts);           // ISO 字符串
    } else {
      d = new Date(ts * 1000);    // Unix 时间戳（秒）
    }
    if (isNaN(d.getTime())) return '';
    var now = new Date();
    var isToday = d.toDateString() === now.toDateString();
    var hh = ('0' + d.getHours()).slice(-2);
    var mm = ('0' + d.getMinutes()).slice(-2);
    if (isToday) {
      return hh + ':' + mm;
    }
    var month = ('0' + (d.getMonth() + 1)).slice(-2);
    var day = ('0' + d.getDate()).slice(-2);
    return month + '/' + day + ' ' + hh + ':' + mm;
  }

  /** 渲染对话列表 */
  function _renderList() {
    if (!_listEl) return;
    _listEl.innerHTML = '';

    if (_conversations.length === 0) {
      var emptyEl = document.createElement('div');
      emptyEl.className = 'conv-empty';
      emptyEl.textContent = '暂无历史对话';
      _listEl.appendChild(emptyEl);
      return;
    }

    var currentId = AppState.getConversationId();

    _conversations.forEach(function (conv) {
      var item = document.createElement('div');
      item.className = 'conv-item' + (conv.id === currentId ? ' active' : '');
      item.setAttribute('data-id', conv.id);

      var info = document.createElement('div');
      info.className = 'conv-info';

      var title = document.createElement('span');
      title.className = 'conv-title';
      title.textContent = conv.title || '新对话';

      var meta = document.createElement('span');
      meta.className = 'conv-meta';
      meta.textContent = _formatTime(conv.updated_at) + ' · ' + (conv.message_count || 0) + '条';

      info.appendChild(title);
      info.appendChild(meta);

      var delBtn = document.createElement('button');
      delBtn.className = 'conv-delete';
      delBtn.setAttribute('aria-label', '删除对话');
      delBtn.textContent = '\u00D7';
      delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        deleteConversation(conv.id);
      });

      item.appendChild(info);
      item.appendChild(delBtn);

      item.addEventListener('click', function () {
        switchConversation(conv.id);
      });

      _listEl.appendChild(item);
    });
  }

  /** 加载对话列表（防并发） */
  function loadConversations() {
    if (!AppState.isLoggedIn()) return Promise.resolve();

    // 如果正在加载，返回当前的 Promise
    if (_loading && _loadPromise) {
      return _loadPromise;
    }

    _loading = true;
    _loadPromise = ApiClient.listConversations().then(function (data) {
      _conversations = data.conversations || [];
      _renderList();
      _loading = false;
      _loadPromise = null;
    }).catch(function (err) {
      console.error('[Conversations] 加载对话列表失败:', err.message || err);
      _loading = false;
      _loadPromise = null;
      // 如果之前有数据，保留显示；否则显示错误提示
      if (_conversations.length === 0 && _listEl) {
        _listEl.innerHTML = '<div class="conv-empty" style="color:var(--color-error)">加载失败，请刷新重试</div>';
      }
    });

    return _loadPromise;
  }

  /** 创建新对话 */
  function createNewConversation() {
    if (!AppState.isLoggedIn()) return;
    ApiClient.createConversation('').then(function (data) {
      AppState.setConversationId(data.id);
      AppState.setMessages([]);
      if (typeof Chat !== 'undefined') {
        Chat.renderHistory();
      }
      loadConversations();
      if (typeof Toast !== 'undefined') {
        Toast.show('新对话已创建', 'success');
      }
    }).catch(function (err) {
      if (typeof Toast !== 'undefined') {
        Toast.show('创建对话失败: ' + (err.message || '未知错误'), 'error');
      }
    });
  }

  /** 切换到指定对话 */
  function switchConversation(convId) {
    if (!convId) return;
    AppState.setConversationId(convId);
    ApiClient.getConversationMessages(convId).then(function (data) {
      var msgs = (data.messages || []).map(function (m) {
        return {
          role: m.role,
          content: m.content,
          avatar: m.role === 'user' ? 'U' : 'AI',
          timestamp: Date.now(),
        };
      });
      // 检查消息完整性：统计 user 和 assistant 消息数量
      var userCount = 0, assistantCount = 0;
      msgs.forEach(function (m) {
        if (m.role === 'user') userCount++;
        if (m.role === 'assistant') assistantCount++;
      });
      console.log('[Conversations] 切换对话 | convId=' + convId + ' user=' + userCount + ' assistant=' + assistantCount + ' total=' + msgs.length);
      if (userCount > 0 && assistantCount === 0) {
        console.warn('[Conversations] 警告：该对话缺少 assistant 回复消息');
      }
      AppState.setMessages(msgs);
      _renderList();
      if (typeof Chat !== 'undefined') {
        Chat.renderHistory();
      }
    }).catch(function (err) {
      console.error('[Conversations] 加载对话消息失败:', err.message || err);
      // 保留现有消息，不强制清空，避免数据丢失
      if (typeof Toast !== 'undefined') {
        Toast.show('加载对话失败: ' + (err.message || '未知错误'), 'error');
      }
    });
  }

  /** 删除对话 */
  function deleteConversation(convId) {
    if (!confirm('确定要删除这个对话吗？此操作不可恢复。')) return;
    ApiClient.deleteConversation(convId).then(function () {
      if (AppState.getConversationId() === convId) {
        AppState.setConversationId('');
        AppState.setMessages([]);
        if (typeof Chat !== 'undefined') {
          Chat.renderHistory();
        }
      }
      loadConversations();
      if (typeof Toast !== 'undefined') {
        Toast.show('对话已删除', 'success');
      }
    }).catch(function (err) {
      if (typeof Toast !== 'undefined') {
        Toast.show('删除失败: ' + (err.message || '未知错误'), 'error');
      }
    });
  }

  /** 初始化 */
  function init() {
    _listEl = document.getElementById('conv-list');
    _newBtn = document.getElementById('btn-new-conv');

    if (_newBtn) {
      _newBtn.addEventListener('click', createNewConversation);
    }

    loadConversations();
  }

  return {
    init: init,
    loadConversations: loadConversations,
    createNewConversation: createNewConversation,
    switchConversation: switchConversation,
    deleteConversation: deleteConversation,
  };
})();