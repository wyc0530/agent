/**
 * 测试环境初始化
 * 在 jsdom 中加载所有 JS 模块
 */
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const jsDir = path.resolve(__dirname, '../js');

// 按依赖顺序加载
const loadOrder = [
  'state.js',
  'utils.js',
  'api.js',
  'sse.js',
  'toast.js',
  'theme.js',
  'conversations.js',
  'auth.js',
  'chat.js',
  'sidebar.js',
  'app.js',
];

// 创建 jsdom 环境
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
  runScripts: 'dangerously',
});

// 注入全局变量
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.localStorage = dom.window.localStorage;
global.sessionStorage = dom.window.sessionStorage;

// JSDOM polyfill: Element.scrollTo 在真实浏览器中可用，JSDOM 未实现
if (!dom.window.Element.prototype.scrollTo) {
  dom.window.Element.prototype.scrollTo = function (options) {
    if (typeof options === 'object') {
      this.scrollTop = options.top !== undefined ? options.top : this.scrollTop;
      this.scrollLeft = options.left !== undefined ? options.left : this.scrollLeft;
    } else {
      this.scrollTop = arguments[0];
      this.scrollLeft = arguments[1] !== undefined ? arguments[1] : this.scrollLeft;
    }
  };
}

// 加载所有 JS 模块（使用 eval 在 window 上下文中执行）
loadOrder.forEach((file) => {
  const filePath = path.join(jsDir, file);
  if (fs.existsSync(filePath)) {
    const code = fs.readFileSync(filePath, 'utf-8');
    try {
      dom.window.eval(code);
    } catch (e) {
      console.error(`Failed to load ${file}:`, e.message);
    }
  }
});

// 获取模块引用
export const AppState = dom.window.AppState;
export const Utils = dom.window.Utils;
export const ApiClient = dom.window.ApiClient;
export const SSE = dom.window.SSE;
export const Toast = dom.window.Toast;
export const Theme = dom.window.Theme;
export const Conversations = dom.window.Conversations;
export const Auth = dom.window.Auth;
export const Chat = dom.window.Chat;
export const Sidebar = dom.window.Sidebar;
export const App = dom.window.App;

export { dom };