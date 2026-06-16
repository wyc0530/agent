/**
 * Toast 消息提示模块
 */
var Toast = (function () {
  'use strict';

  var _container = null;
  var _timer = null;

  function _ensureContainer() {
    if (_container) return _container;
    _container = Utils.$('#toast-container');
    if (!_container) {
      _container = Utils.createEl('div', { id: 'toast-container', className: 'toast-container' });
      document.body.appendChild(_container);
    }
    return _container;
  }

  /** 显示提示 */
  function show(message, type, duration) {
    type = type || 'info';
    duration = (duration !== undefined) ? duration : 3000;

    var container = _ensureContainer();
    var icon = type === 'success' ? '✓' : type === 'error' ? '✗' : '⚠';
    var toast = Utils.createEl('div', {
      className: 'toast ' + type,
      textContent: icon + ' ' + message,
      role: 'alert',
    });

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(function () {
        toast.classList.add('fade-out');
        toast.addEventListener('animationend', function () {
          toast.remove();
        });
      }, duration);
    }

    return toast;
  }

  return { show: show };
})();