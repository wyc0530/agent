/**
 * API 客户端模块
 * 封装所有后端 REST API 调用
 */
var ApiClient = (function () {
  "use strict";

  var API_BASE = "http://localhost:8000";
  var TIMEOUT_DEFAULT = 10000;
  var TIMEOUT_STREAM = 120000;
  var TIMEOUT_UPLOAD = 60000;

  function setBaseUrl(url) { API_BASE = url; }

  function _buildHeaders() {
    var headers = { "Content-Type": "application/json" };
    var token = AppState.getToken();
    if (token) { headers["Authorization"] = "Bearer " + token; }
    return headers;
  }

  function _request(method, path, body, timeout, stream) {
    timeout = timeout || TIMEOUT_DEFAULT;
    var url = API_BASE + path;
    var options = { method: method, headers: _buildHeaders() };
    if (body) { options.body = JSON.stringify(body); }
    return new Promise(function (resolve, reject) {
      var controller = new AbortController();
      var timer = setTimeout(function () { controller.abort(); }, timeout);
      options.signal = controller.signal;
      fetch(url, options)
        .then(function (resp) {
          clearTimeout(timer);
          if (stream) { resolve(resp); return; }
          return resp.json().then(function (data) {
            resolve({ status: resp.status, data: data });
          }).catch(function () {
            resolve({ status: resp.status, data: { detail: "服务返回异常" } });
          });
        })
        .catch(function (err) {
          clearTimeout(timer);
          if (err.name === "AbortError") {
            reject(new ApiError("请求超时，请稍后重试"));
          } else {
            reject(new ApiError("无法连接到后端 API，请确保服务已启动"));
          }
        });
    });
  }

  function ApiError(message, statusCode) {
    this.message = message;
    this.statusCode = statusCode || 0;
    this.status = this.statusCode;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  function _handleResponse(result) {
    if (result.status >= 200 && result.status < 300) { return result.data; }
    var detail = (result.data && result.data.detail) || "请求失败";
    throw new ApiError(detail, result.status);
  }

  function login(username, password) {
    return _request("POST", "/auth/login", { username: username, password: password })
      .then(function (result) {
        if (result.status === 401) throw new ApiError("用户名或密码错误", 401);
        return _handleResponse(result);
      });
  }

  function register(username, password, displayName, email) {
    return _request("POST", "/auth/register", {
      username: username, password: password,
      display_name: displayName || "", email: email || "",
    }).then(function (result) {
      if (result.status === 409) throw new ApiError("用户名已存在", 409);
      return _handleResponse(result);
    });
  }

  function logout() {
    return _request("POST", "/auth/logout", null, 5000).catch(function () {});
  }

  function getProfile() { return _request("GET", "/user/profile").then(_handleResponse); }
  function updateProfile(profileData) { return _request("PUT", "/user/profile", profileData).then(_handleResponse); }
  function changePassword(oldPassword, newPassword) {
    return _request("PUT", "/user/profile/password", {
      old_password: oldPassword, new_password: newPassword,
    }).then(_handleResponse);
  }
  function checkHealth() { return _request("GET", "/health", null, 5000); }
  function streamChatRequest(payload) { return _request("POST", "/chat/stream", payload, TIMEOUT_STREAM, true); }
  function listConversations() { return _request("GET", "/conversations").then(_handleResponse); }
  function createConversation(title) { return _request("POST", "/conversations", { title: title || "" }).then(_handleResponse); }
  function getConversationMessages(convId) { return _request("GET", "/conversations/" + convId).then(_handleResponse); }
  function deleteConversation(convId) { return _request("DELETE", "/conversations/" + convId).then(_handleResponse); }
  function deleteMessage(convId, msgId) { return _request("DELETE", "/conversations/" + convId + "/messages/" + msgId).then(_handleResponse); }

  /** 上传文件 */
  function uploadFile(file, onProgress) {
    return new Promise(function (resolve, reject) {
      var formData = new FormData();
      formData.append("file", file);
      var xhr = new XMLHttpRequest();
      xhr.open("POST", API_BASE + "/file/upload", true);
      var token = AppState.getToken();
      if (token) { xhr.setRequestHeader("Authorization", "Bearer " + token); }
      xhr.timeout = TIMEOUT_UPLOAD;
      if (onProgress) {
        xhr.upload.onprogress = function (e) {
          if (e.lengthComputable) { onProgress(Math.round((e.loaded / e.total) * 90)); }
        };
      }
      xhr.onload = function () {
        try {
          var resp = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) { resolve(resp); }
          else { reject(new ApiError(resp.detail || "文件上传失败", xhr.status)); }
        } catch (e) { reject(new ApiError("服务器响应异常")); }
      };
      xhr.onerror = function () { reject(new ApiError("无法连接到服务器")); };
      xhr.ontimeout = function () { reject(new ApiError("上传超时")); };
      xhr.send(formData);
    });
  }

  /** 基于文件提问 */
  function askFileQuestion(fileId, question, convId) {
    var body = { file_id: fileId, question: question };
    if (convId) { body.conversation_id = convId; }
    return _request("POST", "/file/ask", body, TIMEOUT_STREAM)
      .then(_handleResponse);
  }

  /** 导出对话为 Word */
  function exportChatAnswer(question, answer, title) {
    return _request("POST", "/chat/export", {
      question: question || "",
      answer: answer,
      title: title || "问答记录",
    }, TIMEOUT_DEFAULT).then(_handleResponse);
  }

  /** 下载文件 */
  function getDownloadUrl(filename) {
    return API_BASE + "/file/download/" + filename;
  }

  return {
    setBaseUrl: setBaseUrl,
    login: login, register: register, logout: logout,
    getProfile: getProfile, updateProfile: updateProfile,
    changePassword: changePassword, checkHealth: checkHealth,
    streamChatRequest: streamChatRequest,
    listConversations: listConversations,
    createConversation: createConversation,
    getConversationMessages: getConversationMessages,
    deleteConversation: deleteConversation,
    deleteMessage: deleteMessage,
    uploadFile: uploadFile,
    askFileQuestion: askFileQuestion,
    exportChatAnswer: exportChatAnswer,
    getDownloadUrl: getDownloadUrl,
    ApiError: ApiError,
  };
})();
