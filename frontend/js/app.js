/**
 * 应用入口模块
 * 路由管理、初始化、全局事件
 */
var App = (function () {
  'use strict';

  var _currentRoute = '';

  /** 路由管理 */
  var router = {
    /** 导航到指定路由 */
    navigate: function (route) {
      if (_currentRoute === route) return;
      _currentRoute = route;
      window.location.hash = route;
      _renderRoute(route);
    },

    /** 获取当前路由 */
    current: function () {
      return _currentRoute;
    },

    /** 处理 hash 变化 */
    onHashChange: function () {
      var hash = window.location.hash.replace('#', '') || '';
      if (!hash) {
        if (AppState.isLoggedIn()) {
          hash = 'chat';
        } else {
          hash = 'login';
        }
      }
      if (hash !== _currentRoute) {
        _currentRoute = hash;
        _renderRoute(hash);
      }
    },
  };

  /** 渲染路由 */
  function _renderRoute(route) {
    var loginPage = Utils.$('#login-page');
    var mainPage = Utils.$('#main-page');

    if (route === 'login') {
      if (loginPage) loginPage.classList.add('active');
      if (mainPage) mainPage.classList.remove('active');
    } else {
      if (AppState.isLoggedIn()) {
        if (loginPage) loginPage.classList.remove('active');
        if (mainPage) mainPage.classList.add('active');
        initMainPage();
      } else {
        router.navigate('login');
      }
    }
  }

  /** 初始化主界面 */
  function initMainPage() {
    // 初始化侧边栏
    if (typeof Sidebar !== 'undefined') {
      Sidebar.init();
    }
    // 初始化聊天
    if (typeof Chat !== 'undefined') {
      Chat.initChat();
    }
  }

  /** 应用初始化 */
  function init() {
    // 初始化主题（最早执行，避免闪烁）
    if (typeof Theme !== 'undefined') {
      Theme.initTheme();
    }

    // 监听 hash 变化
    window.addEventListener('hashchange', router.onHashChange);

    // 初始化登录页
    if (typeof Auth !== 'undefined') {
      Auth.initLoginPage();
    }

    // 检查登录状态
    if (AppState.isLoggedIn()) {
      router.navigate('chat');
    } else {
      router.navigate('login');
    }
  }

  // DOM 加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  return {
    router: router,
    init: init,
  };
})();