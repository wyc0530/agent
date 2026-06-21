/**
 * 前端全局状态管理
 * 使用 localStorage（持久化）和 sessionStorage（会话级）存储
 */
var AppState = (function () {
  'use strict';

  var STORAGE_KEYS = {
    TOKEN: 'ls_token',
    USER_ID: 'ls_user_id',
    USERNAME: 'ls_username',
    DISPLAY_NAME: 'ls_display_name',
    MESSAGES: 'ss_messages',
    PROFILE: 'ss_profile',
    CURRENT_AGENT: 'ss_current_agent',
    CURRENT_CONVERSATION_ID: 'ss_current_conv_id',
  };

  /* 内存缓存 */
  var _cache = {};

  function _getCache(key) {
    if (_cache[key] !== undefined) return _cache[key];
    return null;
  }

  function _setCache(key, value) {
    _cache[key] = value;
  }

  function _clearCache() {
    _cache = {};
  }

  /* localStorage 操作 */
  function _lsGet(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function _lsSet(key, value) {
    try { localStorage.setItem(key, value); _setCache(key, value); } catch (e) {}
  }
  function _lsRemove(key) {
    try { localStorage.removeItem(key); _cache[key] = undefined; } catch (e) {}
  }

  /* sessionStorage 操作 */
  function _ssGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function _ssSet(key, value) {
    try { sessionStorage.setItem(key, value); _setCache(key, value); } catch (e) {}
  }
  function _ssRemove(key) {
    try { sessionStorage.removeItem(key); _cache[key] = undefined; } catch (e) {}
  }

  /* --- 公开 API --- */

  /** 是否已登录 */
  function isLoggedIn() {
    return !!getToken();
  }

  /** 获取/设置 Token */
  function getToken() {
    return _lsGet(STORAGE_KEYS.TOKEN) || '';
  }
  function setToken(token) {
    _lsSet(STORAGE_KEYS.TOKEN, token);
  }

  /** 获取/设置用户ID */
  function getUserId() {
    return _lsGet(STORAGE_KEYS.USER_ID) || '';
  }
  function setUserId(id) {
    _lsSet(STORAGE_KEYS.USER_ID, id);
  }

  /** 获取/设置用户名 */
  function getUsername() {
    return _lsGet(STORAGE_KEYS.USERNAME) || '';
  }
  function setUsername(name) {
    _lsSet(STORAGE_KEYS.USERNAME, name);
  }

  /** 获取/设置昵称 */
  function getDisplayName() {
    return _lsGet(STORAGE_KEYS.DISPLAY_NAME) || '';
  }
  function setDisplayName(name) {
    _lsSet(STORAGE_KEYS.DISPLAY_NAME, name);
  }

  /** 应用登录状态 */
  function applyLogin(authData) {
    setToken(authData.token || '');
    setUserId(authData.user_id || '');
    setUsername(authData.username || '');
    setDisplayName(authData.display_name || authData.username || '');
  }

  /** 获取/设置消息历史 */
  function getMessages() {
    try {
      var raw = _ssGet(STORAGE_KEYS.MESSAGES);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }
  function setMessages(messages) {
    try {
      _ssSet(STORAGE_KEYS.MESSAGES, JSON.stringify(messages));
    } catch (e) {}
  }
  function addMessage(msg) {
    var messages = getMessages();
    messages.push(msg);
    if (messages.length > 50) {
      messages = messages.slice(-50);
    }
    setMessages(messages);
    return messages;
  }

  /** 获取/设置用户资料 */
  function getProfile() {
    try {
      var raw = _ssGet(STORAGE_KEYS.PROFILE);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }
  function setProfile(profile) {
    try {
      _ssSet(STORAGE_KEYS.PROFILE, JSON.stringify(profile));
    } catch (e) {}
  }

  /** 获取/设置当前Agent */
  function getCurrentAgent() {
    return _ssGet(STORAGE_KEYS.CURRENT_AGENT) || '';
  }
  function setCurrentAgent(agent) {
    _ssSet(STORAGE_KEYS.CURRENT_AGENT, agent);
  }

  function getConversationId() {
    return _ssGet(STORAGE_KEYS.CURRENT_CONVERSATION_ID) || '';
  }
  function setConversationId(id) {
    _ssSet(STORAGE_KEYS.CURRENT_CONVERSATION_ID, id || '');
  }

  /** 清除所有状态（退出登录） */
  function clearAll() {
    _lsRemove(STORAGE_KEYS.TOKEN);
    _lsRemove(STORAGE_KEYS.USER_ID);
    _lsRemove(STORAGE_KEYS.USERNAME);
    _lsRemove(STORAGE_KEYS.DISPLAY_NAME);
    _ssRemove(STORAGE_KEYS.MESSAGES);
    _ssRemove(STORAGE_KEYS.PROFILE);
    _ssRemove(STORAGE_KEYS.CURRENT_AGENT);
    _ssRemove(STORAGE_KEYS.CURRENT_CONVERSATION_ID);
    _clearCache();
  }

  return {
    isLoggedIn: isLoggedIn,
    getToken: getToken,
    setToken: setToken,
    getUserId: getUserId,
    setUserId: setUserId,
    getUsername: getUsername,
    setUsername: setUsername,
    getDisplayName: getDisplayName,
    setDisplayName: setDisplayName,
    applyLogin: applyLogin,
    getMessages: getMessages,
    setMessages: setMessages,
    addMessage: addMessage,
    getProfile: getProfile,
    setProfile: setProfile,
    getCurrentAgent: getCurrentAgent,
    setCurrentAgent: setCurrentAgent,
    getConversationId: getConversationId,
    setConversationId: setConversationId,
    clearAll: clearAll,
  };
})();