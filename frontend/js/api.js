/**
 * API 客户端模块
 * 封装所有后端 REST API 调用
 */
var ApiClient = (function () {
  'use strict';

  var API_BASE = 'http://localhost:8000';
  var TIMEOUT_DEFAULT = 10000;
  var TIMEOUT_STREAM = 120000;

  /** 设置 API 地址 */
  function setBaseUrl(url) {
    API_BASE = url;
  }

  /** 构建请求头 */
  function _buildHeaders() {
    var headers = { 'Content-Type': 'application/json' };
    var token = AppState.getToken();
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    return headers;
  }

  /** 通用请求 */
  function _request(method, path, body, timeout, stream) {
    timeout = timeout || TIMEOUT_DEFAULT;
    var url = API_BASE + path;
    var options = {
      method: method,
      headers: _buildHeaders(),
    };
    if (body) {
      options.body = JSON.stringify(body);
    }

    return new Promise(function (resolve, reject) {
      var controller = new AbortController();
      var timer = setTimeout(function () { controller.abort(); }, timeout);
      options.signal = controller.signal;

      fetch(url, options)
        .then(function (resp) {
          clearTimeout(timer);
          if (stream) {
            resolve(resp);
            return;
          }
          return resp.json().then(function (data) {
            resolve({ status: resp.status, data: data });
          }).catch(function () {
            resolve({ status: resp.status, data: { detail: '服务返回异常' } });
          });
        })
        .catch(function (err) {
          clearTimeout(timer);
          if (err.name === 'AbortError') {
            reject(new ApiError('请求超时，请稍后重试'));
          } else {
            reject(new ApiError('无法连接到后端 API，请确保服务已启动'));
          }
        });
    });
  }

  /** 自定义错误 */
  function ApiError(message, statusCode) {
    this.message = message;
    this.statusCode = statusCode || 0;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  /** 处理响应 */
  function _handleResponse(result) {
    if (result.status >= 200 && result.status < 300) {
      return result.data;
    }
    var detail = (result.data && result.data.detail) || '请求失败';
    throw new ApiError(detail, result.status);
  }

  /** 登录 */
  function login(username, password) {
    return _request('POST', '/auth/login', { username: username, password: password })
      .then(function (result) {
        if (result.status === 401) throw new ApiError('用户名或密码错误', 401);
        return _handleResponse(result);
      });
  }

  /** 注册 */
  function register(username, password, displayName, email) {
    return _request('POST', '/auth/register', {
      username: username,
      password: password,
      display_name: displayName || '',
      email: email || '',
    }).then(function (result) {
      if (result.status === 409) throw new ApiError('用户名已存在', 409);
      return _handleResponse(result);
    });
  }

  /** 退出登录 */
  function logout() {
    return _request('POST', '/auth/logout', null, 5000).catch(function () {});
  }

  /** 获取个人信息 */
  function getProfile() {
    return _request('GET', '/user/profile').then(_handleResponse);
  }

  /** 更新个人信息 */
  function updateProfile(profileData) {
    return _request('PUT', '/user/profile', profileData).then(_handleResponse);
  }

  /** 修改密码 */
  function changePassword(oldPassword, newPassword) {
    return _request('PUT', '/user/profile/password', {
      old_password: oldPassword,
      new_password: newPassword,
    }).then(_handleResponse);
  }

  /** 健康检查 */
  function checkHealth() {
    return _request('GET', '/health', null, 5000);
  }

  /** SSE 流式请求 */
  function streamChatRequest(payload) {
    return _request('POST', '/chat/stream', payload, TIMEOUT_STREAM, true);
  }

  /** 获取对话列表 */
  function listConversations() {
    return _request('GET', '/conversations').then(_handleResponse);
  }

  /** 创建新对话 */
  function createConversation(title) {
    return _request('POST', '/conversations', { title: title || '' }).then(_handleResponse);
  }

  /** 获取对话消息 */
  function getConversationMessages(convId) {
    return _request('GET', '/conversations/' + convId).then(_handleResponse);
  }

  /** 删除对话 */
  function deleteConversation(convId) {
    return _request('DELETE', '/conversations/' + convId).then(_handleResponse);
  }

  return {
    setBaseUrl: setBaseUrl,
    login: login,
    register: register,
    logout: logout,
    getProfile: getProfile,
    updateProfile: updateProfile,
    changePassword: changePassword,
    checkHealth: checkHealth,
    streamChatRequest: streamChatRequest,
    listConversations: listConversations,
    createConversation: createConversation,
    getConversationMessages: getConversationMessages,
    deleteConversation: deleteConversation,
    ApiError: ApiError,
  };
})();