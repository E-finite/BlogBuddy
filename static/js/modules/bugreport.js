/**
 * Bug Report module – floating bug report modal.
 */

import { api } from '../api.js';
import { showAlert, setButtonLoading } from '../ui.js';

export function initBugReportModal() {
  const fab = document.getElementById('bug-report-fab');
  const overlay = document.getElementById('bug-report-overlay');
  if (!fab || !overlay) return;

  const form = document.getElementById('bug-report-form');
  const closeBtn = document.getElementById('bug-report-close');
  const cancelBtn = document.getElementById('bug-report-cancel');
  const doneBtn = document.getElementById('bug-report-done');
  const successPanel = document.getElementById('bug-report-success');
  const descriptionField = document.getElementById('bug-report-description');
  const charCount = document.getElementById('bug-report-char-count');
  const pageUrlField = document.getElementById('bug-report-page-url');

  function openModal() {
    pageUrlField.value = window.location.pathname;
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    overlay.classList.remove('active');
    document.body.style.overflow = '';
    setTimeout(() => {
      form.reset();
      form.style.display = '';
      successPanel.style.display = 'none';
      if (charCount) charCount.textContent = '0';
    }, 300);
  }

  fab.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  if (doneBtn) doneBtn.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  if (descriptionField && charCount) {
    descriptionField.addEventListener('input', () => {
      charCount.textContent = descriptionField.value.length;
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById('bug-report-submit');
    const category = form.querySelector('input[name="bug-category"]:checked')?.value || 'bug';
    const title = form.querySelector('#bug-report-title').value.trim();
    const description = descriptionField.value.trim();
    const pageUrl = pageUrlField.value;

    if (!title || !description) {
      showAlert('Vul titel en beschrijving in.', 'error');
      return;
    }

    setButtonLoading(submitBtn, true);
    try {
      await api.submitBugReport(category, title, description, pageUrl);
      form.style.display = 'none';
      successPanel.style.display = '';
    } catch (err) {
      showAlert('Fout bij versturen: ' + err.message, 'error');
    } finally {
      setButtonLoading(submitBtn, false);
    }
  });
}
