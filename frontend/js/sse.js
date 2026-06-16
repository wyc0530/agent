/**
 * SSE 流式请求模块
 * 使用 fetch() + ReadableStream 实现 POST SSE
 */
var SSE = (function () {
  'use strict';

  /**
   * 解析 SSE 行
   * @param {string} line - 原始 SSE 行
   * @returns {object|null} 解析后的数据
   */
  function parseLine(line) {
    if (!line || !line.startsWith('data: ')) return null;
    return Utils.safeJsonParse(line.slice(6), null);
  }

  /**
   * 流式对话
   * @param {object} payload - 请求体
   * @param {object} callbacks - 回调函数 { onStart, onChunk, onDone, onError }
   * @returns {Promise} 完成后 resolve
   */
  function streamChat(payload, callbacks) {
    callbacks = callbacks || {};

    return ApiClient.streamChatRequest(payload).then(function (resp) {
      if (!resp.ok) {
        throw new ApiClient.ApiError('请求失败 (HTTP ' + resp.status + ')', resp.status);
      }

      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function processChunk() {
        return reader.read().then(function (result) {
          if (result.done) {
            if (callbacks.onDone) callbacks.onDone();
            return;
          }

          buffer += decoder.decode(result.value, { stream: true });
          var parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (var i = 0; i < parts.length; i++) {
            var data = parseLine(parts[i]);
            if (!data) continue;

            var type = data.type || '';
            switch (type) {
              case 'start':
                if (callbacks.onStart) callbacks.onStart(data);
                break;
              case 'chunk':
                if (callbacks.onChunk) callbacks.onChunk(data.content || '');
                break;
              case 'error':
                if (callbacks.onError) callbacks.onError(data.content || '流式响应错误');
                return;
              case 'done':
                if (callbacks.onDone) callbacks.onDone();
                return;
            }
          }

          return processChunk();
        });
      }

      return processChunk();
    }).catch(function (err) {
      if (callbacks.onError) callbacks.onError(err.message || '对话服务暂时不可用');
    });
  }

  return {
    parseLine: parseLine,
    streamChat: streamChat,
  };
})();