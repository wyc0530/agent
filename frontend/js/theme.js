/**
 * 主题切换模块
 * 管理明暗主题切换，状态持久化到 localStorage
 */
var Theme = (function () {
  'use strict';

  var THEME_KEY = 'ls_theme';
  var THEME_LIGHT = 'light';
  var THEME_DARK = 'dark';

  var _btn = null;
  var _icon = null;

  /** 获取当前主题 */
  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || THEME_LIGHT;
  }

  /** 设置主题 */
  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (e) { /* 忽略存储错误 */ }
    _updateIcon(theme);
  }

  /** 切换主题 */
  function toggleTheme() {
    var current = getTheme();
    var next = current === THEME_DARK ? THEME_LIGHT : THEME_DARK;
    setTheme(next);
  }

  /** 更新图标 */
  function _updateIcon(theme) {
    if (_icon) {
      _icon.textContent = theme === THEME_DARK ? '☀️' : '🌙';
    }
  }

  /** 初始化主题 */
  function initTheme() {
    _btn = document.getElementById('btn-theme-toggle');
    _icon = document.getElementById('theme-icon');

    // 从 localStorage 恢复主题，无记录时默认亮色
    var savedTheme = null;
    try {
      savedTheme = localStorage.getItem(THEME_KEY);
    } catch (e) { /* 忽略 */ }
    setTheme(savedTheme || THEME_LIGHT);

    // 绑定切换按钮
    if (_btn) {
      _btn.addEventListener('click', toggleTheme);
    }
  }

  return {
    initTheme: initTheme,
    toggleTheme: toggleTheme,
    getTheme: getTheme,
    setTheme: setTheme,
  };
})();