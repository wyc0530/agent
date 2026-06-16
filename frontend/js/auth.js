/**
 * 认证模块
 * 登录/注册/退出登录/密码修改
 */
var Auth = (function () {
  'use strict';

  /** 初始化登录页面事件 */
  function initLoginPage() {
    var tabs = Utils.$$('.auth-tab');
    var forms = Utils.$$('.auth-form');

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var target = this.getAttribute('data-tab');
        tabs.forEach(function (t) { t.classList.remove('active'); });
        forms.forEach(function (f) { f.classList.remove('active'); });
        this.classList.add('active');
        var form = Utils.$('.auth-form[data-form="' + target + '"]');
        if (form) form.classList.add('active');
      });
    });

    // 登录表单
    var loginBtn = Utils.$('#btn-login');
    if (loginBtn) {
      loginBtn.addEventListener('click', handleLogin);
    }
    var loginForm = Utils.$('.auth-form[data-form="login"]');
    if (loginForm) {
      loginForm.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') handleLogin();
      });
    }

    // 注册表单
    var registerBtn = Utils.$('#btn-register');
    if (registerBtn) {
      registerBtn.addEventListener('click', handleRegister);
    }
  }

  /** 处理登录 */
  function handleLogin() {
    var username = (Utils.$('#login-username') || {}).value || '';
    var password = (Utils.$('#login-password') || {}).value || '';

    if (!username || !password) {
      Toast.show('请输入用户名和密码', 'warning');
      return;
    }

    var btn = Utils.$('#btn-login');
    if (btn) { btn.disabled = true; btn.textContent = '登录中...'; }

    ApiClient.login(username, password)
      .then(function (data) {
        AppState.applyLogin(data);
        Toast.show('登录成功！', 'success');
        setTimeout(function () { App.router.navigate('chat'); }, 500);
      })
      .catch(function (err) {
        Toast.show(err.message || '登录失败', 'error');
      })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = '登录'; }
      });
  }

  /** 处理注册 */
  function handleRegister() {
    var username = (Utils.$('#reg-username') || {}).value || '';
    var displayName = (Utils.$('#reg-display-name') || {}).value || '';
    var email = (Utils.$('#reg-email') || {}).value || '';
    var password = (Utils.$('#reg-password') || {}).value || '';
    var passwordConfirm = (Utils.$('#reg-password-confirm') || {}).value || '';

    var err = Utils.validateRequired(username, '用户名') ||
      Utils.validateMinLength(username, 3, '用户名');
    if (err) { Toast.show(err, 'warning'); return; }

    err = Utils.validateRequired(password, '密码') ||
      Utils.validateMinLength(password, 6, '密码');
    if (err) { Toast.show(err, 'warning'); return; }

    if (password !== passwordConfirm) {
      Toast.show('两次密码不一致', 'warning');
      return;
    }

    if (email) {
      err = Utils.validateEmail(email);
      if (err) { Toast.show(err, 'warning'); return; }
    }

    var btn = Utils.$('#btn-register');
    if (btn) { btn.disabled = true; btn.textContent = '注册中...'; }

    ApiClient.register(username, password, displayName, email)
      .then(function (data) {
        AppState.applyLogin(data);
        Toast.show('注册成功！', 'success');
        setTimeout(function () { App.router.navigate('chat'); }, 500);
      })
      .catch(function (err) {
        Toast.show(err.message || '注册失败', 'error');
      })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.textContent = '注册'; }
      });
  }

  /** 处理退出登录 */
  function handleLogout() {
    ApiClient.logout();
    AppState.clearAll();
    App.router.navigate('login');
  }

  /** 显示退出确认弹窗 */
  function showLogoutConfirm() {
    var overlay = Utils.createEl('div', { className: 'modal-overlay' });
    var modal = Utils.createEl('div', { className: 'modal' });

    var msg = Utils.createEl('p', { textContent: '确定要退出登录吗？' });
    var actions = Utils.createEl('div', { className: 'modal-actions' });

    var cancelBtn = Utils.createEl('button', {
      className: 'btn btn-secondary',
      textContent: '取消',
      onClick: function () { overlay.remove(); },
    });

    var confirmBtn = Utils.createEl('button', {
      className: 'btn btn-danger',
      textContent: '确定退出',
      onClick: function () {
        overlay.remove();
        handleLogout();
      },
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    modal.appendChild(msg);
    modal.appendChild(actions);
    overlay.appendChild(modal);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });

    document.body.appendChild(overlay);
  }

  /** 处理密码修改 */
  function handlePasswordChange() {
    var oldPass = (Utils.$('#settings-old-password') || {}).value || '';
    var newPass = (Utils.$('#settings-new-password') || {}).value || '';
    var newPass2 = (Utils.$('#settings-new-password-confirm') || {}).value || '';

    if (!oldPass || !newPass) {
      Toast.show('请填写原密码和新密码', 'warning');
      return;
    }
    if (newPass.length < 6) {
      Toast.show('新密码长度不能少于6位', 'warning');
      return;
    }
    if (newPass !== newPass2) {
      Toast.show('两次输入的新密码不一致', 'warning');
      return;
    }

    ApiClient.changePassword(oldPass, newPass)
      .then(function () {
        Toast.show('密码已修改', 'success');
        Utils.$('#settings-old-password').value = '';
        Utils.$('#settings-new-password').value = '';
        Utils.$('#settings-new-password-confirm').value = '';
      })
      .catch(function (err) {
        Toast.show(err.message || '密码修改失败', 'error');
      });
  }

  return {
    initLoginPage: initLoginPage,
    handleLogin: handleLogin,
    handleRegister: handleRegister,
    handleLogout: handleLogout,
    showLogoutConfirm: showLogoutConfirm,
    handlePasswordChange: handlePasswordChange,
  };
})();