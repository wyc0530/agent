/**
 * 聊天模块测试
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { Chat, AppState } from './setup.js';

beforeEach(() => {
  sessionStorage.clear();
  AppState.clearAll();
  // 创建聊天 DOM 结构
  document.body.innerHTML = `
    <div id="chat-messages" class="chat-messages"></div>
    <div class="chat-input-area">
      <textarea id="chat-input"></textarea>
      <button id="btn-send"></button>
    </div>
  `;
  // 初始化聊天模块
  Chat.initChat();
});

describe('Chat', () => {
  describe('AGENT_ROLE_LABELS', () => {
    it('包含所有 Agent 标签', () => {
      expect(Chat.AGENT_ROLE_LABELS.auto).toBe('自动识别');
      expect(Chat.AGENT_ROLE_LABELS.planner).toBe('学习规划师');
      expect(Chat.AGENT_ROLE_LABELS.expert).toBe('学习专家');
      expect(Chat.AGENT_ROLE_LABELS.partner).toBe('学习伙伴');
      expect(Chat.AGENT_ROLE_LABELS.quizzer).toBe('出题官');
      expect(Chat.AGENT_ROLE_LABELS.reviewer).toBe('复习助理');
      expect(Chat.AGENT_ROLE_LABELS.examiner).toBe('考试指导');
    });
  });

  describe('renderHistory', () => {
    it('空消息时显示空态', () => {
      Chat.renderHistory();
      const emptyState = document.querySelector('.empty-state');
      expect(emptyState).toBeTruthy();
      expect(emptyState.textContent).toContain('学习');
    });

    it('有消息时渲染消息列表', () => {
      AppState.addMessage({ role: 'user', content: '你好', avatar: '👤', timestamp: Date.now() });
      AppState.addMessage({ role: 'assistant', content: '你好！', avatar: '🤖', agent: '学习伙伴', timestamp: Date.now() });
      Chat.renderHistory();
      const messages = document.querySelectorAll('.message');
      expect(messages.length).toBe(2);
      expect(messages[0].classList.contains('user')).toBe(true);
      expect(messages[1].classList.contains('assistant')).toBe(true);
    });
  });

  describe('sendMessage', () => {
    it('空消息不发送', () => {
      const input = document.getElementById('chat-input');
      input.value = '  ';
      const beforeCount = AppState.getMessages().length;
      Chat.sendMessage();
      expect(AppState.getMessages().length).toBe(beforeCount);
    });

    it('发送有效消息后清空输入框', () => {
      const input = document.getElementById('chat-input');
      input.value = '测试消息';
      Chat.sendMessage();
      // 消息发送后输入框应清空
      expect(input.value).toBe('');
    });
  });
});