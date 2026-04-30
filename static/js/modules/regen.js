/**
 * Selection Regeneration Popup module – inline text regeneration via selection.
 */

import { api } from '../api.js';
import { showAlert, escapeHtml } from '../ui.js';
import { queueDraftAutosave } from './state.js';
import { updatePublishPreviewFromForm } from './preview.js';

let _regenSel = null;
let _regenPopupEl = null;
let _regenSelChangeTimer = null;
let _mouseIsDown = false;

document.addEventListener('mousedown', (e) => { if (e.button === 0) _mouseIsDown = true; });
document.addEventListener('mouseup',   (e) => { if (e.button === 0) _mouseIsDown = false; });

function _buildRegenPopup() {
  if (_regenPopupEl) return _regenPopupEl;

  const popup = document.createElement('div');
  popup.id = 'regen-selection-popup';
  popup.style.cssText = [
    'display:none',
    'position:fixed',
    'z-index:2147483647',
    'background:#fff',
    'border:1px solid #d0d0d0',
    'border-radius:10px',
    'box-shadow:0 6px 28px rgba(0,0,0,0.22)',
    'padding:14px',
    'width:340px',
    'box-sizing:border-box',
    'font-family:inherit',
  ].join(';');

  popup.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.78rem;font-weight:600;color:#555;">Herschrijf selectie</span>
        <button id="regen-sel-close" style="background:none;border:none;cursor:pointer;font-size:1rem;color:#888;padding:0;line-height:1;" title="Sluiten">✕</button>
      </div>
      <div id="regen-sel-preview" style="font-size:0.74rem;color:#777;background:#f5f5f5;padding:4px 7px;border-radius:4px;max-height:42px;overflow:hidden;font-style:italic;"></div>
      <textarea id="regen-sel-instruction" rows="2"
        placeholder="Aanpasinstructie… (Enter = verzenden, Shift+Enter = nieuwe regel)"
        style="width:100%;box-sizing:border-box;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:0.85rem;resize:vertical;font-family:inherit;"></textarea>
      <div style="display:flex;gap:8px;align-items:center;">
        <button id="regen-sel-btn"
          style="background:#0070f3;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:0.85rem;cursor:pointer;font-family:inherit;">
          Hergenereren
        </button>
        <span id="regen-sel-status" style="font-size:0.8rem;color:#666;"></span>
      </div>
    </div>`;

  document.body.appendChild(popup);
  _regenPopupEl = popup;
  return popup;
}

function _hideRegenPopup() {
  if (_regenPopupEl) _regenPopupEl.style.display = 'none';
  _regenSel = null;
}

function _rangeToHtml(range) {
  const wrapper = document.createElement('div');
  wrapper.appendChild(range.cloneContents());
  return wrapper.innerHTML;
}

function _positionAndShowPopup(selectedText, selData, anchorX, anchorY) {
  const popup = _buildRegenPopup();
  _regenSel = selData;

  const previewEl = popup.querySelector('#regen-sel-preview');
  if (previewEl) {
    previewEl.textContent = selectedText.length > 90
      ? selectedText.substring(0, 90) + '…'
      : selectedText;
  }
  popup.querySelector('#regen-sel-status').textContent = '';
  popup.querySelector('#regen-sel-instruction').value = '';

  popup.style.visibility = 'hidden';
  popup.style.display = 'block';
  const W  = popup.offsetWidth  || 340;
  const H  = popup.offsetHeight || 160;
  const VW = window.innerWidth;
  const VH = window.innerHeight;
  let x = anchorX + 14;
  let y = anchorY + 14;
  if (x + W > VW - 8) x = anchorX - W - 8;
  if (y + H > VH - 8) y = anchorY - H - 8;
  popup.style.left = `${Math.max(8, x)}px`;
  popup.style.top  = `${Math.max(8, y)}px`;
  popup.style.visibility = 'visible';

  setTimeout(() => popup.querySelector('#regen-sel-instruction')?.focus(), 30);
}

export function initSelectionRegenPopup() {
  const titleInput   = document.getElementById('title');
  const contentInput = document.getElementById('content');
  const textareaEls  = [titleInput, contentInput].filter(Boolean);

  const popup = _buildRegenPopup();

  document.addEventListener('selectionchange', () => {
    if (_mouseIsDown) return;

    clearTimeout(_regenSelChangeTimer);
    _regenSelChangeTimer = setTimeout(() => {
      const active = document.activeElement;

      if (popup.contains(active)) return;

      if (textareaEls.includes(active)) {
        const start = active.selectionStart;
        const end   = active.selectionEnd;
        if (start === end) { _hideRegenPopup(); return; }
        const selectedText = active.value.substring(start, end);
        if (!selectedText.trim()) { _hideRegenPopup(); return; }

        const rect = active.getBoundingClientRect();
        _positionAndShowPopup(
          selectedText,
          { mode: 'textarea', el: active, start, end, text: selectedText },
          rect.left + rect.width / 2,
          rect.top - 8
        );
        return;
      }

      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
        if (_regenSel?.mode === 'preview') _hideRegenPopup();
        return;
      }

      const contentPreviewDiv = document.getElementById('pub-content-preview');
      const imagePreviewDiv = document.getElementById('publish-preview');
      const range = sel.getRangeAt(0);
      const inContent = contentPreviewDiv && contentPreviewDiv.contains(range.commonAncestorContainer);
      const inImage = imagePreviewDiv && imagePreviewDiv.contains(range.commonAncestorContainer);
      if (!inContent && !inImage) {
        if (_regenSel?.mode === 'preview') _hideRegenPopup();
        return;
      }

      const selectedText = sel.toString().trim();
      if (!selectedText) return;
      const selectedHtml = _rangeToHtml(range);

      const titleBody   = document.getElementById('preview-title-body');
      const contentBody = document.getElementById('preview-content-body');
      let containerId = null;
      if (titleBody   && titleBody.contains(range.commonAncestorContainer))   containerId = 'preview-title-body';
      if (contentBody && contentBody.contains(range.commonAncestorContainer)) containerId = 'preview-content-body';

      const frozenRange = range.cloneRange();
      const rects    = range.getClientRects();
      const lastRect = rects[rects.length - 1] || range.getBoundingClientRect();

      _positionAndShowPopup(
        selectedText,
        { mode: 'preview', range: frozenRange, text: selectedText, html: selectedHtml, containerId },
        lastRect.right,
        lastRect.bottom
      );
    }, 80);
  });

  textareaEls.forEach(el => {
    el.addEventListener('mouseup', (e) => {
      setTimeout(() => {
        const start = el.selectionStart;
        const end   = el.selectionEnd;
        if (start === end) { _hideRegenPopup(); return; }
        const selectedText = el.value.substring(start, end);
        if (!selectedText.trim()) { _hideRegenPopup(); return; }
        _positionAndShowPopup(
          selectedText,
          { mode: 'textarea', el, start, end, text: selectedText },
          e.clientX, e.clientY
        );
      }, 0);
    });
  });

  document.addEventListener('mouseup', (e) => {
    const contentPreviewDiv = document.getElementById('pub-content-preview');
    const imagePreviewDiv = document.getElementById('publish-preview');
    const inContent = contentPreviewDiv && contentPreviewDiv.contains(e.target);
    const inImage = imagePreviewDiv && imagePreviewDiv.contains(e.target);
    if (!inContent && !inImage) return;
    if (popup.contains(e.target)) return;

    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;

      const range = sel.getRangeAt(0);
      const rangeInContent = contentPreviewDiv && contentPreviewDiv.contains(range.commonAncestorContainer);
      const rangeInImage = imagePreviewDiv && imagePreviewDiv.contains(range.commonAncestorContainer);
      if (!rangeInContent && !rangeInImage) return;

      const selectedText = sel.toString().trim();
      if (!selectedText) return;
      const selectedHtml = _rangeToHtml(range);

      const titleBody   = document.getElementById('preview-title-body');
      const contentBody = document.getElementById('preview-content-body');
      let containerId = null;
      if (titleBody   && titleBody.contains(range.commonAncestorContainer))   containerId = 'preview-title-body';
      if (contentBody && contentBody.contains(range.commonAncestorContainer)) containerId = 'preview-content-body';

      const frozenRange = range.cloneRange();
      _positionAndShowPopup(
        selectedText,
        { mode: 'preview', range: frozenRange, text: selectedText, html: selectedHtml, containerId },
        e.clientX, e.clientY
      );
    }, 0);
  });

  document.addEventListener('mousedown', (e) => {
    if (popup.style.display === 'none') return;
    if (popup.contains(e.target)) return;
    if (textareaEls.includes(e.target)) return;
    const previewDiv = document.getElementById('publish-preview');
    const contentPreviewDiv = document.getElementById('pub-content-preview');
    if (previewDiv && previewDiv.contains(e.target)) return;
    if (contentPreviewDiv && contentPreviewDiv.contains(e.target)) return;
    _hideRegenPopup();
  });

  popup.addEventListener('click', (e) => {
    if (e.target.id === 'regen-sel-close') _hideRegenPopup();
  });

  popup.addEventListener('click', (e) => {
    if (e.target.id === 'regen-sel-btn') submitInlineRegen();
  });
  popup.addEventListener('keydown', (e) => {
    if (e.target.id === 'regen-sel-instruction' && e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitInlineRegen();
    }
  });
}

async function submitInlineRegen() {
  if (!_regenSel) return;
  const popup = _regenPopupEl;
  if (!popup) return;

  const instruction = (popup.querySelector('#regen-sel-instruction')?.value || '').trim();
  if (!instruction) { showAlert('Voer een aanpasinstructie in.', 'error'); return; }

  const language  = window._currentDraftWithImages?.language || 'nl';
  const statusEl  = popup.querySelector('#regen-sel-status');
  const regenBtn  = popup.querySelector('#regen-sel-btn');
  if (statusEl) statusEl.textContent = 'Bezig…';
  if (regenBtn) regenBtn.disabled = true;

  try {
    const sel = _regenSel;

    let selectedText = sel.mode === 'preview' ? (sel.html || sel.text) : sel.text;
    let contextBefore = '';
    let contextAfter  = '';

    if (sel.mode === 'textarea') {
      const full = sel.el.value;
      contextBefore = full.substring(Math.max(0, sel.start - 300), sel.start);
      contextAfter  = full.substring(sel.end, Math.min(full.length, sel.end + 300));
    } else {
      const container = sel.containerId
        ? document.getElementById(sel.containerId)
        : document.getElementById('publish-preview');
      if (container) {
        const full = container.innerHTML || '';
        const lookup = sel.html || selectedText;
        const idx  = full.indexOf(lookup);
        if (idx !== -1) {
          contextBefore = full.substring(Math.max(0, idx - 300), idx);
          contextAfter  = full.substring(idx + lookup.length, idx + lookup.length + 300);
        }
      }
    }

    const result = await api.regenerateInline(
      selectedText, instruction, contextBefore, contextAfter, language
    );
    const replacement = result.replacementText || '';

    if (sel.mode === 'textarea') {
      const full = sel.el.value;
      sel.el.value = full.substring(0, sel.start) + replacement + full.substring(sel.end);
      if (window._currentDraftWithImages) {
        if (sel.el.id === 'title')   window._currentDraftWithImages.title       = sel.el.value;
        if (sel.el.id === 'content') window._currentDraftWithImages.contentHtml = sel.el.value;
      }
    } else {
      const range = sel.range;
      range.deleteContents();

      const tpl = document.createElement('template');
      tpl.innerHTML = replacement;
      const frag = tpl.content.cloneNode(true);
      range.insertNode(frag);

      const contentBody = document.getElementById('preview-content-body');
      const titleBody   = document.getElementById('preview-title-body');
      const contentInput = document.getElementById('content');
      const titleInput   = document.getElementById('title');

      if (sel.containerId === 'preview-content-body' && contentBody && contentInput) {
        contentInput.value = contentBody.innerHTML;
        if (window._currentDraftWithImages) window._currentDraftWithImages.contentHtml = contentInput.value;
      } else if (sel.containerId === 'preview-title-body' && titleBody && titleInput) {
        titleInput.value = titleBody.textContent || titleBody.innerText || '';
        if (window._currentDraftWithImages) window._currentDraftWithImages.title = titleInput.value;
      }
    }

    _hideRegenPopup();
    if (sel.mode === 'textarea') updatePublishPreviewFromForm();
    queueDraftAutosave();
    showAlert('Selectie succesvol herschreven.', 'success');

  } catch (error) {
    console.error('Inline regen error:', error);
    if (statusEl) statusEl.textContent = '';
    showAlert(error.message || 'Fout bij hergenereren', 'error');
  } finally {
    if (regenBtn) regenBtn.disabled = false;
  }
}
