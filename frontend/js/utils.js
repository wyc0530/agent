/**
 * 工具函数模块
 * 表单校验、DOM 操作、格式化等
 */
var Utils = (function () {
  'use strict';

  /** 防抖 */
  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var ctx = this, args = arguments;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
    };
  }

  /** 节流 */
  function throttle(fn, limit) {
    var inThrottle = false;
    return function () {
      var ctx = this, args = arguments;
      if (!inThrottle) {
        fn.apply(ctx, args);
        inThrottle = true;
        setTimeout(function () { inThrottle = false; }, limit);
      }
    };
  }

  /** HTML 转义（防 XSS） */
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /** 获取元素 */
  function $(selector, parent) {
    return (parent || document).querySelector(selector);
  }
  function $$(selector, parent) {
    return (parent || document).querySelectorAll(selector);
  }

  /** 创建元素 */
  function createEl(tag, attrs, children) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === 'className') {
          el.className = attrs[key];
        } else if (key === 'textContent') {
          el.textContent = attrs[key];
        } else if (key === 'innerHTML') {
          el.innerHTML = attrs[key];
        } else if (key.startsWith('on')) {
          el.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
        } else if (key === 'style' && typeof attrs[key] === 'object') {
          Object.assign(el.style, attrs[key]);
        } else {
          el.setAttribute(key, attrs[key]);
        }
      });
    }
    if (children) {
      if (Array.isArray(children)) {
        children.forEach(function (c) { if (c) el.appendChild(c); });
      } else if (typeof children === 'string') {
        el.textContent = children;
      } else if (children instanceof Node) {
        el.appendChild(children);
      }
    }
    return el;
  }

  /** 表单校验 */
  function validateRequired(value, fieldName) {
    if (!value || !value.trim()) {
      return fieldName + '为必填项';
    }
    return null;
  }

  function validateMinLength(value, min, fieldName) {
    if (!value || value.length < min) {
      return fieldName + '至少' + min + '个字符';
    }
    return null;
  }

  function validateEmail(value) {
    if (!value) return null;
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(value) ? null : '邮箱格式不正确';
  }

  /** 格式化时间 */
  function formatTime(ts) {
    var d = new Date(ts);
    var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
    return pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  /** 滚动到底部 */
  function scrollToBottom(el, smooth) {
    if (!el) return;
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (smooth) {
          el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        } else {
          el.scrollTop = el.scrollHeight;
        }
      });
    });
  }

  /** 安全 JSON 解析 */
  function safeJsonParse(str, fallback) {
    try { return JSON.parse(str); } catch (e) { return fallback !== undefined ? fallback : null; }
  }

  return {
    debounce: debounce,
    throttle: throttle,
    escapeHtml: escapeHtml,
    $: $,
    $$: $$,
    createEl: createEl,
    validateRequired: validateRequired,
    validateMinLength: validateMinLength,
    validateEmail: validateEmail,
    formatTime: formatTime,
    scrollToBottom: scrollToBottom,
    safeJsonParse: safeJsonParse,
  };
})();